"""
Audit Log Service.

Provides a clean interface for recording audit events throughout the application.
All CWOM and Task operations should use this service to maintain an audit trail.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from .audit_models import AuditLogModel


def generate_ulid() -> str:
    """Generate a ULID for audit log entries."""
    try:
        from ulid import ULID
        return str(ULID())
    except ImportError:
        import uuid
        return str(uuid.uuid4())


class AuditService:
    """Service for managing audit log entries.

    Usage:
        audit = AuditService(db_session)
        audit.log_create("Issue", issue.id, issue.to_dict(), actor_kind="agent", actor_id="worker-1")
    """

    def __init__(self, db: Session):
        self.db = db

    def log_create(
        self,
        entity_kind: str,
        entity_id: str,
        after: Dict[str, Any],
        actor_kind: str = "system",
        actor_id: str = "unknown",
        note: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLogModel:
        """Log the creation of an entity.

        Args:
            entity_kind: Type of entity (e.g., "Repo", "Issue", "Task")
            entity_id: ID of the entity
            after: State of the entity after creation
            actor_kind: Type of actor ("human", "agent", "system")
            actor_id: ID of the actor
            note: Optional human-readable note
            trace_id: Optional trace ID for correlation

        Returns:
            The created AuditLogModel
        """
        entry = AuditLogModel(
            id=generate_ulid(),
            ts=datetime.now(timezone.utc),
            actor_kind=actor_kind,
            actor_id=actor_id,
            action="created",
            entity_kind=entity_kind,
            entity_id=entity_id,
            before=None,
            after=after,
            note=note,
            trace_id=trace_id,
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def log_update(
        self,
        entity_kind: str,
        entity_id: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
        actor_kind: str = "system",
        actor_id: str = "unknown",
        note: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLogModel:
        """Log an update to an entity.

        Args:
            entity_kind: Type of entity (e.g., "Repo", "Issue", "Task")
            entity_id: ID of the entity
            before: State of the entity before the update
            after: State of the entity after the update
            actor_kind: Type of actor ("human", "agent", "system")
            actor_id: ID of the actor
            note: Optional human-readable note
            trace_id: Optional trace ID for correlation

        Returns:
            The created AuditLogModel
        """
        entry = AuditLogModel(
            id=generate_ulid(),
            ts=datetime.now(timezone.utc),
            actor_kind=actor_kind,
            actor_id=actor_id,
            action="updated",
            entity_kind=entity_kind,
            entity_id=entity_id,
            before=before,
            after=after,
            note=note,
            trace_id=trace_id,
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def log_status_change(
        self,
        entity_kind: str,
        entity_id: str,
        old_status: str,
        new_status: str,
        actor_kind: str = "system",
        actor_id: str = "unknown",
        note: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLogModel:
        """Log a status change on an entity.

        Args:
            entity_kind: Type of entity (e.g., "Issue", "Run", "Task")
            entity_id: ID of the entity
            old_status: Previous status value
            new_status: New status value
            actor_kind: Type of actor ("human", "agent", "system")
            actor_id: ID of the actor
            note: Optional human-readable note
            trace_id: Optional trace ID for correlation

        Returns:
            The created AuditLogModel
        """
        entry = AuditLogModel(
            id=generate_ulid(),
            ts=datetime.now(timezone.utc),
            actor_kind=actor_kind,
            actor_id=actor_id,
            action="status_changed",
            entity_kind=entity_kind,
            entity_id=entity_id,
            before={"status": old_status},
            after={"status": new_status},
            note=note or f"Status changed: {old_status} -> {new_status}",
            trace_id=trace_id,
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def log_delete(
        self,
        entity_kind: str,
        entity_id: str,
        before: Dict[str, Any],
        actor_kind: str = "system",
        actor_id: str = "unknown",
        note: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLogModel:
        """Log the deletion of an entity.

        Args:
            entity_kind: Type of entity (e.g., "Repo", "Issue", "Task")
            entity_id: ID of the entity
            before: State of the entity before deletion
            actor_kind: Type of actor ("human", "agent", "system")
            actor_id: ID of the actor
            note: Optional human-readable note
            trace_id: Optional trace ID for correlation

        Returns:
            The created AuditLogModel
        """
        entry = AuditLogModel(
            id=generate_ulid(),
            ts=datetime.now(timezone.utc),
            actor_kind=actor_kind,
            actor_id=actor_id,
            action="deleted",
            entity_kind=entity_kind,
            entity_id=entity_id,
            before=before,
            after=None,
            note=note,
            trace_id=trace_id,
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def log_link(
        self,
        entity_kind: str,
        entity_id: str,
        linked_kind: str,
        linked_id: str,
        actor_kind: str = "system",
        actor_id: str = "unknown",
        note: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLogModel:
        """Log linking two entities together.

        Args:
            entity_kind: Type of primary entity
            entity_id: ID of primary entity
            linked_kind: Type of linked entity
            linked_id: ID of linked entity
            actor_kind: Type of actor ("human", "agent", "system")
            actor_id: ID of the actor
            note: Optional human-readable note
            trace_id: Optional trace ID for correlation

        Returns:
            The created AuditLogModel
        """
        entry = AuditLogModel(
            id=generate_ulid(),
            ts=datetime.now(timezone.utc),
            actor_kind=actor_kind,
            actor_id=actor_id,
            action="linked",
            entity_kind=entity_kind,
            entity_id=entity_id,
            before=None,
            after={"linked_kind": linked_kind, "linked_id": linked_id},
            note=note or f"Linked to {linked_kind}:{linked_id}",
            trace_id=trace_id,
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def log_unlink(
        self,
        entity_kind: str,
        entity_id: str,
        unlinked_kind: str,
        unlinked_id: str,
        actor_kind: str = "system",
        actor_id: str = "unknown",
        note: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLogModel:
        """Log unlinking two entities.

        Args:
            entity_kind: Type of primary entity
            entity_id: ID of primary entity
            unlinked_kind: Type of unlinked entity
            unlinked_id: ID of unlinked entity
            actor_kind: Type of actor ("human", "agent", "system")
            actor_id: ID of the actor
            note: Optional human-readable note
            trace_id: Optional trace ID for correlation

        Returns:
            The created AuditLogModel
        """
        entry = AuditLogModel(
            id=generate_ulid(),
            ts=datetime.now(timezone.utc),
            actor_kind=actor_kind,
            actor_id=actor_id,
            action="unlinked",
            entity_kind=entity_kind,
            entity_id=entity_id,
            before={"linked_kind": unlinked_kind, "linked_id": unlinked_id},
            after=None,
            note=note or f"Unlinked from {unlinked_kind}:{unlinked_id}",
            trace_id=trace_id,
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    # Query methods

    def query_by_entity(
        self,
        entity_kind: str,
        entity_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogModel]:
        """Get audit history for a specific entity.

        Args:
            entity_kind: Type of entity
            entity_id: ID of the entity
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of AuditLogModel entries, newest first
        """
        return (
            self.db.query(AuditLogModel)
            .filter(
                AuditLogModel.entity_kind == entity_kind,
                AuditLogModel.entity_id == entity_id,
            )
            .order_by(desc(AuditLogModel.ts))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def query_by_trace(
        self,
        trace_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogModel]:
        """Get all audit entries for a trace ID.

        Args:
            trace_id: Trace ID to query
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of AuditLogModel entries, newest first
        """
        return (
            self.db.query(AuditLogModel)
            .filter(AuditLogModel.trace_id == trace_id)
            .order_by(desc(AuditLogModel.ts))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def query_by_actor(
        self,
        actor_kind: str,
        actor_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogModel]:
        """Get all audit entries by a specific actor.

        Args:
            actor_kind: Type of actor ("human", "agent", "system")
            actor_id: ID of the actor
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of AuditLogModel entries, newest first
        """
        return (
            self.db.query(AuditLogModel)
            .filter(
                AuditLogModel.actor_kind == actor_kind,
                AuditLogModel.actor_id == actor_id,
            )
            .order_by(desc(AuditLogModel.ts))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def query_by_action(
        self,
        action: str,
        entity_kind: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogModel]:
        """Get all audit entries for a specific action type.

        Args:
            action: Action type ("created", "updated", "status_changed", "deleted", "linked", "unlinked")
            entity_kind: Optional filter by entity type
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of AuditLogModel entries, newest first
        """
        query = self.db.query(AuditLogModel).filter(AuditLogModel.action == action)

        if entity_kind:
            query = query.filter(AuditLogModel.entity_kind == entity_kind)

        return (
            query.order_by(desc(AuditLogModel.ts))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def query_recent(
        self,
        limit: int = 50,
        entity_kind: Optional[str] = None,
    ) -> List[AuditLogModel]:
        """Get most recent audit entries.

        Args:
            limit: Maximum number of entries to return
            entity_kind: Optional filter by entity type

        Returns:
            List of AuditLogModel entries, newest first
        """
        query = self.db.query(AuditLogModel)

        if entity_kind:
            query = query.filter(AuditLogModel.entity_kind == entity_kind)

        return query.order_by(desc(AuditLogModel.ts)).limit(limit).all()
