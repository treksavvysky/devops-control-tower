"""
JCT MCP Server — exposes control tower operations to Claude Code.

Usage:
    python -m devops_control_tower.mcp          # stdio transport
    jct-mcp                                      # via pyproject.toml entry point

Claude Code configuration (.claude/settings.local.json):
    {
      "mcpServers": {
        "jct": {
          "command": "python3",
          "args": ["-m", "devops_control_tower.mcp"]
        }
      }
    }
"""
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

server = FastMCP(
    name="jct",
    instructions=(
        "Jules Control Tower: AI-assisted development operations. "
        "Claim tasks from the queue, read context and constraints, "
        "execute work, report artifacts, and complete tasks. "
        "All operations are audited with full causality tracking."
    ),
)


# ---------------------------------------------------------------------------
# Lazy-initialized singletons
# ---------------------------------------------------------------------------

_session_factory = None


def _get_db():
    """Get a new DB session. Caller must close it."""
    global _session_factory
    if _session_factory is None:
        from devops_control_tower.db.base import get_session_local

        _session_factory = get_session_local()
    return _session_factory()


def _success(**kwargs: Any) -> str:
    """Format a success response."""
    return json.dumps({"success": True, **kwargs}, default=str)


def _error(code: str, message: str, suggestion: str = "") -> str:
    """Format an error response."""
    err: Dict[str, str] = {"code": code, "message": message}
    if suggestion:
        err["suggestion"] = suggestion
    return json.dumps({"success": False, "error": err})


# ---------------------------------------------------------------------------
# In-memory state for active claims
# ---------------------------------------------------------------------------

# Maps task_id -> {"run_id", "trace_uri", "store"}
_active_claims: Dict[str, Dict[str, Any]] = {}


def _get_active_claim(task_id: str, db=None):
    """Get active claim for a task. Falls back to DB query."""
    if task_id in _active_claims:
        return _active_claims[task_id]

    if db is None:
        return None

    from devops_control_tower.db.cwom_models import CWOMRunModel
    from devops_control_tower.db.models import TaskModel
    from devops_control_tower.worker.storage import create_trace_store

    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if task and task.cwom_issue_id:
        run = (
            db.query(CWOMRunModel)
            .filter(
                CWOMRunModel.for_issue_id == task.cwom_issue_id,
                CWOMRunModel.status == "running",
            )
            .first()
        )
        if run:
            from devops_control_tower.config import get_settings

            settings = get_settings()
            store = create_trace_store(settings.jct_trace_root, run.id)
            claim = {
                "run_id": run.id,
                "trace_uri": run.artifact_root_uri or store.get_uri(),
                "store": store,
            }
            _active_claims[task_id] = claim
            return claim
    return None


# ---------------------------------------------------------------------------
# Lifecycle Tools
# ---------------------------------------------------------------------------


