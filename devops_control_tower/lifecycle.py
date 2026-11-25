"""
Task lifecycle: the single enforcement point for task state transitions.

Every change to ``tasks.status`` goes through this module (DEVOPS-CON-11; PR #12
review B1–B3, N1). Each transition is ONE conditional ``UPDATE`` whose
``WHERE`` clause encodes the invariants, so they hold atomically across
processes and on SQLite and PostgreSQL alike:

* ownership: the writer must be the claim's ``assigned_to``;
* claim generation: every claim increments ``claim_generation``; a writer
  must present the generation it claimed, so a stale holder or stale reaper
  can never act on a newer claim (ABA);
* lease validity: completing requires ``lease_expires_at > now`` *in the
  UPDATE itself*, so an expired claim fails closed even if the lease reaper
  never ran or failed;
* confirmed termination: an expired claim becomes ``queued`` again only with
  confirmed termination; otherwise it is ``held`` for an operator;
* generic transitions (REST ``PATCH /tasks/{id}/status``, enqueue) are
  limited to ``pending→queued``, ``pending→cancelled`` and
  ``queued→cancelled``. Nothing generic can enter or leave ``running`` or
  ``held``, or complete a task.

Callers that also update runs, issues or evidence do so only *after* the task
transition succeeds, in the same transaction.

Not enforced here (DEVOPS-CON-5): caller authentication. Identities passed in
(executor actor, operator) are as trustworthy as the surface that supplied
them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .db.audit_service import AuditService
from .db.models import TaskModel

GENERIC_TRANSITIONS = frozenset(
    {("pending", "queued"), ("pending", "cancelled"), ("queued", "cancelled")}
)


class LifecycleError(Exception):
    """A lifecycle transition was refused. ``code`` is stable for callers."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ClaimToken:
    """What a claimant holds: task, identity and the generation it claimed."""

    task_id: str
    actor: str
    generation: int


def _now(now: Optional[datetime]) -> datetime:
    return now or datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _cas(db: Session, task_id: str, conditions: list, values: Dict[str, Any]) -> bool:
    changed = (
        db.query(TaskModel)
        .filter(TaskModel.id == task_id, *conditions)
        .update(values, synchronize_session=False)
    )
    return bool(changed)


def diagnose(
    db: Session, token: ClaimToken, now: Optional[datetime] = None
) -> LifecycleError:
    """Why ``token`` is not (or no longer) a live claim."""
    now = _now(now)
    db.expire_all()
    task = db.query(TaskModel).filter(TaskModel.id == token.task_id).first()
    if task is None:
        return LifecycleError("TASK_NOT_FOUND", f"Task '{token.task_id}' not found.")
    if task.status != "running":
        return LifecycleError(
            "TASK_NOT_RUNNING",
            f"Task '{task.id}' is not running (current status: {task.status}).",
        )
    if task.assigned_to != token.actor:
        return LifecycleError(
            "CLAIM_NOT_HELD",
            f"Task '{task.id}' is claimed by '{task.assigned_to}', "
            f"not '{token.actor}'.",
        )
    if (task.claim_generation or 0) != token.generation:
        return LifecycleError(
            "CLAIM_LOST",
            f"Claim generation {token.generation} is stale for task '{task.id}' "
            f"(current {task.claim_generation}).",
        )
    if task.lease_expires_at is None or _as_utc(task.lease_expires_at) <= now:
        return LifecycleError(
            "LEASE_EXPIRED", f"The claim lease on task '{task.id}' has expired."
        )
    return LifecycleError(
        "CONCURRENT_CHANGE", f"Task '{task.id}' changed concurrently."
    )


def _live_conditions(token: ClaimToken, now: datetime) -> list:
    return [
        TaskModel.status == "running",
        TaskModel.assigned_to == token.actor,
        TaskModel.claim_generation == token.generation,
        TaskModel.lease_expires_at > now,
    ]


# --------------------------------------------------------------- claim
def claim(
    db: Session,
    task_id: str,
    actor: str,
    lease_expires_at: datetime,
    now: Optional[datetime] = None,
) -> Optional[ClaimToken]:
    """queued → running for ``actor``. Returns the token, or None if not claimable.

    Commits, so the claim is visible to other processes immediately.
    """
    now = _now(now)
    ok = _cas(
        db,
        task_id,
        [TaskModel.status == "queued"],
        {
            "status": "running",
            "assigned_to": actor,
            "started_at": now,
            "lease_expires_at": lease_expires_at,
            "claim_generation": TaskModel.claim_generation + 1,
        },
    )
    if not ok:
        return None  # nothing was written
    db.commit()
    db.expire_all()
    task = db.query(TaskModel).filter(TaskModel.id == task_id).one()
    return ClaimToken(
        task_id=str(task.id), actor=actor, generation=task.claim_generation
    )


def require_live_claim(
    db: Session, token: ClaimToken, now: Optional[datetime] = None
) -> TaskModel:
    """Read check for non-terminal writes (e.g. artifacts). Raises if not live."""
    now = _now(now)
    task = (
        db.query(TaskModel)
        .filter(TaskModel.id == token.task_id, *_live_conditions(token, now))
        .first()
    )
    if task is None:
        raise diagnose(db, token, now)
    return task


