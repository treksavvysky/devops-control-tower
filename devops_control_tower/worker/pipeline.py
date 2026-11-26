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
    commit: bool = True,
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
    existing = (
        db.query(CWOMEvidencePackModel)
        .filter(CWOMEvidencePackModel.for_run_id == run.id)
        .first()
    )
    if existing is not None:  # idempotent: one evidence pack per run
        return existing
    prover = Prover(prover_id=prover_id)
    evidence_pack = prover.prove(
        db=db,
        run=run,
        task=task,
        trace_store=store,
        commit=commit,
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
    """Apply review policy after prove. Does not commit (caller's transaction).

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
        v.strip() for v in settings.jct_review_auto_approve_verdicts.split(",")
    ]
    verdict_qualifies = evidence_pack.verdict in allowed_verdicts

    from .eligibility import evidence_is_experimental

    if evidence_is_experimental(evidence_pack):
        # Experimental runs are never auto-approved (DEVOPS-CON-11).
        auto_approve = False
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
            "decision_reason": (f"Auto-approved: verdict={evidence_pack.verdict}"),
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
            commit=False,
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

        audit = AuditService(db, commit=False)
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


PROOF_PENDING = "pending"
PROOF_DONE = "done"


def complete_proof(
    db: Session,
    run: CWOMRunModel,
    task: TaskModel,
    store: Optional[TraceStore],
    prover_id: str,
    actor_id: str,
    review: bool,
) -> Dict[str, Any]:
    """The proof stage after a result was accepted: one transaction.

    Evidence pack, review policy and ``run.proof_status = "done"`` commit
    together. On any error everything is rolled back and the run stays
    ``proof_status = "pending"`` for :func:`recover_pending_proofs`
    (review C1: an explicit, recoverable stage instead of a partial commit).
    """
    try:
        evidence_pack = run_prove(
            db=db, run=run, task=task, store=store, prover_id=prover_id, commit=False
        )
        out: Dict[str, Any] = {"evidence_pack": evidence_pack}
        if review:
            out["review"] = apply_review_policy(
                db=db,
                task=task,
                run=run,
                evidence_pack=evidence_pack,
                actor_id=actor_id,
                trace_id=task.trace_id,
            )
        run.proof_status = PROOF_DONE
        db.commit()
        return out
    except Exception:
        db.rollback()
        raise


def recover_pending_proofs(db: Session, actor_id: str = "proof-recovery") -> list:
    """Retry the proof stage for accepted results whose proof didn't commit.

    Idempotent. Only runs bound to a finished task of the same claim
    generation are proved; review policy applies only to successful results.
    Returns the run IDs proved.
    """
    from ..config import get_settings
    from .storage import create_trace_store

    done = []
    pending = (
        db.query(CWOMRunModel).filter(CWOMRunModel.proof_status == PROOF_PENDING).all()
    )
    for run in pending:
        task = (
            db.query(TaskModel).filter(TaskModel.id == run.task_id).first()
            if run.task_id
            else None
        )
        if (
            task is None
            or task.status not in ("completed", "failed")
            or (task.claim_generation or 0) != run.claim_generation
        ):
            continue
        try:
            store = create_trace_store(get_settings().jct_trace_root, run.id)
            complete_proof(
                db,
                run,
                task,
                store,
                prover_id=actor_id,
                actor_id=actor_id,
                review=task.status == "completed" and run.status == "done",
            )
            done.append(run.id)
        except Exception as exc:
            logger.warning("Proof recovery failed for run %s: %s", run.id, exc)
    return done
