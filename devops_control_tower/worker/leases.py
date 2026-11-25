"""
Claim leases, expiry and held tasks (DEVOPS-CON-3 G7; DEVOPS-CON-10; DEVOPS-CON-11).

A claim is valid until ``tasks.lease_expires_at``. When a lease expires, DCT
must not hand the task to anyone else unless the previous holder's
**termination is confirmed** (George, 2026-11-25): otherwise the old process
could still be running while a new claimant starts, which gives two live
executions of one task.

So an expired lease is processed like this:

* if a ``TerminationConfirmer`` confirms the previous holder has terminated,
  the task is requeued (the holding run fails with ``LEASE_EXPIRED``);
* otherwise, which is always the case today since DCT has no substrate client
  yet, the task is **held**: status ``held``, run ``blocked``, reason recorded.
  An operator resolves it with :func:`resolve_held_task`.

The reaper is *not* what fences a stale holder. Completion refuses an expired
lease by itself (see :func:`devops_control_tower.lifecycle.finish`), so an
expired claim fails closed even if this reaper never runs or fails.

State changes go through :mod:`devops_control_tower.lifecycle`: one conditional
UPDATE on (id, status, claim_generation) plus the lease condition. Never on
timestamp equality (DEVOPS-CON-10), and never on holder identity alone, which
isn't unique per claim (ABA; PR #12 review N1).

Operator authorization: :func:`resolve_held_task` records the operator ID it
is given but does not *verify* it. Anyone who can run ``dct-held`` against the
DCT database (including an agent with a shell on that host) can resolve a
hold. Operator authentication is DEVOPS-CON-5.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.audit_service import AuditService
from ..db.cwom_models import CWOMIssueModel, CWOMRunModel
from ..db.models import TaskModel
from ..lifecycle import (
    LifecycleError,
    hold_expired,
    requeue_after_confirmed_termination,
    resolve_held,
)

logger = logging.getLogger(__name__)

LEASE_EXPIRED = "LEASE_EXPIRED"

#: Called with an expired task; returns True only if the previous holder's
#: execution is confirmed terminated. Any exception counts as "not confirmed".
TerminationConfirmer = Callable[[TaskModel], bool]


def _as_utc(value: datetime) -> datetime:
    """Normalise a DB datetime (SQLite returns naive values) to aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def lease_expiry(time_budget_seconds: int, now: Optional[datetime] = None) -> datetime:
    """Lease deadline: time budget plus the configured grace period."""
    now = now or datetime.now(timezone.utc)
    grace = get_settings().jct_lease_grace_seconds
    return now + timedelta(seconds=int(time_budget_seconds or 0) + grace)


def is_lease_expired(task: TaskModel, now: Optional[datetime] = None) -> bool:
    """True when the task has a lease and it has passed."""
    if task.lease_expires_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return _as_utc(task.lease_expires_at) <= now


def _runs_for(db: Session, task: TaskModel, statuses: List[str]) -> List[CWOMRunModel]:
    if not task.cwom_issue_id:
        return []
    return (
        db.query(CWOMRunModel)
        .filter(
            CWOMRunModel.for_issue_id == task.cwom_issue_id,
            CWOMRunModel.status.in_(statuses),
        )
        .all()
    )


def _issue_for(db: Session, task: TaskModel) -> Optional[CWOMIssueModel]:
    if not task.cwom_issue_id:
        return None
    return (
        db.query(CWOMIssueModel).filter(CWOMIssueModel.id == task.cwom_issue_id).first()
    )


def _confirmed(confirmer: Optional[TerminationConfirmer], task: TaskModel) -> bool:
    if confirmer is None:
        return False
    try:
        return bool(confirmer(task))
    except Exception as exc:  # fail closed: an erroring confirmer never requeues
        logger.warning("Termination confirmer failed for task %s: %s", task.id, exc)
        return False