# --------------------------------------------------------------- finish
def finish(
    db: Session,
    token: ClaimToken,
    success: bool,
    *,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    trace_path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """running → completed|failed, only for the live claim. Does not commit.

    Fails closed: an expired lease, another holder, a newer generation or a
    non-running task all refuse, independent of whether any reaper ran.
    """
    now = _now(now)
    final = "completed" if success else "failed"
    values: Dict[str, Any] = {
        "status": final,
        "completed_at": now,
        "lease_expires_at": None,
    }
    if result is not None:
        values["result"] = result
    if error is not None:
        values["error"] = error
    if trace_path is not None:
        values["trace_path"] = trace_path
    if not _cas(db, token.task_id, _live_conditions(token, now), values):
        raise diagnose(db, token, now)
    AuditService(db).log_status_change(
        entity_kind="Task",
        entity_id=token.task_id,
        old_status="running",
        new_status=final,
        actor_kind="agent",
        actor_id=token.actor,
        note=f"Finished by claim generation {token.generation}",
    )
    return final


# --------------------------------------------------------------- expiry
def hold_expired(
    db: Session, task: TaskModel, reason: str, now: Optional[datetime] = None
) -> bool:
    """running → held for an expired claim of exactly this generation.

    Does not commit.
    """
    now = _now(now)
    return _cas(
        db,
        str(task.id),
        [
            TaskModel.status == "running",
            TaskModel.claim_generation == (task.claim_generation or 0),
            TaskModel.lease_expires_at <= now,
        ],
        {
            "status": "held",
            "lease_expires_at": None,
            "held_at": now,
            "held_reason": reason,
        },
    )


def requeue_after_confirmed_termination(
    db: Session, task: TaskModel, now: Optional[datetime] = None
) -> bool:
    """running → queued for an expired claim whose termination is confirmed."""
    now = _now(now)
    return _cas(
        db,
        str(task.id),
        [
            TaskModel.status == "running",
            TaskModel.claim_generation == (task.claim_generation or 0),
            TaskModel.lease_expires_at <= now,
        ],
        {
            "status": "queued",
            "assigned_to": None,
            "started_at": None,
            "lease_expires_at": None,
        },
    )


def resolve_held(
    db: Session, task: TaskModel, action: str, now: Optional[datetime] = None
) -> bool:
    """held → queued|failed for exactly the held generation. Does not commit."""
    now = _now(now)
    if action == "requeue":
        values = {
            "status": "queued",
            "assigned_to": None,
            "started_at": None,
            "held_at": None,
            "held_reason": None,
        }
    elif action == "fail":
        values = {"status": "failed", "completed_at": now}
    else:
        raise LifecycleError("INVALID_ACTION", "action must be 'requeue' or 'fail'")
    return _cas(
        db,
        str(task.id),
        [
            TaskModel.status == "held",
            TaskModel.claim_generation == (task.claim_generation or 0),
        ],
        values,
    )


# --------------------------------------------------------------- generic
def generic_transition(
    db: Session,
    task_id: str,
    to_status: str,
    extras: Optional[Dict[str, Any]] = None,
    actor_id: str = "generic",
    now: Optional[datetime] = None,
) -> TaskModel:
    """Allowed generic transitions only (see GENERIC_TRANSITIONS). Commits.

    ``extras`` may carry result, error or trace_path; ownership fields can't be
    set here.
    """
    now = _now(now)
    extras = dict(extras or {})
    forbidden = {
        "assigned_to",
        "lease_expires_at",
        "claim_generation",
        "held_at",
        "held_reason",
        "started_at",
        "status",
    } & set(extras)
    if forbidden:
        raise LifecycleError(
            "TRANSITION_FORBIDDEN",
            f"{sorted(forbidden)} can only change through claim/finish/hold/resolve.",
        )
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if task is None:
        raise LifecycleError("TASK_NOT_FOUND", f"Task '{task_id}' not found.")
    current = task.status
    if (current, to_status) not in GENERIC_TRANSITIONS:
        raise LifecycleError(
            "TRANSITION_FORBIDDEN",
            f"Generic transition {current} → {to_status} is not allowed; use the "
            "claim/finish/hold/resolve lifecycle operations.",
        )
    values: Dict[str, Any] = {"status": to_status, **extras}
    if to_status == "queued" and not task.queued_at:
        values["queued_at"] = now
    if to_status == "cancelled":
        values["completed_at"] = now
    if not _cas(db, task_id, [TaskModel.status == current], values):
        raise LifecycleError(
            "CONCURRENT_CHANGE", f"Task '{task_id}' changed concurrently."
        )
    AuditService(db).log_status_change(
        entity_kind="Task",
        entity_id=task_id,
        old_status=current,
        new_status=to_status,
        actor_kind="system",
        actor_id=actor_id,
        note="generic transition",
    )
    db.commit()
    db.expire_all()
    return db.query(TaskModel).filter(TaskModel.id == task_id).one()
