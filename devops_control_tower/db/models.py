"""
SQLAlchemy models for DevOps Control Tower.
"""

import uuid as uuid_module
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
from sqlalchemy.types import CHAR

from .base import Base


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36)
    storing as stringified hex values.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, uuid_module.UUID):
                return str(value)
            else:
                return str(uuid_module.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, uuid_module.UUID):
            return value
        else:
            return uuid_module.UUID(value)


class TaskModel(Base):
    """SQLAlchemy model for V1 tasks."""

    __tablename__ = "tasks_v1"

    # Primary key - server-generated UUID (portable across DBs)
    id = Column(GUID(), primary_key=True, default=uuid_module.uuid4)

    # Core task fields
    type = Column(String(64), nullable=False, index=True)
    status = Column(
        Enum(
            "queued", "running", "completed", "failed", "cancelled",
            name="task_status"
        ),
        nullable=False,
        default="queued",
        index=True,
    )
    priority = Column(
        Enum("low", "medium", "high", "critical", name="task_priority"),
        nullable=False,
        default="medium",
        index=True,
    )
    source = Column(String(64), nullable=False, default="api", index=True)

    # Payload and options (JSON)
    payload = Column(JSON, nullable=False)
    target = Column(JSON, nullable=True)  # TaskTargetV1 as JSON
    options = Column(JSON, nullable=False, default=dict)  # TaskOptionsV1 as JSON
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    tags = Column(JSON, nullable=False, default=list)

    # Deduplication and callbacks
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    callback_url = Column(String(2000), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Execution tracking
    worker_id = Column(String(128), nullable=True)
    attempt = Column(Integer, nullable=False, default=0)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_tasks_v1_type_status", "type", "status"),
        Index("ix_tasks_v1_priority_status", "priority", "status"),
        Index("ix_tasks_v1_created_at", "created_at"),
        Index("ix_tasks_v1_source_status", "source", "status"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "task_id": str(self.id),
            "type": self.type,
            "status": self.status,
            "priority": self.priority,
            "source": self.source,
            "payload": self.payload,
            "target": self.target,
            "options": self.options,
            "metadata": self.metadata_,
            "tags": self.tags,
            "idempotency_key": self.idempotency_key,
            "callback_url": self.callback_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "worker_id": self.worker_id,
            "attempt": self.attempt,
            "result": self.result,
            "error": self.error,
        }


class EventModel(Base):
    """SQLAlchemy model for events."""

    __tablename__ = "events"

    # Primary fields
    id = Column(GUID(), primary_key=True, default=uuid_module.uuid4)
    type = Column(String(100), nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    data = Column(JSON, nullable=False, default=dict)
    priority = Column(
        Enum("low", "medium", "high", "critical", name="event_priority"),
        nullable=False,
        default="medium",
        index=True,
    )
    tags = Column(JSON, nullable=False, default=dict)

    # Status tracking
    status = Column(
        Enum("pending", "processing", "completed", "failed", name="event_status"),
        nullable=False,
        default="pending",
        index=True,
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Processing details
    processed_by = Column(String(100), nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_events_type_status", "type", "status"),
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_priority_status", "priority", "status"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "type": self.type,
            "source": self.source,
            "data": self.data,
            "priority": self.priority,
            "tags": self.tags,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat()
            if self.processed_at
            else None,
            "processed_by": self.processed_by,
            "result": self.result,
            "error": self.error,
        }


class WorkflowModel(Base):
    """SQLAlchemy model for workflows."""

    __tablename__ = "workflows"

    # Primary fields
    id = Column(GUID(), primary_key=True, default=uuid_module.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # Configuration
    trigger_events = Column(JSON, nullable=False, default=list)  # List of event types
    trigger_conditions = Column(Text, nullable=True)  # Stored as serialized function
    steps = Column(JSON, nullable=False, default=list)  # List of workflow steps

    # Status and execution tracking
    status = Column(
        Enum(
            "idle",
            "running",
            "completed",
            "failed",
            "cancelled",
            name="workflow_status",
        ),
        nullable=False,
        default="idle",
        index=True,
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_executed_at = Column(DateTime(timezone=True), nullable=True)

    # Execution details
    execution_count = Column(Integer, nullable=False, default=0)
    last_execution_context = Column(JSON, nullable=True)
    last_result = Column(JSON, nullable=True)
    last_error = Column(Text, nullable=True)

    # Configuration
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    timeout_seconds = Column(Integer, nullable=False, default=3600)  # 1 hour default

    # Indexes
    __table_args__ = (
        Index("ix_workflows_status_active", "status", "is_active"),
        Index("ix_workflows_last_executed", "last_executed_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "trigger_events": self.trigger_events,
            "steps": self.steps,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_executed_at": self.last_executed_at.isoformat()
            if self.last_executed_at
            else None,
            "execution_count": self.execution_count,
            "last_result": self.last_result,
            "last_error": self.last_error,
            "is_active": self.is_active,
            "timeout_seconds": self.timeout_seconds,
        }


class AgentModel(Base):
    """SQLAlchemy model for AI agents."""

    __tablename__ = "agents"

    # Primary fields
    id = Column(GUID(), primary_key=True, default=uuid_module.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    type = Column(
        String(50), nullable=False, index=True
    )  # e.g., 'infrastructure', 'security'
    description = Column(Text, nullable=True)

    # Configuration
    config = Column(JSON, nullable=False, default=dict)
    capabilities = Column(JSON, nullable=False, default=list)  # List of capabilities

    # Status tracking
    status = Column(
        Enum(
            "inactive", "starting", "running", "stopping", "error", name="agent_status"
        ),
        nullable=False,
        default="inactive",
        index=True,
    )

    # Health and performance
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(20), nullable=False, default="unknown", index=True)
    health_details = Column(JSON, nullable=True)

    # Execution statistics
    tasks_completed = Column(Integer, nullable=False, default=0)
    tasks_failed = Column(Integer, nullable=False, default=0)
    average_response_time = Column(Integer, nullable=True)  # in milliseconds

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)

    # Configuration
    is_enabled = Column(Boolean, nullable=False, default=True, index=True)
    auto_restart = Column(Boolean, nullable=False, default=True)
    max_concurrent_tasks = Column(Integer, nullable=False, default=5)

    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)

    # Indexes
    __table_args__ = (
        Index("ix_agents_type_status", "type", "status"),
        Index("ix_agents_health_enabled", "health_status", "is_enabled"),
        Index("ix_agents_last_activity", "last_activity_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "config": self.config,
            "capabilities": self.capabilities,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat()
            if self.last_heartbeat
            else None,
            "health_status": self.health_status,
            "health_details": self.health_details,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "average_response_time": self.average_response_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_activity_at": self.last_activity_at.isoformat()
            if self.last_activity_at
            else None,
            "is_enabled": self.is_enabled,
            "auto_restart": self.auto_restart,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "last_error": self.last_error,
            "error_count": self.error_count,
        }


# Note: The canonical TaskModel for JCT V1 Task Spec is defined above as TaskModel
# with __tablename__ = "tasks_v1". The duplicate definition that was here has been removed.
