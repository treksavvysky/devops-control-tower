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
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger(__name__)

server = FastMCP(
    name="jct",
    instructions=(
        "Jules Control Tower: AI-assisted development operations. "
        "Claim tasks from the queue, read context and constraints, "
        "execute work, report artifacts, and complete tasks. "
        "All operations are audited with full causality tracking."
    ),
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
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


EXECUTOR_TYPE = "mcp_agent"
EXECUTOR_VERSION = "0.2.0"


def _actor_id() -> Optional[str]:
    """Identity this MCP server acts for (JCT_ACTOR_ID), or None if unset."""
    from devops_control_tower.config import get_settings

    actor = (get_settings().jct_actor_id or "").strip()
    return actor or None


def _actor_missing_error() -> str:
    return _error(
        "ACTOR_NOT_CONFIGURED",
        "This JCT MCP server has no executor identity (JCT_ACTOR_ID is unset).",
        "Set JCT_ACTOR_ID in the MCP server's environment, e.g. Claude@codejourney.",
    )


def _executor_record(actor: str) -> Dict[str, Any]:
    return {"type": EXECUTOR_TYPE, "version": EXECUTOR_VERSION, "worker_id": actor}


def _process_expired_leases(db) -> dict:
    """Process expired claims (hold, or requeue on confirmed termination).

    Never lets the reaper break the calling tool. No termination confirmer is
    available in the MCP server, so expired claims are held (DEVOPS-CON-11).
    """
    from devops_control_tower.worker.leases import process_expired_leases

    try:
        return process_expired_leases(db, actor_id="lease-reaper:mcp")
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        logger.warning("Lease reaper failed: %s", exc)
        return {"held": [], "requeued": []}


def _claim_token(task_id: str, actor: str, claim_generation):
    """The caller's claim token. ``claim_generation`` is required (review C3).

    The request itself must say which claim attempt it acts for. We never
    substitute a cached or stored generation: a delayed call from an older
    attempt would otherwise act on the newest one.
    """
    from devops_control_tower.lifecycle import ClaimToken

    if claim_generation is None:
        return None, _error(
            "CLAIM_TOKEN_REQUIRED",
            f"claim_generation is required for task '{task_id}'.",
            "Pass the claim_generation returned by jct_claim_task.",
        )
    try:
        gen = int(claim_generation)
    except (TypeError, ValueError):
        return None, _error(
            "CLAIM_TOKEN_REQUIRED", "claim_generation must be an integer."
        )
    return ClaimToken(task_id=str(task_id), actor=actor, generation=gen), None


def _lifecycle_error(exc) -> str:
    return _error(exc.code, exc.message, "Use jct_list_tasks and claim the task again.")


# ---------------------------------------------------------------------------
# In-memory state for active claims
# ---------------------------------------------------------------------------

# Maps task_id -> {"run_id", "trace_uri", "store"}
_active_claims: Dict[str, Dict[str, Any]] = {}


def _get_active_claim(task_id: str, generation: int, db=None):
    """The run and trace store of exactly this claim attempt.

    The in-memory entry is used only if it is for the same generation;
    otherwise (e.g. after a restart) the run is found by (task_id,
    claim_generation), never "the first running run on the issue" (review N2).
    """
    cached = _active_claims.get(task_id)
    if cached and cached.get("claim_generation") == generation:
        return cached

    if db is None:
        return None

    from devops_control_tower.config import get_settings
    from devops_control_tower.lifecycle import attempt_runs
    from devops_control_tower.worker.storage import create_trace_store

    runs = attempt_runs(db, str(task_id), generation)
    if not runs:
        return None
    run = runs[0]
    store = create_trace_store(get_settings().jct_trace_root, run.id)
    return {
        "run_id": run.id,
        "trace_uri": run.artifact_root_uri or store.get_uri(),
        "store": store,
        "claim_generation": generation,
    }


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

        _process_expired_leases(db)

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

        actor = _actor_id()
        if not actor:
            return _actor_missing_error()

        _process_expired_leases(db)

        from devops_control_tower.lifecycle import claim as lifecycle_claim
        from devops_control_tower.worker.leases import lease_expiry

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

        # Atomic claim through the lifecycle module: queued → running, new
        # claim generation, lease (DEVOPS-CON-11)
        now = datetime.now(timezone.utc)
        lease_expires_at = lease_expiry(task.time_budget_seconds, now)
        # The claim, its run and the issue status commit together (review C4):
        # a hold can't land between the claim and the attempt's registration.
        token = lifecycle_claim(db, str(task.id), actor, lease_expires_at, now)
        if token is None:  # nothing was written; the session is closed below
            return _error(
                "TASK_ALREADY_CLAIMED",
                f"Task '{task_id}' was claimed by another worker.",
                "Use jct_list_tasks to find another available task.",
            )

        db.refresh(task)

        # Create CWOM Run if task has linked issue
        run_id = None
        context_packet_data = None
        constraint_snapshot_data = None
        issue_data = None
        issue = None

        if task.cwom_issue_id:
            issue = (
                db.query(CWOMIssueModel)
                .filter(CWOMIssueModel.id == task.cwom_issue_id)
                .first()
            )

            if issue:
                run_id = str(uuid.uuid4())
                trace_uri = get_trace_uri(settings.jct_trace_root, run_id)

                run = CWOMRunModel(
                    id=run_id,
                    kind="Run",
                    trace_id=task.trace_id,
                    for_issue_id=issue.id,
                    for_issue_kind="Issue",
                    repo_id=issue.repo_id,
                    repo_kind="Repo",
                    task_id=str(task.id),
                    claim_generation=token.generation,
                    status="running",
                    mode="agent",
                    executor=_executor_record(actor),
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

                audit = AuditService(db, commit=False)
                audit.log_create(
                    entity_kind="Run",
                    entity_id=run_id,
                    after=run.to_dict(),
                    actor_kind="agent",
                    actor_id=actor,
                    note=f"Run created via MCP for task {task.id}",
                    trace_id=task.trace_id,
                )

        db.commit()  # claim + run + issue + audit, one transaction

        if issue is not None:
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
                .filter(CWOMContextPacketModel.for_issue_id == issue.id)
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
                "claim_generation": token.generation,
            }

            # Write initial manifest
            store.write_json(
                "manifest.json",
                {
                    "version": "1.0",
                    "task_id": str(task.id),
                    "run_id": run_id,
                    "trace_id": task.trace_id,
                    "executor": _executor_record(actor),
                    "started_at": now.isoformat(),
                    "lease_expires_at": lease_expires_at.isoformat(),
                    "status": "running",
                },
            )

        return _success(
            task_id=str(task.id),
            run_id=run_id,
            trace_id=task.trace_id,
            executor=actor,
            claim_generation=token.generation,
            lease_expires_at=lease_expires_at.isoformat(),
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
                    .filter(CWOMContextPacketModel.for_issue_id == issue.id)
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
                    result["doctrine_refs"] = [d.to_dict() for d in issue.doctrine_refs]

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
    claim_generation: Optional[int] = None,
) -> str:
    """Report an artifact produced during execution.

    Requires ``claim_generation`` and a live claim (this actor, this
    generation, lease not expired). The claim is fenced (row write-locked)
    before anything is written, and the artifact record commits in that same
    transaction, so a concurrent hold either precedes it (refused) or follows
    it (review C4). Content goes to a content-addressed path, so a refused or
    failed write can never overwrite another artifact's bytes.
    """
    # Validate artifact_type against the CWOM enum
    from devops_control_tower.cwom.enums import ArtifactType

    valid_types = [e.value for e in ArtifactType]
    if artifact_type not in valid_types:
        return _error(
            "INVALID_ARTIFACT_TYPE",
            f"'{artifact_type}' is not a valid artifact type. "
            f"Valid types: {', '.join(valid_types)}",
        )

    actor = _actor_id()
    if not actor:
        return _actor_missing_error()

    db = _get_db()
    try:
        import hashlib

        from devops_control_tower.db.audit_service import AuditService
        from devops_control_tower.db.cwom_models import CWOMArtifactModel
        from devops_control_tower.db.models import TaskModel

        _process_expired_leases(db)

        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return _error("TASK_NOT_FOUND", f"Task '{task_id}' not found.")

        if task.status != "running":
            return _error(
                "TASK_NOT_RUNNING",
                f"Task '{task_id}' is not running (current status: {task.status}).",
            )
        token, token_error = _claim_token(task_id, actor, claim_generation)
        if token_error:
            return token_error
        from devops_control_tower.lifecycle import LifecycleError, fence

        try:
            fence(db, token)  # holds the claim until this transaction commits
        except LifecycleError as exc:
            return _lifecycle_error(exc)  # nothing written; session closed below

        claim = _get_active_claim(task_id, token.generation, db)
        if not claim:
            return _error(
                "NO_ACTIVE_CLAIM",
                f"No run found for claim generation {token.generation} "
                f"of task '{task_id}'.",
                "Use jct_claim_task first.",
            )

        run_id = claim["run_id"]
        store = claim.get("store")

        # Digest the exact bytes recorded (G5); URI-only artifacts stay undigested
        digest = None
        size_bytes = None
        if content is not None:
            content_bytes = content.encode("utf-8")
            digest = "sha256:" + hashlib.sha256(content_bytes).hexdigest()
            size_bytes = len(content_bytes)

        # Write content to trace store
        artifact_uri = uri
        if content and store:
            safe_title = title.lower().replace(" ", "_").replace("/", "_")[:50]
            # content-addressed: same bytes → same path; never overwrites others
            artifact_path = f"artifacts/{digest.split(':', 1)[1][:16]}-{safe_title}"
            store.write_text(artifact_path, content)
            artifact_uri = f"{store.get_uri()}/{artifact_path}"
            store.append_event(
                {
                    "event": "artifact_reported",
                    "title": title,
                    "type": artifact_type,
                    "path": artifact_path,
                    "digest": digest,
                    "size_bytes": size_bytes,
                    "actor": actor,
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
            digest=digest,
            size_bytes=size_bytes,
        )
        db.add(artifact)

        audit = AuditService(db, commit=False)
        audit.log_create(
            entity_kind="Artifact",
            entity_id=artifact_id,
            after=artifact.to_dict(),
            actor_kind="agent",
            actor_id=actor,
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
            digest=digest,
            size_bytes=size_bytes,
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
    claim_generation: Optional[int] = None,
) -> str:
    """Complete a claimed task and trigger prove/review.

    Requires ``claim_generation``. Two explicit stages (review C1):

    1. **Accept the result**, in one transaction: the task transition (this
       actor, this generation, running, lease not expired), this attempt's
       run and issue, and the audit entries. Nothing is written if the claim
       isn't live, even if no lease reaper ran.
    2. **Prove and review**, in one transaction. If it fails, the run stays
       ``proof_status="pending"`` and ``recover_pending_proofs`` retries it.
    """
    actor = _actor_id()
    if not actor:
        return _actor_missing_error()

    db = _get_db()
    try:
        from devops_control_tower.db.audit_service import AuditService
        from devops_control_tower.db.cwom_models import (
            CWOMArtifactModel,
            CWOMIssueModel,
        )
        from devops_control_tower.db.models import TaskModel
        from devops_control_tower.lifecycle import LifecycleError, attempt_runs, finish
        from devops_control_tower.worker.pipeline import PROOF_PENDING, complete_proof

        _process_expired_leases(db)

        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not task:
            return _error("TASK_NOT_FOUND", f"Task '{task_id}' not found.")
        if task.status != "running":
            return _error(
                "TASK_NOT_RUNNING",
                f"Task '{task_id}' is not running (current status: {task.status}).",
            )
        token, token_error = _claim_token(task_id, actor, claim_generation)
        if token_error:
            return token_error

        now = datetime.now(timezone.utc)
        outputs_dict: Dict[str, Any] = {}
        if outputs:
            try:
                outputs_dict = json.loads(outputs)
            except json.JSONDecodeError:
                outputs_dict = {"raw": outputs}
        outputs_dict["summary"] = summary

        claim = _get_active_claim(task_id, token.generation, db)
        store = claim.get("store") if claim else None

        # ---- Stage 1: accept the result (one transaction) ----
        try:
            finish(
                db,
                token,
                success,
                result=outputs_dict,
                error=error_message if (not success and error_message) else None,
                trace_path=store.get_uri() if store else None,
                now=now,
            )
        except LifecycleError as exc:
            return _lifecycle_error(exc)  # nothing written; session closed below

        response: Dict[str, Any] = {
            "task_id": str(task.id),
            "task_status": "completed" if success else "failed",
            "claim_generation": token.generation,
        }
        runs = attempt_runs(db, str(task_id), token.generation, ["running"])
        run = runs[0] if runs else None
        if run is not None:
            run.status = "done" if success else "failed"
            run.outputs = outputs_dict
            run.proof_status = PROOF_PENDING
            if not success:
                run.failure = {
                    "code": "AGENT_REPORTED_FAILURE",
                    "message": error_message or summary,
                }
            issue = (
                db.query(CWOMIssueModel)
                .filter(CWOMIssueModel.id == run.for_issue_id)
                .first()
            )
            if issue:
                issue.status = "done" if success else "failed"
            AuditService(db, commit=False).log_status_change(
                entity_kind="Run",
                entity_id=run.id,
                old_status="running",
                new_status=run.status,
                actor_kind="agent",
                actor_id=actor,
                note=summary,
                trace_id=task.trace_id,
            )
        db.commit()
        _active_claims.pop(task_id, None)
        db.refresh(task)

        if run is None:
            return _success(**response)
        run_id = run.id
        response["run_id"] = run_id
        response["run_status"] = run.status

        # Final manifest, written after the result was accepted
        if store:
            run_artifacts = (
                db.query(CWOMArtifactModel)
                .filter(CWOMArtifactModel.produced_by_id == run_id)
                .all()
            )
            store.write_json(
                "manifest.json",
                {
                    "version": "1.1",
                    "task_id": str(task.id),
                    "run_id": run_id,
                    "claim_generation": token.generation,
                    "trace_id": task.trace_id,
                    "executor": _executor_record(actor),
                    "started_at": task.started_at.isoformat()
                    if task.started_at
                    else None,
                    "completed_at": now.isoformat(),
                    "status": "completed" if success else "failed",
                    "result": outputs_dict,
                    "artifacts": [
                        {
                            "id": a.id,
                            "title": a.title,
                            "uri": a.uri,
                            "digest": a.digest,
                            "size_bytes": a.size_bytes,
                        }
                        for a in run_artifacts
                    ],
                },
            )

        # ---- Stage 2: prove and review (one transaction, recoverable) ----
        try:
            proof = complete_proof(
                db,
                run,
                task,
                store,
                prover_id="claude-code-mcp",
                actor_id=actor,
                review=success,
            )
            evidence_pack = proof["evidence_pack"]
            response["evidence_pack"] = {
                "id": evidence_pack.id,
                "verdict": evidence_pack.verdict,
                "verdict_reason": evidence_pack.verdict_reason,
            }
            if "review" in proof:
                response["review"] = proof["review"]
            db.refresh(run)
            response["run_status"] = run.status
        except Exception as prove_exc:
            logger.warning("Prove/review failed for run %s: %s", run_id, prove_exc)
            response["prove_error"] = str(prove_exc)
            response["proof_status"] = PROOF_PENDING

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
        from devops_control_tower.cwom.services import EvidencePackService
        from devops_control_tower.db.cwom_models import CWOMRunModel

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
        from devops_control_tower.worker.eligibility import production_eligibility

        return _success(
            evidence_pack=ep.to_dict(),
            production_eligibility=production_eligibility(db, ep),
        )
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
    reviewer_name: Optional[str] = None,
) -> str:
    """Submit a review decision for an evidence pack.

    The reviewer identity is this server's JCT_ACTOR_ID, not a parameter:
    `reviewer_name` is a display label only. A reviewer who executed the run
    is refused (no self-review).
    """
    actor = _actor_id()
    if not actor:
        return _actor_missing_error()

    db = _get_db()
    try:
        from devops_control_tower.cwom.services import (
            EvidencePackService,
            ReviewDecisionService,
            SelfReviewError,
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
                "actor_id": actor,
                "display": reviewer_name or actor,
            },
            "decision": decision,
            "decision_reason": reason,
            "tags": ["mcp-review"],
        }

        review_svc = ReviewDecisionService(db)
        try:
            review = review_svc.create(
                review_data=review_data,
                actor_kind="agent",
                actor_id=actor,
            )
        except SelfReviewError as exc:
            # Raised before anything is written, so there is nothing to roll back
            return _error("SELF_REVIEW_FORBIDDEN", str(exc))

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
    operation: Optional[str] = None,
    type: Optional[str] = None,
    target_repo: Optional[str] = None,
    repo: Optional[str] = None,
    target_ref: str = "main",
    ref: Optional[str] = None,
    target_path: str = "",
    path: Optional[str] = None,
    target: Optional[Dict[str, Any]] = None,
    time_budget_seconds: int = 3600,
    priority: str = "P2",
    acceptance_criteria: Optional[List[str]] = None,
    context_summary: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    create_cwom: bool = True,
    **kwargs,
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

        # Resolve operation
        actual_operation = (
            operation or type or kwargs.get("operation") or kwargs.get("type")
        )
        if not actual_operation:
            return _error(
                "INVALID_PARAMETERS", "Either 'operation' or 'type' must be provided."
            )

        # Resolve target repo, ref, path
        actual_repo = (
            target_repo or repo or kwargs.get("repo") or kwargs.get("target_repo")
        )
        actual_ref = (
            target_ref or ref or kwargs.get("ref") or kwargs.get("target_ref") or "main"
        )
        actual_path = (
            target_path or path or kwargs.get("path") or kwargs.get("target_path") or ""
        )

        if isinstance(target, dict):
            actual_repo = actual_repo or target.get("repo") or target.get("repository")
            actual_ref = actual_ref or target.get("ref") or actual_ref
            actual_path = actual_path or target.get("path") or actual_path

        if not actual_repo:
            return _error(
                "INVALID_PARAMETERS",
                "Either 'target_repo', 'repo', or 'target.repo' must be provided.",
            )

        # Resolve constraints
        constraints_dict = kwargs.get("constraints")
        if isinstance(constraints_dict, dict):
            time_budget_seconds = (
                constraints_dict.get("time_budget_seconds") or time_budget_seconds
            )

        # Build task spec
        task_data = {
            "version": "1.0",
            "requested_by": {
                "kind": "agent",
                "id": _actor_id() or "unidentified-mcp-client",
                "label": "JCT MCP client",
            },
            "objective": objective,
            "operation": actual_operation,
            "target": {
                "repo": actual_repo,
                "ref": actual_ref,
                "path": actual_path,
            },
            "constraints": {
                "time_budget_seconds": time_budget_seconds,
                "allow_network": False,
                "allow_secrets": False,
            },
            "inputs": kwargs.get("inputs") or kwargs.get("payload") or {},
            "acceptance_criteria": acceptance_criteria
            or kwargs.get("acceptance_criteria")
            or [],
            "metadata": kwargs.get("metadata") or {},
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
            actor_id=_actor_id() or "unidentified-mcp-client",
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