def process_expired_leases(
    db: Session,
    actor_id: str = "lease-reaper",
    now: Optional[datetime] = None,
    confirm_termination: Optional[TerminationConfirmer] = None,
) -> Dict[str, List[str]]:
    """Hold (or, with confirmed termination, requeue) tasks whose lease expired.

    Returns ``{"held": [...], "requeued": [...]}``. Commits when anything changed.
    """
    now = now or datetime.now(timezone.utc)
    candidates = (
        db.query(TaskModel)
        .filter(TaskModel.status == "running", TaskModel.lease_expires_at.isnot(None))
        .all()
    )
    out: Dict[str, List[str]] = {"held": [], "requeued": []}
    audit = AuditService(db)

    for task in candidates:
        if not is_lease_expired(task, now):
            continue
        task_id = str(task.id)
        holder = task.assigned_to or "unknown"
        gen = task.claim_generation or 0
        expired_at = _as_utc(task.lease_expires_at).isoformat()

        if _confirmed(confirm_termination, task):
            if not requeue_after_confirmed_termination(db, task, now):
                continue
            note = (
                f"Claim generation {gen} by {holder} expired at {expired_at}; "
                "termination confirmed; task requeued"
            )
            audit.log_status_change(
                entity_kind="Task",
                entity_id=task_id,
                old_status="running",
                new_status="queued",
                actor_kind="system",
                actor_id=actor_id,
                note=note,
                trace_id=task.trace_id,
            )
            for run in _runs_for(db, task, ["running"]):
                run.status = "failed"
                run.failure = {
                    "code": LEASE_EXPIRED,
                    "message": note,
                    "termination": "confirmed",
                }
                audit.log_status_change(
                    entity_kind="Run",
                    entity_id=run.id,
                    old_status="running",
                    new_status="failed",
                    actor_kind="system",
                    actor_id=actor_id,
                    note=note,
                    trace_id=task.trace_id,
                )
            issue = _issue_for(db, task)
            if issue and issue.status == "running":
                issue.status = "planned"
            out["requeued"].append(task_id)
            logger.warning(
                "Lease expired for task %s; termination confirmed; requeued", task_id
            )
            continue

        reason = (
            f"Claim generation {gen} by {holder} expired at {expired_at}; termination "
            "of the previous holder not confirmed; held for operator resolution"
        )
        if not hold_expired(db, task, reason, now):
            continue
        audit.log_status_change(
            entity_kind="Task",
            entity_id=task_id,
            old_status="running",
            new_status="held",
            actor_kind="system",
            actor_id=actor_id,
            note=reason,
            trace_id=task.trace_id,
        )
        for run in _runs_for(db, task, ["running"]):
            run.status = "blocked"
            run.failure = {
                "code": LEASE_EXPIRED,
                "message": reason,
                "termination": "unconfirmed",
            }
            audit.log_status_change(
                entity_kind="Run",
                entity_id=run.id,
                old_status="running",
                new_status="blocked",
                actor_kind="system",
                actor_id=actor_id,
                note=reason,
                trace_id=task.trace_id,
            )
        issue = _issue_for(db, task)
        if issue and issue.status == "running":
            issue.status = "blocked"
        out["held"].append(task_id)
        logger.warning(
            "Lease expired for task %s; termination unconfirmed; HELD", task_id
        )

    if out["held"] or out["requeued"]:
        db.commit()
    return out


def list_held_tasks(db: Session) -> List[TaskModel]:
    return (
        db.query(TaskModel)
        .filter(TaskModel.status == "held")
        .order_by(TaskModel.held_at)
        .all()
    )


class HeldTaskError(ValueError):
    """Raised for invalid held-task resolutions."""


def resolve_held_task(
    db: Session,
    task_id: str,
    action: str,
    operator_id: str,
    note: str,
    termination_confirmed: bool = False,
) -> TaskModel:
    """Operator resolution of a held task (identity recorded, not verified).

    ``action="requeue"`` requires ``termination_confirmed=True``: the operator
    asserts the previous holder is no longer running. ``action="fail"`` ends
    the task. Both are audited with the operator ID and note.
    """
    if action not in ("requeue", "fail"):
        raise HeldTaskError("action must be 'requeue' or 'fail'")
    if not operator_id or not operator_id.strip():
        raise HeldTaskError("operator_id is required")
    if not note or not note.strip():
        raise HeldTaskError("a resolution note is required")
    if action == "requeue" and not termination_confirmed:
        raise HeldTaskError(
            "requeue requires confirmed termination of the previous holder "
            "(termination_confirmed=True)"
        )
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if task is None:
        raise HeldTaskError(f"task {task_id} not found")
    if task.status != "held":
        raise HeldTaskError(f"task {task_id} is not held (status {task.status})")

    try:
        changed = resolve_held(db, task, action)
    except LifecycleError as exc:
        raise HeldTaskError(str(exc)) from exc
    if not changed:
        raise HeldTaskError(f"task {task_id} changed concurrently; not resolved")
    if action == "fail":
        db.query(TaskModel).filter(TaskModel.id == task.id).update(
            {"error": f"Held task failed by operator {operator_id}: {note}"},
            synchronize_session=False,
        )
    new_status = "queued" if action == "requeue" else "failed"
    run_status = "failed"
    issue_status = "planned" if action == "requeue" else "failed"

    full_note = (
        f"Held task resolved by {operator_id} (operator identity recorded, not "
        f"verified): {action}"
        f"{' (termination confirmed by operator)' if termination_confirmed else ''}. "
        f"{note}"
    )
    audit = AuditService(db)
    audit.log_status_change(
        entity_kind="Task",
        entity_id=str(task.id),
        old_status="held",
        new_status=new_status,
        actor_kind="human",
        actor_id=operator_id,
        note=full_note,
        trace_id=task.trace_id,
    )
    for run in _runs_for(db, task, ["blocked"]):
        run.status = run_status
        failure = dict(run.failure or {})
        failure.update(
            {
                "resolution": action,
                "resolved_by": operator_id,
                "termination": "confirmed"
                if termination_confirmed
                else failure.get("termination", "unconfirmed"),
            }
        )
        run.failure = failure
        audit.log_status_change(
            entity_kind="Run",
            entity_id=run.id,
            old_status="blocked",
            new_status=run_status,
            actor_kind="human",
            actor_id=operator_id,
            note=full_note,
            trace_id=task.trace_id,
        )
    issue = _issue_for(db, task)
    if issue and issue.status == "blocked":
        issue.status = issue_status
    db.commit()
    db.expire_all()
    return db.query(TaskModel).filter(TaskModel.id == task_id).one()
