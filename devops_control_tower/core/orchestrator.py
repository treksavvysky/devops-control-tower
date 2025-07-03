"""
Core orchestration engine for DevOps Control Tower.

This module provides the main orchestration capabilities that coordinate
AI agents, workflows, and integrations across the platform.
"""

from typing import Dict, List, Optional, Any
import asyncio
import logging
from datetime import datetime

from ..data.models.events import Event
from ..data.models.workflows import Workflow
from ..agents.base import BaseAgent


logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main orchestration engine that coordinates all platform activities.
    
    The Orchestrator manages:
    - AI agent lifecycle and coordination
    - Workflow execution and monitoring
    - Event processing and routing
    - Integration management
    - Resource allocation and optimization
    """
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.workflows: Dict[str, Workflow] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        
    async def start(self) -> None:
        """Start the orchestration engine."""
        logger.info("Starting DevOps Control Tower Orchestrator")
        self.is_running = True
        
        # Start the main event processing loop
        event_processor_task = asyncio.create_task(self._process_events())
        self.running_tasks["event_processor"] = event_processor_task
        
        # Start all registered agents
        for agent_name, agent in self.agents.items():
            task = asyncio.create_task(agent.start())
            self.running_tasks[f"agent_{agent_name}"] = task
            logger.info(f"Started agent: {agent_name}")
        
        logger.info("Orchestrator started successfully")
    
    async def stop(self) -> None:
        """Stop the orchestration engine and all components."""
        logger.info("Stopping DevOps Control Tower Orchestrator")
        self.is_running = False
        
        # Stop all agents
        for agent_name, agent in self.agents.items():
            await agent.stop()
            logger.info(f"Stopped agent: {agent_name}")
        
        # Cancel all running tasks
        for task_name, task in self.running_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Cancelled task: {task_name}")
        
        self.running_tasks.clear()
        logger.info("Orchestrator stopped successfully")
    
    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """Register an AI agent with the orchestrator."""
        self.agents[name] = agent
        logger.info(f"Registered agent: {name}")
    
    def register_workflow(self, name: str, workflow: Workflow) -> None:
        """Register a workflow with the orchestrator."""
        self.workflows[name] = workflow
        logger.info(f"Registered workflow: {name}")
    
    async def emit_event(self, event: Event) -> None:
        """Emit an event to be processed by the orchestrator."""
        await self.event_queue.put(event)
        logger.debug(f"Emitted event: {event.type}")
    
    async def execute_workflow(self, workflow_name: str, context: Dict[str, Any]) -> Any:
        """Execute a named workflow with the given context."""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow not found: {workflow_name}")
        
        workflow = self.workflows[workflow_name]
        logger.info(f"Executing workflow: {workflow_name}")
        
        try:
            result = await workflow.execute(context)
            logger.info(f"Workflow completed successfully: {workflow_name}")
            return result
        except Exception as e:
            logger.error(f"Workflow failed: {workflow_name}, error: {e}")
            raise
    
    async def _process_events(self) -> None:
        """Main event processing loop."""
        logger.info("Starting event processor")
        
        while self.is_running:
            try:
                # Wait for an event with timeout
                event = await asyncio.wait_for(
                    self.event_queue.get(), 
                    timeout=1.0
                )
                
                # Process the event
                await self._handle_event(event)
                
            except asyncio.TimeoutError:
                # No events to process, continue loop
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _handle_event(self, event: Event) -> None:
        """Handle a single event by routing it to appropriate agents/workflows."""
        logger.debug(f"Processing event: {event.type}")
        
        # Route event to interested agents
        for agent_name, agent in self.agents.items():
            if agent.handles_event_type(event.type):
                try:
                    await agent.handle_event(event)
                except Exception as e:
                    logger.error(f"Agent {agent_name} failed to handle event: {e}")
        
        # Check if any workflows should be triggered by this event
        for workflow_name, workflow in self.workflows.items():
            if workflow.is_triggered_by(event):
                try:
                    # Execute workflow in background
                    task = asyncio.create_task(
                        workflow.execute({"triggering_event": event})
                    )
                    self.running_tasks[f"workflow_{workflow_name}_{event.id}"] = task
                except Exception as e:
                    logger.error(f"Failed to trigger workflow {workflow_name}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the orchestrator."""
        return {
            "is_running": self.is_running,
            "agents": {
                name: agent.get_status() 
                for name, agent in self.agents.items()
            },
            "workflows": {
                name: workflow.get_status() 
                for name, workflow in self.workflows.items()
            },
            "running_tasks": len(self.running_tasks),
            "queue_size": self.event_queue.qsize(),
            "timestamp": datetime.utcnow().isoformat()
        }
