"""Tests for the core orchestrator."""

import pytest
import asyncio
from unittest.mock import AsyncMock

from devops_control_tower.core.orchestrator import Orchestrator
from devops_control_tower.agents.base import BaseAgent
from devops_control_tower.data.models.events import Event, EventTypes, EventPriority
from devops_control_tower.data.models.workflows import Workflow


class TestAgent(BaseAgent):
    """Test agent for testing purposes."""
    
    def __init__(self):
        super().__init__("test_agent", "Test agent for unit tests")
        self.register_event_type(EventTypes.SYSTEM_STARTUP)
        self.events_handled = []
    
    async def _initialize(self) -> None:
        pass
    
    async def _cleanup(self) -> None:
        pass
    
    async def handle_event(self, event: Event) -> None:
        self.events_handled.append(event)


class TestOrchestrator:
    """Test cases for the Orchestrator class."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initializes correctly."""
        orch = Orchestrator()
        assert not orch.is_running
        assert len(orch.agents) == 0
        assert len(orch.workflows) == 0
    
    def test_register_agent(self):
        """Test agent registration."""
        orch = Orchestrator()
        agent = TestAgent()
        
        orch.register_agent("test", agent)
        
        assert "test" in orch.agents
        assert orch.agents["test"] == agent
    
    def test_register_workflow(self):
        """Test workflow registration."""
        orch = Orchestrator()
        workflow = Workflow("test_workflow", "Test workflow")
        
        orch.register_workflow("test", workflow)
        
        assert "test" in orch.workflows
        assert orch.workflows["test"] == workflow
    
    @pytest.mark.asyncio
    async def test_start_stop_orchestrator(self, orchestrator):
        """Test starting and stopping the orchestrator."""
        assert not orchestrator.is_running
        
        await orchestrator.start()
        assert orchestrator.is_running
        
        await orchestrator.stop()
        assert not orchestrator.is_running
    
    @pytest.mark.asyncio
    async def test_emit_event(self, orchestrator):
        """Test event emission."""
        event = Event(
            event_type=EventTypes.SYSTEM_STARTUP,
            source="test",
            data={"test": True}
        )
        
        await orchestrator.emit_event(event)
        
        # Event should be in the queue
        assert orchestrator.event_queue.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_agent_handles_event(self, orchestrator):
        """Test that agents receive and handle events."""
        agent = TestAgent()
        orchestrator.register_agent("test", agent)
        
        await orchestrator.start()
        
        event = Event(
            event_type=EventTypes.SYSTEM_STARTUP,
            source="test",
            data={"test": True}
        )
        
        await orchestrator.emit_event(event)
        
        # Give some time for event processing
        await asyncio.sleep(0.1)
        
        # Agent should have handled the event
        assert len(agent.events_handled) == 1
        assert agent.events_handled[0] == event
        
        await orchestrator.stop()
    
    def test_get_status(self, orchestrator):
        """Test status reporting."""
        status = orchestrator.get_status()
        
        assert "is_running" in status
        assert "agents" in status
        assert "workflows" in status
        assert "running_tasks" in status
        assert "queue_size" in status
        assert "timestamp" in status
    
    @pytest.mark.asyncio
    async def test_execute_workflow_not_found(self, orchestrator):
        """Test executing non-existent workflow raises error."""
        with pytest.raises(ValueError, match="Workflow not found"):
            await orchestrator.execute_workflow("nonexistent", {})
