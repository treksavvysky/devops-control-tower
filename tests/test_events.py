"""Tests for event models."""

import pytest
from datetime import datetime

from devops_control_tower.data.models.events import (
    Event, EventTypes, EventPriority, EventStatus
)


class TestEvent:
    """Test cases for the Event class."""
    
    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(
            event_type=EventTypes.SYSTEM_STARTUP,
            source="test",
            data={"key": "value"},
            priority=EventPriority.HIGH
        )
        
        assert event.type == EventTypes.SYSTEM_STARTUP
        assert event.source == "test"
        assert event.data == {"key": "value"}
        assert event.priority == EventPriority.HIGH
        assert event.status == EventStatus.PENDING
        assert event.id is not None
        assert isinstance(event.created_at, datetime)
    
    def test_event_defaults(self):
        """Test event creation with defaults."""
        event = Event(
            event_type="custom.event",
            source="test",
            data={}
        )
        
        assert event.priority == EventPriority.MEDIUM
        assert event.tags == {}
        assert event.status == EventStatus.PENDING
    
    def test_mark_processing(self):
        """Test marking event as processing."""
        event = Event("test.event", "test", {})
        
        event.mark_processing("test_processor")
        
        assert event.status == EventStatus.PROCESSING
        assert event.processed_by == "test_processor"
        assert event.processed_at is not None
    
    def test_mark_completed(self):
        """Test marking event as completed."""
        event = Event("test.event", "test", {})
        result = {"success": True}
        
        event.mark_completed(result)
        
        assert event.status == EventStatus.COMPLETED
        assert event.result == result
    
    def test_mark_failed(self):
        """Test marking event as failed."""
        event = Event("test.event", "test", {})
        error_msg = "Something went wrong"
        
        event.mark_failed(error_msg)
        
        assert event.status == EventStatus.FAILED
        assert event.error == error_msg
    
    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = Event(
            event_type="test.event",
            source="test",
            data={"key": "value"},
            priority=EventPriority.HIGH,
            tags={"env": "test"}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["type"] == "test.event"
        assert event_dict["source"] == "test"
        assert event_dict["data"] == {"key": "value"}
        assert event_dict["priority"] == "high"
        assert event_dict["tags"] == {"env": "test"}
        assert event_dict["status"] == "pending"
        assert "id" in event_dict
        assert "created_at" in event_dict
    
    def test_from_dict(self):
        """Test creating event from dictionary."""
        event_data = {
            "id": "test-id",
            "type": "test.event",
            "source": "test",
            "data": {"key": "value"},
            "priority": "high",
            "tags": {"env": "test"},
            "status": "pending",
            "created_at": "2023-01-01T00:00:00",
            "processed_at": None,
            "processed_by": None,
            "result": None,
            "error": None
        }
        
        event = Event.from_dict(event_data)
        
        assert event.id == "test-id"
        assert event.type == "test.event"
        assert event.source == "test"
        assert event.data == {"key": "value"}
        assert event.priority == EventPriority.HIGH
        assert event.tags == {"env": "test"}
        assert event.status == EventStatus.PENDING
    
    def test_event_string_representation(self):
        """Test event string representation."""
        event = Event("test.event", "test", {}, EventPriority.CRITICAL)
        
        str_repr = str(event)
        
        assert "Event(" in str_repr
        assert "test.event" in str_repr
        assert "critical" in str_repr
        assert event.id[:8] in str_repr


class TestEventTypes:
    """Test cases for EventTypes constants."""
    
    def test_event_types_defined(self):
        """Test that event types are properly defined."""
        # Infrastructure events
        assert hasattr(EventTypes, 'INFRASTRUCTURE_ALERT')
        assert hasattr(EventTypes, 'INFRASTRUCTURE_SCALING')
        assert hasattr(EventTypes, 'INFRASTRUCTURE_DEPLOYMENT')
        assert hasattr(EventTypes, 'INFRASTRUCTURE_FAILURE')
        
        # Security events
        assert hasattr(EventTypes, 'SECURITY_VULNERABILITY')
        assert hasattr(EventTypes, 'SECURITY_BREACH')
        assert hasattr(EventTypes, 'SECURITY_SCAN_COMPLETE')
        
        # Development events
        assert hasattr(EventTypes, 'CODE_COMMIT')
        assert hasattr(EventTypes, 'BUILD_COMPLETED')
        assert hasattr(EventTypes, 'BUILD_FAILED')
        
        # System events
        assert hasattr(EventTypes, 'SYSTEM_STARTUP')
        assert hasattr(EventTypes, 'SYSTEM_SHUTDOWN')
    
    def test_event_type_values(self):
        """Test that event types have expected values."""
        assert EventTypes.INFRASTRUCTURE_ALERT == "infrastructure.alert"
        assert EventTypes.SECURITY_VULNERABILITY == "security.vulnerability"
        assert EventTypes.CODE_COMMIT == "development.code_commit"
        assert EventTypes.SYSTEM_STARTUP == "system.startup"


class TestEventPriority:
    """Test cases for EventPriority enum."""
    
    def test_priority_values(self):
        """Test priority enum values."""
        assert EventPriority.LOW.value == "low"
        assert EventPriority.MEDIUM.value == "medium"
        assert EventPriority.HIGH.value == "high"
        assert EventPriority.CRITICAL.value == "critical"


class TestEventStatus:
    """Test cases for EventStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert EventStatus.PENDING.value == "pending"
        assert EventStatus.PROCESSING.value == "processing"
        assert EventStatus.COMPLETED.value == "completed"
        assert EventStatus.FAILED.value == "failed"
