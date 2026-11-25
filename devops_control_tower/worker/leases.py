"""
Claim leases for tasks (DEVOPS-CON-3, gap G7).

A claim is valid until ``tasks.lease_expires_at``. Expired claims are requeued
so a crashed or rate-limited executor cannot leave a task ``running`` forever.
The run that held the expired claim is marked failed with ``LEASE_EXPIRED``,
which also makes any late completion from that claimant fail.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.audit_service import AuditService
from ..db.cwom_models import CWOMIssueModel, CWOMRunModel
from ..db.models import TaskModel

logger = logging.getLogger(__name__)

LEASE_EXPIRED = "LEASE_EXPIRED"


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


def requeue_expired(
    db: Session,
    actor_id: str = "lease-reaper",
    now: Optional[datetime] = None,
) -> List[str]:
    """Requeue running tasks whose lease has expired.

    Each requeue is a compare-and-set on (id, status, lease_expires_at), so two
    reapers cannot both act on the same expiry. Commits when anything changed.

    Returns:
        IDs of the tasks that were requeued.
    """
    now = now or datetime.now(timezone.utc)
    candidates = (
        db.query(TaskModel)
        .filter(TaskModel.status == "running", TaskModel.lease_expires_at.isnot(None))
        .all()
    )

    requeued: List[str] = []
    audit = AuditService(db)
    for task in candidates:
        if not is_lease_expired(task, now):
            continue

        old_assignee = task.assigned_to
        old_lease = task.lease_expires_at
        changed = (
            db.query(TaskModel)
            .filter(
                TaskModel.id == task.id,
                TaskModel.status == "running",
                TaskModel.lease_expires_at == old_lease,
            )
            .update(
                {
                    "status": "queued",
                    "assigned_to": None,
                    "started_at": None,
                    "lease_expires_at": None,
                },
                synchronize_session=False,
            )
        )
        if not changed:
            continue

        task_id = str(task.id)
        note = (
            f"Claim by {old_assignee or 'unknown'} expired at "
            f"{_as_utc(old_lease).isoformat()}; task requeued"
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

        if task.cwom_issue_id:
            runs = (
                db.query(CWOMRunModel)
                .filter(
                    CWOMRunModel.for_issue_id == task.cwom_issue_id,
                    CWOMRunModel.status == "running",
                )
                .all()
            )
            for run in runs:
                run.status = "failed"
                run.failure = {"code": LEASE_EXPIRED, "message": note}
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
            issue = (
                db.query(CWOMIssueModel)
                .filter(CWOMIssueModel.id == task.cwom_issue_id)
                .first()
            )
            if issue and issue.status == "running":
                issue.status = "planned"

        requeued.append(task_id)
        logger.warning("Lease expired for task %s; requeued (%s)", task_id, note)

    if requeued:
        db.commit()
    return requeued
