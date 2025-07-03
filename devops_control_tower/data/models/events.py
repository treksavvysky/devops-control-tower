"""
Event models for the DevOps Control Tower.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid


class EventPriority(Enum):
    """Event priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Event:
    """
    Represents an event in the DevOps Control Tower system.
    
    Events are the primary means of communication between components
    and trigger automated responses from agents and workflows.
    """
    
    def __init__(
        self,
        event_type: str,
        source: str,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.MEDIUM,
        tags: Optional[Dict[str, str]] = None
    ):
        self.id = str(uuid.uuid4())
        self.type = event_type
        self.source = source
        self.data = data
        self.priority = priority
        self.tags = tags or {}
        self.status = EventStatus.PENDING
        self.created_at = datetime.utcnow()
        self.processed_at: Optional[datetime] = None
        self.processed_by: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
    
    def mark_processing(self, processor: str) -> None:
        """Mark the event as being processed."""
        self.status = EventStatus.PROCESSING
        self.processed_at = datetime.utcnow()
        self.processed_by = processor
    
    def mark_completed(self, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark the event as completed."""
        self.status = EventStatus.COMPLETED
        self.result = result
    
    def mark_failed(self, error: str) -> None:
        """Mark the event as failed."""
        self.status = EventStatus.FAILED
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "data": self.data,
            "priority": self.priority.value,
            "tags": self.tags,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "processed_by": self.processed_by,
            "result": self.result,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create an event from a dictionary."""
        event = cls(
            event_type=data["type"],
            source=data["source"],
            data=data["data"],
            priority=EventPriority(data["priority"]),
            tags=data.get("tags")
        )
        
        event.id = data["id"]
        event.status = EventStatus(data["status"])
        event.created_at = datetime.fromisoformat(data["created_at"])
        
        if data.get("processed_at"):
            event.processed_at = datetime.fromisoformat(data["processed_at"])
        
        event.processed_by = data.get("processed_by")
        event.result = data.get("result")
        event.error = data.get("error")
        
        return event
    
    def __str__(self) -> str:
        return f"Event(id={self.id[:8]}, type={self.type}, priority={self.priority.value})"
    
    def __repr__(self) -> str:
        return self.__str__()


# Common event types used throughout the system
class EventTypes:
    """Common event types used in the system."""
    
    # Infrastructure events
    INFRASTRUCTURE_ALERT = "infrastructure.alert"
    INFRASTRUCTURE_SCALING = "infrastructure.scaling"
    INFRASTRUCTURE_DEPLOYMENT = "infrastructure.deployment"
    INFRASTRUCTURE_FAILURE = "infrastructure.failure"
    
    # Security events
    SECURITY_VULNERABILITY = "security.vulnerability"
    SECURITY_BREACH = "security.breach"
    SECURITY_SCAN_COMPLETE = "security.scan_complete"
    
    # Development events
    CODE_COMMIT = "development.code_commit"
    CODE_REVIEW = "development.code_review"
    BUILD_STARTED = "development.build_started"
    BUILD_COMPLETED = "development.build_completed"
    BUILD_FAILED = "development.build_failed"
    
    # Deployment events
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_ROLLBACK = "deployment.rollback"
    
    # Monitoring events
    METRIC_THRESHOLD = "monitoring.metric_threshold"
    HEALTH_CHECK_FAILED = "monitoring.health_check_failed"
    SERVICE_DOWN = "monitoring.service_down"
    SERVICE_RECOVERED = "monitoring.service_recovered"
    
    # User events
    USER_ACTION = "user.action"
    USER_REQUEST = "user.request"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    AGENT_STARTED = "system.agent_started"
    AGENT_STOPPED = "system.agent_stopped"
    WORKFLOW_TRIGGERED = "system.workflow_triggered"
    WORKFLOW_COMPLETED = "system.workflow_completed"