@server.tool(
    name="jct_list_tasks",
    description=(
        "List tasks available in the JCT queue. Shows queued tasks by default. "
        "Use this to see what work is available before claiming a task."
    ),
)
def jct_list_tasks(
    status: str = "queued",
    operation: Optional[str] = None,
    limit: int = 10,
) -> str:
    """List tasks filtered by status and operation."""
    db = _get_db()
    try:
        from devops_control_tower.db.services import TaskService

        svc = TaskService(db)
        tasks = svc.get_tasks(
            status=status,
            operation=operation,
            limit=limit,
        )
        return _success(
            tasks=[
                {
                    "task_id": str(t.id),
                    "operation": t.operation,
                    "objective": t.objective,
                    "target_repo": t.target_repo,
                    "target_ref": t.target_ref,
                    "status": t.status,
                    "time_budget_seconds": t.time_budget_seconds,
                    "queued_at": t.queued_at,
                    "cwom_issue_id": t.cwom_issue_id,
                }
                for t in tasks
            ],
            count=len(tasks),
        )
    except Exception as exc:
        return _error("LIST_TASKS_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_claim_task",
    description=(
        "Claim a queued task for execution. Atomically transitions the task from "
        "'queued' to 'running' and creates a CWOM Run. Returns the full task context "
        "including objective, constraints, and context packet. If the task was already "
        "claimed by another worker, returns an error."
    ),
)
def jct_claim_task(task_id: str) -> str:
    """Claim a queued task for execution."""
    db = _get_db()
    try:
        from sqlalchemy import text

        from devops_control_tower.config import get_settings
        from devops_control_tower.db.audit_service import AuditService
        from devops_control_tower.db.cwom_models import (
            CWOMConstraintSnapshotModel,
            CWOMContextPacketModel,
            CWOMIssueModel,
            CWOMRunModel,
        )
        from devops_control_tower.db.models import TaskModel
        from devops_control_tower.worker.storage import (
            create_trace_store,
            get_trace_uri,
        )

        settings = get_settings()

        # Find the task
        try:
            task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        except Exception:
            task = None
        if not task:
            return _error(
                "TASK_NOT_FOUND",
                f"Task '{task_id}' not found.",
                "Use jct_list_tasks to find available tasks.",
            )

        if task.status != "queued":
            return _error(
                "TASK_ALREADY_CLAIMED",
                f"Task '{task_id}' is no longer queued "
                f"(current status: {task.status}).",
                "Use jct_list_tasks to find another available task.",
            )

        # Atomically claim (optimistic locking)
        now = datetime.now(timezone.utc)
        result = db.execute(
            text(
                """
                UPDATE tasks
                SET status = 'running',
                    started_at = :started_at,
                    assigned_to = :worker_id
                WHERE id = :task_id AND status = 'queued'
            """
            ),
            {
                "task_id": str(task.id),
                "started_at": now,
                "worker_id": "claude-code",
            },
        )
        db.commit()

        if result.rowcount == 0:
            return _error(
                "TASK_ALREADY_CLAIMED",
                f"Task '{task_id}' was claimed by another worker.",
                "Use jct_list_tasks to find another available task.",
            )

        db.refresh(task)

        # Create CWOM Run if task has linked issue
        run_id = None
        run_data = None
        context_packet_data = None
        constraint_snapshot_data = None
        issue_data = None

        if task.cwom_issue_id:
            issue = (
                db.query(CWOMIssueModel)
                .filter(CWOMIssueModel.id == task.cwom_issue_id)
                .first()
            )

            if issue:
                run_id = str(uuid.uuid4())
                trace_uri = get_trace_uri(
                    settings.jct_trace_root, run_id
                )

                run = CWOMRunModel(
                    id=run_id,
                    kind="Run",
                    trace_id=task.trace_id,
                    for_issue_id=issue.id,
                    for_issue_kind="Issue",
                    repo_id=issue.repo_id,
                    repo_kind="Repo",
                    status="running",
                    mode="agent",
                    executor={
                        "type": "claude_code",
                        "version": "0.1.0",
                        "worker_id": "claude-code",
                    },
                    inputs={
                        "task_id": str(task.id),
                        "operation": task.operation,
                    },
                    artifact_root_uri=trace_uri,
                    plan={},
                    telemetry={},
                    cost={},
                    outputs={},
                )
                db.add(run)

                issue.status = "running"

                audit = AuditService(db)
                audit.log_create(
                    entity_kind="Run",
                    entity_id=run_id,
                    after=run.to_dict(),
                    actor_kind="agent",
                    actor_id="claude-code",
                    note=f"Run created via MCP for task {task.id}",
                    trace_id=task.trace_id,
                )

                db.commit()

                run_data = {
                    "id": run_id,
                    "status": "running",
                    "mode": "agent",
                    "artifact_root_uri": trace_uri,
                }

                issue_data = {
                    "id": issue.id,
                    "title": issue.title,
                    "type": issue.type,
                    "status": issue.status,
                }
                if issue.acceptance:
                    issue_data["acceptance_criteria"] = (
                        issue.acceptance.get("criteria", [])
                        if isinstance(issue.acceptance, dict)
                        else []
                    )

                # Load context packet
                cp = (
                    db.query(CWOMContextPacketModel)
                    .filter(
                        CWOMContextPacketModel.for_issue_id == issue.id
                    )
                    .first()
                )
                if cp:
                    context_packet_data = cp.to_dict()

                # Load constraint snapshot
                cs_id = None
                if cp and cp.constraint_snapshot_id:
                    cs_id = cp.constraint_snapshot_id
                if cs_id:
                    cs = (
                        db.query(CWOMConstraintSnapshotModel)
                        .filter(CWOMConstraintSnapshotModel.id == cs_id)
                        .first()
                    )
                    if cs:
                        constraint_snapshot_data = cs.to_dict()

                # Initialize trace store and cache claim
                store = create_trace_store(settings.jct_trace_root, run_id)
                _active_claims[task_id] = {
                    "run_id": run_id,
                    "trace_uri": trace_uri,
                    "store": store,
                }

                # Write initial manifest
                store.write_json(
                    "manifest.json",
                    {
                        "version": "1.0",
                        "task_id": str(task.id),
                        "run_id": run_id,
                        "trace_id": task.trace_id,
                        "executor": {
                            "type": "claude_code",
                            "version": "0.1.0",
                        },
                        "started_at": now.isoformat(),
                        "status": "running",
                    },
                )

        return _success(
            task_id=str(task.id),
            run_id=run_id,
            trace_id=task.trace_id,
            objective=task.objective,
            operation=task.operation,
            target={
                "repo": task.target_repo,
                "ref": task.target_ref,
                "path": task.target_path,
            },
            constraints={
                "time_budget_seconds": task.time_budget_seconds,
                "allow_network": task.allow_network,
                "allow_secrets": task.allow_secrets,
            },
            issue=issue_data,
            context_packet=context_packet_data,
            constraint_snapshot=constraint_snapshot_data,
        )

    except Exception as exc:
        db.rollback()
        return _error("CLAIM_TASK_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_get_context",
    description=(
        "Get the full context packet and constraint snapshot for a task. "
        "Use this to understand the detailed requirements, prior art, "
        "acceptance criteria, and operating constraints for your current task."
    ),
)
def jct_get_context(task_id: str) -> str:
    """Get context packet and constraints for a claimed task."""
    db = _get_db()
    try:
        from devops_control_tower.db.cwom_models import (
            CWOMConstraintSnapshotModel,
            CWOMContextPacketModel,
            CWOMDoctrineRefModel,
            CWOMIssueModel,
        )
        from devops_control_tower.db.models import TaskModel

        try:
            task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        except Exception:
            task = None
        if not task:
            return _error("TASK_NOT_FOUND", f"Task '{task_id}' not found.")

        result: Dict[str, Any] = {"task_id": str(task.id)}

        if task.cwom_issue_id:
            issue = (
                db.query(CWOMIssueModel)
                .filter(CWOMIssueModel.id == task.cwom_issue_id)
                .first()
            )
            if issue:
                result["issue"] = issue.to_dict()

                # Context packet
                cp = (
                    db.query(CWOMContextPacketModel)
                    .filter(
                        CWOMContextPacketModel.for_issue_id == issue.id
                    )
                    .first()
                )
                if cp:
                    result["context_packet"] = cp.to_dict()

                    # Constraint snapshot from context packet
                    if cp.constraint_snapshot_id:
                        cs = (
                            db.query(CWOMConstraintSnapshotModel)
                            .filter(
                                CWOMConstraintSnapshotModel.id
                                == cp.constraint_snapshot_id
                            )
                            .first()
                        )
                        if cs:
                            result["constraint_snapshot"] = cs.to_dict()

                # Doctrine refs via join table
                if hasattr(issue, "doctrine_refs") and issue.doctrine_refs:
                    result["doctrine_refs"] = [
                        d.to_dict() for d in issue.doctrine_refs
                    ]

        return _success(**result)
    except Exception as exc:
        return _error("GET_CONTEXT_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_report_artifact",
    description=(
        "Report an artifact produced during task execution. Call this for each "
        "meaningful output: code patches, documentation, analysis reports, etc. "
        "The artifact content or URI is recorded in the CWOM and trace store."
    ),
)
def jct_report_artifact(
    task_id: str,
    title: str,
    artifact_type: str,
    content: Optional[str] = None,
    uri: Optional[str] = None,
    media_type: str = "text/plain",
) -> str:
    """Report an artifact produced during execution."""
    # Validate artifact_type against the CWOM enum
    from devops_control_tower.cwom.enums import ArtifactType

    valid_types = [e.value for e in ArtifactType]
    if artifact_type not in valid_types:
        return _error(
            "INVALID_ARTIFACT_TYPE",
            f"'{artifact_type}' is not a valid artifact type. "
            f"Valid types: {', '.join(valid_types)}",
        )

    db = _get_db()
    try:
        from devops_control_tower.db.audit_service import AuditService
        from devops_control_tower.db.cwom_models import CWOMArtifactModel
        from devops_control_tower.db.models import TaskModel

        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return _error("TASK_NOT_FOUND", f"Task '{task_id}' not found.")

        claim = _get_active_claim(task_id, db)
        if not claim:
            return _error(
                "NO_ACTIVE_CLAIM",
                f"No active claim found for task '{task_id}'.",
                "Use jct_claim_task first.",
            )

        run_id = claim["run_id"]
        store = claim.get("store")

        # Write content to trace store
        artifact_uri = uri
        if content and store:
            safe_title = (
                title.lower().replace(" ", "_").replace("/", "_")[:50]
            )
            artifact_path = f"artifacts/{safe_title}"
            store.write_text(artifact_path, content)
            artifact_uri = f"{store.get_uri()}/{artifact_path}"
            store.append_event(
                {
                    "event": "artifact_reported",
                    "title": title,
                    "type": artifact_type,
                    "path": artifact_path,
                }
            )

        # Create CWOM Artifact
        artifact_id = str(uuid.uuid4())

        # Get the issue_id from the run
        from devops_control_tower.db.cwom_models import CWOMRunModel

        run = db.query(CWOMRunModel).filter(CWOMRunModel.id == run_id).first()
        issue_id = run.for_issue_id if run else None

        artifact = CWOMArtifactModel(
            id=artifact_id,
            kind="Artifact",
            trace_id=task.trace_id,
            produced_by_id=run_id,
            produced_by_kind="Run",
            for_issue_id=issue_id,
            for_issue_kind="Issue" if issue_id else None,
            type=artifact_type,
            title=title,
            uri=artifact_uri,
            media_type=media_type,
        )
        db.add(artifact)

        audit = AuditService(db)
        audit.log_create(
            entity_kind="Artifact",
            entity_id=artifact_id,
            after=artifact.to_dict(),
            actor_kind="agent",
            actor_id="claude-code",
            note=f"Artifact reported via MCP: {title}",
            trace_id=task.trace_id,
        )

        db.commit()

        return _success(
            artifact_id=artifact_id,
            task_id=str(task.id),
            run_id=run_id,
            title=title,
            type=artifact_type,
            uri=artifact_uri,
        )
    except Exception as exc:
        db.rollback()
        return _error("REPORT_ARTIFACT_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_complete_task",
    description=(
        "Complete a claimed task. Provide a summary of what was done and whether "
        "it succeeded. This triggers the proof evaluation and review pipeline. "
        "After calling this, the task enters the prove/review flow automatically."
    ),
)
def jct_complete_task(
    task_id: str,
    success: bool,
    summary: str,
    outputs: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
    """Complete a claimed task and trigger prove/review."""
    db = _get_db()
    try:
        from devops_control_tower.db.audit_service import AuditService
        from devops_control_tower.db.cwom_models import (
            CWOMIssueModel,
            CWOMRunModel,
        )
        from devops_control_tower.db.models import TaskModel
        from devops_control_tower.worker.pipeline import (
            apply_review_policy,
            run_prove,
        )

        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return _error("TASK_NOT_FOUND", f"Task '{task_id}' not found.")

        if task.status != "running":
            return _error(
                "TASK_NOT_RUNNING",
                f"Task '{task_id}' is not running "
                f"(current status: {task.status}).",
            )

        claim = _get_active_claim(task_id, db)
        now = datetime.now(timezone.utc)

        # Parse outputs if provided as JSON string
        outputs_dict = {}
        if outputs:
            try:
                outputs_dict = json.loads(outputs)
            except json.JSONDecodeError:
                outputs_dict = {"raw": outputs}
        outputs_dict["summary"] = summary

        # Update task
        task.status = "completed" if success else "failed"
        task.completed_at = now
        task.result = outputs_dict
        if not success and error_message:
            task.error = error_message

        response: Dict[str, Any] = {
            "task_id": str(task.id),
            "task_status": task.status,
        }

        # Update CWOM Run if exists
        run = None
        if claim:
            run_id = claim["run_id"]
            store = claim.get("store")

            run = (
                db.query(CWOMRunModel)
                .filter(CWOMRunModel.id == run_id)
                .first()
            )

            if run:
                run.status = "done" if success else "failed"
                run.outputs = outputs_dict

                if not success:
                    run.failure = {
                        "code": "AGENT_REPORTED_FAILURE",
                        "message": error_message or summary,
                    }

                # Update linked issue
                issue = (
                    db.query(CWOMIssueModel)
                    .filter(CWOMIssueModel.id == run.for_issue_id)
                    .first()
                )
                if issue:
                    issue.status = "done" if success else "failed"

                # Audit log
                audit = AuditService(db)
                audit.log_status_change(
                    entity_kind="Run",
                    entity_id=run.id,
                    old_status="running",
                    new_status="done" if success else "failed",
                    actor_kind="agent",
                    actor_id="claude-code",
                    note=summary,
                    trace_id=task.trace_id,
                )

                # Write final manifest
                if store:
                    store.write_json(
                        "manifest.json",
                        {
                            "version": "1.0",
                            "task_id": str(task.id),
                            "run_id": run_id,
                            "trace_id": task.trace_id,
                            "completed_at": now.isoformat(),
                            "status": "completed" if success else "failed",
                            "result": outputs_dict,
                        },
                    )
                    if store:
                        task.trace_path = store.get_uri()

                response["run_id"] = run_id
                response["run_status"] = run.status

                # Flush (not commit) so prove can read updated state
                db.flush()

                # Step 4: Prove
                try:
                    evidence_pack = run_prove(
                        db=db,
                        run=run,
                        task=task,
                        store=store,
                        prover_id="claude-code-mcp",
                    )
                    response["evidence_pack"] = {
                        "id": evidence_pack.id,
                        "verdict": evidence_pack.verdict,
                        "verdict_reason": evidence_pack.verdict_reason,
                    }

                    # Step 5: Review
                    if success:
                        review_result = apply_review_policy(
                            db=db,
                            task=task,
                            run=run,
                            evidence_pack=evidence_pack,
                            actor_id="claude-code",
                            trace_id=task.trace_id,
                        )
                        response["review"] = review_result
                        # Refresh run status after review policy
                        db.refresh(run)
                        response["run_status"] = run.status
                except Exception as prove_exc:
                    logger.warning(
                        "Prove/review failed for run %s: %s",
                        run_id,
                        prove_exc,
                    )
                    response["prove_error"] = str(prove_exc)

            # Clean up active claim
            _active_claims.pop(task_id, None)

        db.commit()
        return _success(**response)

    except Exception as exc:
        db.rollback()
        return _error("COMPLETE_TASK_ERROR", str(exc))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Observation Tools
# ---------------------------------------------------------------------------


@server.tool(
    name="jct_get_task",
    description=(
        "Get detailed information about a specific task, including its status, "
        "linked CWOM objects, and execution history."
    ),
)
def jct_get_task(task_id: str) -> str:
    """Get full details of a task."""
    db = _get_db()
    try:
        from devops_control_tower.db.models import TaskModel

        try:
            task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        except Exception:
            task = None
        if not task:
            return _error("TASK_NOT_FOUND", f"Task '{task_id}' not found.")
        return _success(task=task.to_dict())
    except Exception as exc:
        return _error("GET_TASK_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_get_run",
    description=(
        "Get detailed information about a CWOM Run, including its status, "
        "executor info, outputs, artifacts, and evidence pack."
    ),
)
def jct_get_run(run_id: str) -> str:
    """Get full details of a CWOM Run."""
    db = _get_db()
    try:
        from devops_control_tower.db.cwom_models import CWOMRunModel
        from devops_control_tower.cwom.services import EvidencePackService

        run = db.query(CWOMRunModel).filter(CWOMRunModel.id == run_id).first()
        if not run:
            return _error("RUN_NOT_FOUND", f"Run '{run_id}' not found.")

        result = run.to_dict()

        # Include evidence pack if exists
        ep_svc = EvidencePackService(db)
        ep = ep_svc.get_for_run(run_id)
        if ep:
            result["evidence_pack"] = ep.to_dict()

        return _success(run=result)
    except Exception as exc:
        return _error("GET_RUN_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_get_evidence",
    description=(
        "Get the evidence pack by run ID or evidence pack ID. "
        "Shows the verdict (pass/fail/partial), criteria evaluations, "
        "collected evidence, and any missing items."
    ),
)
def jct_get_evidence(run_id: str) -> str:
    """Get evidence pack by run_id or evidence_pack_id."""
    db = _get_db()
    try:
        from devops_control_tower.cwom.services import EvidencePackService

        svc = EvidencePackService(db)
        # Try as run_id first, then fall back to direct evidence pack ID
        ep = svc.get_for_run(run_id)
        if not ep:
            ep = svc.get(run_id)
        if not ep:
            return _error(
                "EVIDENCE_NOT_FOUND",
                f"No evidence pack found for '{run_id}' "
                "(searched by run ID and evidence pack ID).",
            )
        return _success(evidence_pack=ep.to_dict())
    except Exception as exc:
        return _error("GET_EVIDENCE_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_get_audit_trail",
    description=(
        "Get the audit trail for a task, issue, or run. Shows all state changes, "
        "who made them, and when. Useful for debugging or understanding history."
    ),
)
def jct_get_audit_trail(
    entity_kind: str,
    entity_id: str,
    limit: int = 50,
) -> str:
    """Get audit trail for an entity."""
    db = _get_db()
    try:
        from devops_control_tower.db.audit_service import AuditService

        audit = AuditService(db)
        entries = audit.query_by_entity(entity_kind, entity_id, limit=limit)
        return _success(
            entries=[e.to_dict() for e in entries],
            count=len(entries),
        )
    except Exception as exc:
        return _error("GET_AUDIT_ERROR", str(exc))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Review Tools
# ---------------------------------------------------------------------------


@server.tool(
    name="jct_submit_review",
    description=(
        "Submit a review decision for a completed task's evidence pack. "
        "Use 'approved' to accept, 'rejected' to reject, or 'needs_changes' "
        "to request modifications. This transitions the Issue and Run status."
    ),
)
def jct_submit_review(
    evidence_pack_id: str,
    decision: str,
    reason: str,
    reviewer_name: str = "claude-code",
) -> str:
    """Submit a review decision for an evidence pack."""
    db = _get_db()
    try:
        from devops_control_tower.cwom.services import (
            EvidencePackService,
            ReviewDecisionService,
        )

        if decision not in ("approved", "rejected", "needs_changes"):
            return _error(
                "INVALID_DECISION",
                f"Decision must be 'approved', 'rejected', or "
                f"'needs_changes', got '{decision}'.",
            )

        # Get evidence pack
        ep_svc = EvidencePackService(db)
        ep = ep_svc.get(evidence_pack_id)
        if not ep:
            return _error(
                "EVIDENCE_NOT_FOUND",
                f"Evidence pack '{evidence_pack_id}' not found.",
            )

        review_data = {
            "for_evidence_pack": {
                "kind": "EvidencePack",
                "id": evidence_pack_id,
            },
            "for_run": {"kind": "Run", "id": ep.for_run_id},
            "for_issue": {"kind": "Issue", "id": ep.for_issue_id},
            "reviewer": {
                "actor_kind": "agent",
                "actor_id": reviewer_name,
                "display": reviewer_name,
            },
            "decision": decision,
            "decision_reason": reason,
            "tags": ["mcp-review"],
        }

        review_svc = ReviewDecisionService(db)
        review = review_svc.create(
            review_data=review_data,
            actor_kind="agent",
            actor_id=reviewer_name,
        )

        db.commit()

        return _success(
            review_id=review.id,
            decision=decision,
            evidence_pack_id=evidence_pack_id,
            issue_id=ep.for_issue_id,
            run_id=ep.for_run_id,
        )
    except Exception as exc:
        db.rollback()
        return _error("SUBMIT_REVIEW_ERROR", str(exc))
    finally:
        db.close()


@server.tool(
    name="jct_list_pending_reviews",
    description=(
        "List tasks that are under review and awaiting a decision. "
        "Use this to find work that needs review approval."
    ),
)
def jct_list_pending_reviews(limit: int = 10) -> str:
    """List evidence packs awaiting review."""
    db = _get_db()
    try:
        from devops_control_tower.db.cwom_models import (
            CWOMEvidencePackModel,
            CWOMIssueModel,
        )

        # Find issues under review
        issues = (
            db.query(CWOMIssueModel)
            .filter(CWOMIssueModel.status == "under_review")
            .limit(limit)
            .all()
        )

        results = []
        for issue in issues:
            ep = (
                db.query(CWOMEvidencePackModel)
                .filter(CWOMEvidencePackModel.for_issue_id == issue.id)
                .order_by(CWOMEvidencePackModel.created_at.desc())
                .first()
            )
            results.append(
                {
                    "issue_id": issue.id,
                    "issue_title": issue.title,
                    "issue_status": issue.status,
                    "evidence_pack_id": ep.id if ep else None,
                    "verdict": ep.verdict if ep else None,
                    "verdict_reason": ep.verdict_reason if ep else None,
                    "run_id": ep.for_run_id if ep else None,
                }
            )

        return _success(pending_reviews=results, count=len(results))
    except Exception as exc:
        return _error("LIST_REVIEWS_ERROR", str(exc))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task Creation Tools
# ---------------------------------------------------------------------------


@server.tool(
    name="jct_enqueue_task",
    description=(
        "Submit a new task to the JCT queue. The task goes through policy "
        "validation and, if accepted, is persisted with status 'queued'. "
        "Optionally creates CWOM objects (Issue, ContextPacket) automatically."
    ),
)
def jct_enqueue_task(
    objective: str,
    operation: str,
    target_repo: str,
    target_ref: str = "main",
    target_path: str = "",
    time_budget_seconds: int = 3600,
    priority: str = "P2",
    acceptance_criteria: Optional[List[str]] = None,
    context_summary: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    create_cwom: bool = True,
) -> str:
    """Submit a new task to the queue."""
    db = _get_db()
    try:
        from devops_control_tower.cwom.task_adapter import task_to_cwom
        from devops_control_tower.db.audit_service import AuditService
        from devops_control_tower.db.services import TaskService
        from devops_control_tower.policy import PolicyError
        from devops_control_tower.policy import evaluate as evaluate_policy
        from devops_control_tower.schemas.task_v1 import TaskCreateV1

        trace_id = str(uuid.uuid4())

        # Build task spec
        task_data = {
            "version": "1.0",
            "requested_by": {
                "kind": "agent",
                "id": "claude-code",
                "label": "Claude Code (MCP)",
            },
            "objective": objective,
            "operation": operation,
            "target": {
                "repo": target_repo,
                "ref": target_ref,
                "path": target_path,
            },
            "constraints": {
                "time_budget_seconds": time_budget_seconds,
                "allow_network": False,
                "allow_secrets": False,
            },
            "inputs": {},
            "acceptance_criteria": acceptance_criteria or [],
            "metadata": {},
        }
        if idempotency_key:
            task_data["idempotency_key"] = idempotency_key

        task_spec = TaskCreateV1.model_validate(task_data)

        # Policy evaluation
        try:
            normalized = evaluate_policy(task_spec)
        except PolicyError as e:
            return _error(e.code, e.message)

        # Persist task
        task_service = TaskService(db)
        create_result = task_service.create_task(normalized, trace_id=trace_id)
        db_task = create_result.task

        if not create_result.created:
            return _error(
                "IDEMPOTENCY_CONFLICT",
                f"Task with idempotency_key '{idempotency_key}' already exists.",
                f"Existing task ID: {db_task.id}",
            )

        # Audit
        audit = AuditService(db)
        audit.log_create(
            entity_kind="Task",
            entity_id=str(db_task.id),
            after=db_task.to_dict(),
            actor_kind="agent",
            actor_id="claude-code",
            note="Task created via MCP jct_enqueue_task",
            trace_id=trace_id,
        )

        task_service.update_task_status(str(db_task.id), "queued")

        # Create CWOM objects
        cwom_data = None
        if create_cwom:
            cwom_result = task_to_cwom(task_spec, db)
            db_task.cwom_issue_id = cwom_result.issue.id
            db.commit()
            db.refresh(db_task)

            cwom_data = {
                "repo_id": cwom_result.repo.id,
                "issue_id": cwom_result.issue.id,
                "context_packet_id": cwom_result.context_packet.id,
                "constraint_snapshot_id": cwom_result.constraint_snapshot.id,
            }
        else:
            db.commit()

        result = {
            "task_id": str(db_task.id),
            "trace_id": trace_id,
            "status": "queued",
        }
        if cwom_data:
            result["cwom"] = cwom_data

        return _success(**result)

    except Exception as exc:
        db.rollback()
        return _error("ENQUEUE_TASK_ERROR", str(exc))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the JCT MCP server (stdio transport)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )
    # Re-read settings from current process env (MCP config sets env vars)
    from devops_control_tower.config import reset_settings

    reset_settings()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
