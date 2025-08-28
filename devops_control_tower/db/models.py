"""
SQLAlchemy models for DevOps Control Tower.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import (
    Column, String, DateTime, Text, JSON, Enum,
    Integer, Boolean, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class EventModel(Base):
    """SQLAlchemy model for events."""
    
    __tablename__ = "events"
    
    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(100), nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    data = Column(JSON, nullable=False, default=dict)
    priority = Column(
        Enum("low", "medium", "high", "critical", name="event_priority"),
        nullable=False,
        default="medium",
        index=True
    )
    tags = Column(JSON, nullable=False, default=dict)
    
    # Status tracking
    status = Column(
        Enum("pending", "processing", "completed", "failed", name="event_status"),
        nullable=False,
        default="pending",
        index=True
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
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "processed_by": self.processed_by,
            "result": self.result,
            "error": self.error,
        }


class WorkflowModel(Base):
    """SQLAlchemy model for workflows."""
    
    __tablename__ = "workflows"
    
    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Configuration
    trigger_events = Column(JSON, nullable=False, default=list)  # List of event types
    trigger_conditions = Column(Text, nullable=True)  # Stored as serialized function
    steps = Column(JSON, nullable=False, default=list)  # List of workflow steps
    
    # Status and execution tracking
    status = Column(
        Enum("idle", "running", "completed", "failed", "cancelled", name="workflow_status"),
        nullable=False,
        default="idle",
        index=True
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
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
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
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    type = Column(String(50), nullable=False, index=True)  # e.g., 'infrastructure', 'security'
    description = Column(Text, nullable=True)
    
    # Configuration
    config = Column(JSON, nullable=False, default=dict)
    capabilities = Column(JSON, nullable=False, default=list)  # List of capabilities
    
    # Status tracking
    status = Column(
        Enum("inactive", "starting", "running", "stopping", "error", name="agent_status"),
        nullable=False,
        default="inactive",
        index=True
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
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "health_status": self.health_status,
            "health_details": self.health_details,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "average_response_time": self.average_response_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "is_enabled": self.is_enabled,
            "auto_restart": self.auto_restart,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "last_error": self.last_error,
            "error_count": self.error_count,
        }
