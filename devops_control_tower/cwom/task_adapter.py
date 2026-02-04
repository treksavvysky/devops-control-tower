"""
CWOM v0.1 Task Adapter.

Provides bidirectional conversion between JCT V1 Task system and CWOM objects.
This adapter enables gradual migration from Tasks to CWOM while maintaining
backward compatibility.

Mapping:
    TaskCreateV1 → Repo + Issue + ContextPacket + ConstraintSnapshot
    Issue + ContextPacket + ConstraintSnapshot → TaskCreateV1 (for API compat)
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..schemas.task_v1 import TaskCreateV1, TaskCreateLegacyV1
from .enums import ConstraintScope, IssueType, Priority, Status
from .primitives import (
    Acceptance,
    Actor,
    ActorKind,
    Constraints,
    ObjectKind,
    Ref,
    RiskConstraint,
    Source,
    TimeConstraint,
)
from .repo import RepoCreate
from .issue import IssueCreate
from .context_packet import ContextPacketCreate
from .constraint_snapshot import ConstraintSnapshotCreate
from .services import (
    ConstraintSnapshotService,
    ContextPacketService,
    IssueService,
    RepoService,
)
from ..db.cwom_models import (
    CWOMConstraintSnapshotModel,
    CWOMContextPacketModel,
    CWOMIssueModel,
    CWOMRepoModel,
)


# Operation to IssueType mapping
OPERATION_TO_ISSUE_TYPE = {
    "code_change": IssueType.FEATURE,
    "docs": IssueType.DOC,
    "analysis": IssueType.RESEARCH,
    "ops": IssueType.OPS,
}

# Reverse mapping for issue_to_task
ISSUE_TYPE_TO_OPERATION = {
    IssueType.FEATURE: "code_change",
    IssueType.BUG: "code_change",  # Bugs are still code changes
    IssueType.DOC: "docs",
    IssueType.RESEARCH: "analysis",
    IssueType.OPS: "ops",
    IssueType.CHORE: "ops",  # Chores map to ops
    IssueType.INCIDENT: "ops",  # Incidents map to ops
}


@dataclass
class CWOMObjects:
    """Container for CWOM objects created from a Task."""

    repo: CWOMRepoModel
    issue: CWOMIssueModel
    context_packet: CWOMContextPacketModel
    constraint_snapshot: CWOMConstraintSnapshotModel


def task_to_cwom(
    task: TaskCreateV1 | TaskCreateLegacyV1,
    db: Session,
) -> CWOMObjects:
    """
    Convert a JCT V1 Task to CWOM objects.

    Creates or retrieves:
    - Repo (get-or-create by slug from target.repo)
    - Issue (linked to Repo)
    - ContextPacket (linked to Issue, contains inputs)
    - ConstraintSnapshot (contains task constraints)

    Args:
        task: The task specification to convert
        db: Database session for persistence

    Returns:
        CWOMObjects containing all created/retrieved objects
    """
    # Normalize legacy task to canonical format
    if isinstance(task, TaskCreateLegacyV1):
        task_data = task.model_dump(exclude_none=True)
        # Ensure operation is set (legacy uses 'type')
        if "operation" not in task_data and "type" in task_data:
            task_data["operation"] = task_data.pop("type")
        # Ensure inputs is set (legacy uses 'payload')
        if "inputs" not in task_data and "payload" in task_data:
            task_data["inputs"] = task_data.pop("payload")
    else:
        task_data = task.model_dump()

    # Extract target info
    target = task_data.get("target", {})
    repo_slug = target.get("repo", "")
    repo_ref = target.get("ref", "main")
    repo_path = target.get("path", "")

    # Create Actor from requested_by
    requested_by = task_data.get("requested_by", {})
    actor = Actor(
        actor_kind=ActorKind(requested_by.get("kind", "human")),
        actor_id=requested_by.get("id", "unknown"),
        display=requested_by.get("label"),
    )

    # 1. Get or create Repo
    repo_service = RepoService(db)
    repo = repo_service.get_by_slug(repo_slug)

    if not repo:
        # Create new repo
        # Derive name from slug (e.g., "myorg/my-repo" -> "my-repo")
        repo_name = repo_slug.split("/")[-1] if "/" in repo_slug else repo_slug

        repo_create = RepoCreate(
            name=repo_name,
            slug=repo_slug,
            source=Source(
                system="jct",  # Created via JCT task system
                external_id=repo_slug,
            ),
            default_branch=repo_ref,
        )
        repo = repo_service.create(repo_create)

    # 2. Create ConstraintSnapshot
    constraints_data = task_data.get("constraints", {})
    constraint_service = ConstraintSnapshotService(db)

    # Build properly typed constraint objects
    time_budget = constraints_data.get("time_budget_seconds", 900)
    time_constraint = TimeConstraint(available_minutes=time_budget // 60) if time_budget else None

    # Map allow_network/allow_secrets to risk tolerance
    allow_network = constraints_data.get("allow_network", False)
    allow_secrets = constraints_data.get("allow_secrets", False)
    # Low tolerance = no network/secrets, high = both allowed
    risk_tolerance = "high" if (allow_network and allow_secrets) else "medium" if (allow_network or allow_secrets) else "low"
    risk_constraint = RiskConstraint(
        tolerance=risk_tolerance,
        notes=f"allow_network={allow_network}, allow_secrets={allow_secrets}",
    )

    constraint_create = ConstraintSnapshotCreate(
        scope=ConstraintScope.RUN,
        owner=actor,
        constraints=Constraints(
            time=time_constraint,
            risk=risk_constraint,
        ),
        meta={
            "source": "jct_task",
            "idempotency_key": task_data.get("idempotency_key"),
            "time_budget_seconds": time_budget,
            "allow_network": allow_network,
            "allow_secrets": allow_secrets,
        },
    )
    constraint_snapshot = constraint_service.create(constraint_create)

    # 3. Create Issue
    issue_service = IssueService(db)

    operation = task_data.get("operation", "code_change")
    issue_type = OPERATION_TO_ISSUE_TYPE.get(operation, IssueType.FEATURE)

    # Build title from objective (first line or truncated)
    objective = task_data.get("objective", "")
    title = objective.split("\n")[0][:200] if objective else "Untitled Task"

    # Build acceptance criteria - use explicit criteria if provided, else use objective
    acceptance_criteria = task_data.get("acceptance_criteria", [])
    if not acceptance_criteria and objective:
        acceptance_criteria = [objective]

    # Build evidence requirements
    evidence_requirements = task_data.get("evidence_requirements", [])

    issue_create = IssueCreate(
        repo=Ref(kind=ObjectKind.REPO, id=repo.id),
        title=title,
        description=objective,
        type=issue_type,
        priority=Priority.P2,  # Default priority
        status=Status.PLANNED,
        assignees=[actor],
        acceptance=Acceptance(
            criteria=acceptance_criteria,
        ),
        meta={
            "source": "jct_task",
            "idempotency_key": task_data.get("idempotency_key"),
            "task_metadata": task_data.get("metadata", {}),
            "evidence_requirements": evidence_requirements,
        },
    )
    issue = issue_service.create(issue_create)

    # Link constraint snapshot to issue
    issue_service.link_constraint_snapshot(issue.id, constraint_snapshot.id)

    # 4. Create ContextPacket
    context_service = ContextPacketService(db)

    # Task inputs go to meta, not inputs (ContextInputs only accepts documents/data_blobs/links)
    inputs_data = task_data.get("inputs", {})

    context_create = ContextPacketCreate(
        for_issue=Ref(kind=ObjectKind.ISSUE, id=issue.id),
        version="1.0",
        summary=f"Initial context from JCT task",
        # ContextInputs is for documents/blobs - leave empty, use meta for task inputs
        assumptions=[
            f"Target branch: {repo_ref}",
            f"Working path: {repo_path or '(root)'}",
        ],
        instructions=objective,
        constraint_snapshot=Ref(kind=ObjectKind.CONSTRAINT_SNAPSHOT, id=constraint_snapshot.id),
        meta={
            "source": "jct_task",
            "idempotency_key": task_data.get("idempotency_key"),
            "acceptance_criteria": acceptance_criteria,
            "evidence_requirements": evidence_requirements,
            # Store task target/inputs in meta for round-trip
            "task_ref": repo_ref,
            "task_path": repo_path,
            "task_inputs": inputs_data,
        },
    )
    context_packet = context_service.create(context_create)

    # Link context packet to issue
    issue_service.link_context_packet(issue.id, context_packet.id)

    return CWOMObjects(
        repo=repo,
        issue=issue,
        context_packet=context_packet,
        constraint_snapshot=constraint_snapshot,
    )


def issue_to_task(
    issue: CWOMIssueModel,
    context_packet: Optional[CWOMContextPacketModel] = None,
    constraint_snapshot: Optional[CWOMConstraintSnapshotModel] = None,
    repo: Optional[CWOMRepoModel] = None,
) -> Dict[str, Any]:
    """
    Convert CWOM Issue (with related objects) back to JCT V1 Task format.

    This provides backward compatibility for clients expecting Task format.

    Args:
        issue: The CWOM Issue
        context_packet: Optional ContextPacket for inputs
        constraint_snapshot: Optional ConstraintSnapshot for constraints
        repo: Optional Repo for target info

    Returns:
        Dictionary in TaskCreateV1 format
    """
    # Map issue type to operation
    issue_type = IssueType(issue.type) if isinstance(issue.type, str) else issue.type
    operation = ISSUE_TYPE_TO_OPERATION.get(issue_type, "code_change")

    # Build requested_by from issue assignees or meta
    requested_by = {"kind": "system", "id": "cwom", "label": "CWOM System"}
    if issue.assignees and len(issue.assignees) > 0:
        assignee = issue.assignees[0]
        if isinstance(assignee, dict):
            requested_by = {
                "kind": assignee.get("actor_kind", "human"),
                "id": assignee.get("actor_id", "unknown"),
                "label": assignee.get("display"),
            }

    # Build target from repo
    target = {
        "repo": repo.slug if repo else issue.repo_id,
        "ref": "main",
        "path": "",
    }

    # Override with context packet meta if available (task inputs stored in meta)
    if context_packet and context_packet.meta:
        meta = context_packet.meta
        if isinstance(meta, dict):
            target["ref"] = meta.get("task_ref", target["ref"])
            target["path"] = meta.get("task_path", target["path"])

    # Build constraints from constraint snapshot
    constraints = {
        "time_budget_seconds": 900,
        "allow_network": False,
        "allow_secrets": False,
    }
    if constraint_snapshot:
        # First check meta for original task values (most accurate)
        if constraint_snapshot.meta and isinstance(constraint_snapshot.meta, dict):
            meta = constraint_snapshot.meta
            if "time_budget_seconds" in meta:
                constraints["time_budget_seconds"] = meta["time_budget_seconds"]
            if "allow_network" in meta:
                constraints["allow_network"] = meta["allow_network"]
            if "allow_secrets" in meta:
                constraints["allow_secrets"] = meta["allow_secrets"]
        # Fallback to constraints object if meta not available
        elif constraint_snapshot.constraints and isinstance(constraint_snapshot.constraints, dict):
            cs = constraint_snapshot.constraints
            if "time" in cs and cs["time"]:
                available_minutes = cs["time"].get("available_minutes", 15)
                constraints["time_budget_seconds"] = available_minutes * 60
            if "risk" in cs and cs["risk"]:
                tolerance = cs["risk"].get("tolerance", "low")
                constraints["allow_network"] = tolerance in ("medium", "high")
                constraints["allow_secrets"] = tolerance == "high"

    # Build inputs from context packet meta (task_inputs stored there)
    inputs = {}
    if context_packet and context_packet.meta:
        cp_meta = context_packet.meta
        if isinstance(cp_meta, dict):
            inputs = cp_meta.get("task_inputs", {})

    # Build metadata from issue meta
    metadata = {}
    acceptance_criteria = []
    evidence_requirements = []
    if issue.meta:
        meta = issue.meta
        if isinstance(meta, dict):
            # Extract task_metadata if it was stored there
            metadata = meta.get("task_metadata", {})
            evidence_requirements = meta.get("evidence_requirements", [])

    # Extract acceptance criteria from issue.acceptance
    if issue.acceptance:
        acceptance_data = issue.acceptance
        if isinstance(acceptance_data, dict):
            acceptance_criteria = acceptance_data.get("criteria", [])

    return {
        "version": "1.0",
        "idempotency_key": issue.meta.get("idempotency_key") if isinstance(issue.meta, dict) else None,
        "requested_by": requested_by,
        "objective": issue.description or issue.title,
        "operation": operation,
        "target": target,
        "constraints": constraints,
        "inputs": inputs,
        "acceptance_criteria": acceptance_criteria,
        "evidence_requirements": evidence_requirements,
        "metadata": metadata,
    }
