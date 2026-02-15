"""
Shared pipeline functions for prove and review steps.

Used by both WorkerLoop (poll-based executor) and MCP server (agent-based executor).
Extracted from loop.py to avoid duplication.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.audit_service import AuditService
from ..db.cwom_models import CWOMEvidencePackModel, CWOMIssueModel, CWOMRunModel
from ..db.models import TaskModel
from .prover import Prover
from .storage import TraceStore

logger = logging.getLogger(__name__)


def run_prove(
    db: Session,
    run: CWOMRunModel,
    task: TaskModel,
    store: Optional[TraceStore] = None,
    prover_id: str = "prover-v0",
) -> CWOMEvidencePackModel:
    """Run the prover and create an EvidencePack.

    Args:
        db: Database session (artifacts must be committed before calling)
        run: The CWOM Run to evaluate
        task: The Task associated with this run
        store: Optional TraceStore for writing evidence files
        prover_id: Identifier for this prover instance

    Returns:
        CWOMEvidencePackModel with verdict and evidence
    """
    prover = Prover(prover_id=prover_id)
    evidence_pack = prover.prove(
        db=db,
        run=run,
        task=task,
        trace_store=store,
    )
    logger.info(
        f"Evidence pack {evidence_pack.id} created with verdict: "
        f"{evidence_pack.verdict}"
    )
    return evidence_pack


def apply_review_policy(
    db: Session,
    task: TaskModel,
    run: CWOMRunModel,
    evidence_pack: CWOMEvidencePackModel,
    actor_id: str = "worker",
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply review policy after prove.

    Auto-approve path: create ReviewDecision(approved), leave done.
    Manual review path: transition Run/Issue to under_review.

    Args:
        db: Database session
        task: The completed task
        run: The CWOM Run
        evidence_pack: The evidence pack from prove step
        actor_id: ID of the actor applying the policy
        trace_id: Trace ID for audit logging

    Returns:
        Dict with keys:
        - status: "auto_approved" | "awaiting_manual_review"
        - review_id: (if auto-approved) ID of the ReviewDecision
        - message: Human-readable status message
    """
    settings = get_settings()
    auto_approve = settings.jct_review_auto_approve
    allowed_verdicts = [
        v.strip()
        for v in settings.jct_review_auto_approve_verdicts.split(",")
    ]
    verdict_qualifies = evidence_pack.verdict in allowed_verdicts
    _trace_id = trace_id or task.trace_id

    if auto_approve and verdict_qualifies:
        from ..cwom.services import ReviewDecisionService

        review_service = ReviewDecisionService(db)
        review_data = {
            "for_evidence_pack": {
                "kind": "EvidencePack",
                "id": evidence_pack.id,
            },
            "for_run": {"kind": "Run", "id": run.id},
            "for_issue": {"kind": "Issue", "id": run.for_issue_id},
            "reviewer": {
                "actor_kind": "system",
                "actor_id": "auto-approve",
                "display": "Automatic Review (Policy-Based)",
            },
            "decision": "approved",
            "decision_reason": (
                f"Auto-approved: verdict={evidence_pack.verdict}"
            ),
            "tags": ["auto-approved", "v0"],
        }

        # Issue must be under_review for service.create to work
        issue = (
            db.query(CWOMIssueModel)
            .filter(CWOMIssueModel.id == run.for_issue_id)
            .first()
        )
        if issue:
            issue.status = "under_review"
            run.status = "under_review"
            db.flush()

        review = review_service.create(
            review_data=review_data,
            actor_kind="system",
            actor_id=actor_id,
            trace_id=_trace_id,
        )
        logger.info(
            f"Auto-approved: review {review.id} for evidence pack "
            f"{evidence_pack.id}"
        )
        return {
            "status": "auto_approved",
            "review_id": review.id,
            "message": f"Auto-approved with verdict={evidence_pack.verdict}",
        }
    else:
        # Manual review: transition Run/Issue to under_review
        logger.info(
            f"Evidence pack {evidence_pack.id} requires manual review "
            f"(verdict: {evidence_pack.verdict})"
        )

        issue = (
            db.query(CWOMIssueModel)
            .filter(CWOMIssueModel.id == run.for_issue_id)
            .first()
        )

        old_run_status = run.status
        run.status = "under_review"
        run.updated_at = datetime.now(timezone.utc)

        audit = AuditService(db)
        audit.log_status_change(
            entity_kind="Run",
            entity_id=run.id,
            old_status=old_run_status,
            new_status="under_review",
            actor_kind="system",
            actor_id=actor_id,
            note="Awaiting manual review",
            trace_id=_trace_id,
        )

        if issue:
            old_issue_status = issue.status
            issue.status = "under_review"
            issue.updated_at = datetime.now(timezone.utc)

            audit.log_status_change(
                entity_kind="Issue",
                entity_id=issue.id,
                old_status=old_issue_status,
                new_status="under_review",
                actor_kind="system",
                actor_id=actor_id,
                note="Awaiting manual review",
                trace_id=_trace_id,
            )

        logger.info(
            f"Run {run.id} and Issue "
            f"{issue.id if issue else 'N/A'} set to under_review"
        )
        return {
            "status": "awaiting_manual_review",
            "message": (
                f"Verdict={evidence_pack.verdict} requires manual review. "
                f"Use POST /cwom/reviews or jct_submit_review to decide."
            ),
        }
