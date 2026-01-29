"""
Audit Log Database Models.

Provides forensics and event sourcing capabilities for the DevOps Control Tower.
Every significant state change is recorded with before/after snapshots,
actor information, and trace context.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Index,
    String,
    Text,
)
from sqlalchemy.sql import func

from .base import Base


# Audit actor kind enum (matches CWOM actor kinds)
audit_actor_kind_enum = Enum(
    "human",
    "agent",
    "system",
    name="audit_actor_kind",
)

# Audit action enum
audit_action_enum = Enum(
    "created",
    "updated",
    "status_changed",
    "deleted",
    "linked",
    "unlinked",
    name="audit_action",
)


class AuditLogModel(Base):
    """Audit log entry for forensics and event sourcing.

    Every significant operation in the system should create an audit log entry.
    This provides:
    - Full traceability of who did what and when
    - Before/after state for debugging and rollback analysis
    - Correlation via trace_id for distributed tracing
    """

    __tablename__ = "audit_log"

    # Primary key (ULID for sortability and uniqueness)
    id = Column(String(36), primary_key=True)

    # Timestamp of the action
    ts = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        index=True,
    )

    # Who performed the action
    actor_kind = Column(audit_actor_kind_enum, nullable=False)
    actor_id = Column(String(128), nullable=False, index=True)

    # What action was performed
    action = Column(audit_action_enum, nullable=False, index=True)

    # What entity was affected
    entity_kind = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(128), nullable=False, index=True)

    # State before the action (JSON snapshot)
    before = Column(JSON, nullable=True)

    # State after the action (JSON snapshot)
    after = Column(JSON, nullable=True)

    # Optional human-readable note about the action
    note = Column(Text, nullable=True)

    # Trace ID for distributed tracing correlation
    trace_id = Column(String(36), nullable=True, index=True)

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_kind", "entity_id"),
        Index("ix_audit_log_actor", "actor_kind", "actor_id"),
        Index("ix_audit_log_ts_action", "ts", "action"),
        Index("ix_audit_log_entity_ts", "entity_kind", "entity_id", "ts"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "ts": self.ts.isoformat() if self.ts else None,
            "actor_kind": self.actor_kind,
            "actor_id": self.actor_id,
            "action": self.action,
            "entity_kind": self.entity_kind,
            "entity_id": self.entity_id,
            "before": self.before,
            "after": self.after,
            "note": self.note,
            "trace_id": self.trace_id,
        }
