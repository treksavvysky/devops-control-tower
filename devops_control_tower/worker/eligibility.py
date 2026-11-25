"""
Experimental runs and production eligibility (DEVOPS-CON-11).

Fluxion owns acceptance. DCT's job is to make sure the evidence it hands to an
acceptance decision is labelled honestly. A run of an *experimental* task
(admitted only with an authorized experiment ID, see policy.task_gate) can
never be production-eligible evidence, whatever its verdict or review.

Production-eligible evidence = not experimental AND verdict "pass" AND an
"approved" ReviewDecision by a reviewer other than the run's executor.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

EXPERIMENTAL_TAG = "experimental"


def experiment_id(metadata: Optional[dict]) -> Optional[str]:
    """Experiment ID from task metadata, or None for a production task."""
    if not metadata or "experiment" not in metadata:
        return None
    raw = metadata.get("experiment")
    exp = raw.get("id") if isinstance(raw, dict) else raw
    return exp.strip() if isinstance(exp, str) and exp.strip() else None


def evidence_is_experimental(evidence_pack: Any) -> bool:
    tags = getattr(evidence_pack, "tags", None) or []
    meta = getattr(evidence_pack, "meta", None) or {}
    return EXPERIMENTAL_TAG in tags or bool(meta.get("experiment"))


def production_eligibility(db: Session, evidence_pack: Any) -> Dict[str, Any]:
    """Whether this evidence may support a production acceptance decision."""
    from ..cwom.services import run_executor_id
    from ..db.cwom_models import CWOMReviewDecisionModel, CWOMRunModel

    reasons: List[str] = []
    if evidence_is_experimental(evidence_pack):
        exp = (getattr(evidence_pack, "meta", None) or {}).get("experiment")
        reasons.append(f"experimental run ({exp or 'experiment'}); never production evidence")
    if getattr(evidence_pack, "verdict", None) != "pass":
        reasons.append(f"verdict is {getattr(evidence_pack, 'verdict', None)!r}, not 'pass'")

    run = (
        db.query(CWOMRunModel)
        .filter(CWOMRunModel.id == evidence_pack.for_run_id)
        .first()
    )
    executor = run_executor_id(run) if run is not None else None
    approvals = (
        db.query(CWOMReviewDecisionModel)
        .filter(
            CWOMReviewDecisionModel.for_evidence_pack_id == evidence_pack.id,
            CWOMReviewDecisionModel.decision == "approved",
        )
        .all()
    )
    independent = [r for r in approvals if not executor or r.reviewer_id != executor]
    if not independent:
        reasons.append("no 'approved' review by an actor other than the executor")

    return {"eligible": not reasons, "reasons": reasons}
