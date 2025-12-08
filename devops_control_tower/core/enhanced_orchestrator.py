"""
Enhanced orchestration engine with database integration.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..agents.base import BaseAgent
from ..config import get_settings
from ..data.models.events import Event
from ..data.models.workflows import Workflow
from ..db.base import SessionLocal
from ..db.services import AgentService, EventService, WorkflowService

logger = logging.getLogger(__name__)


class DatabaseOrchestratorMixin:
    """Mixin to add database capabilities to orchestrator."""

    _db: Optional[Session]
    _event_service: Optional[EventService]
    _workflow_service: Optional[WorkflowService]
    _agent_service: Optional[AgentService]

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self._db = None
        self._event_service = None
        self._workflow_service = None
        self._agent_service = None

    @property
    def db(self) -> Session:
        """Get database session."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def event_service(self) -> EventService:
        """Get event service."""
        if self._event_service is None:
            self._event_service = EventService(self.db)
        return self._event_service

    @property
    def workflow_service(self) -> WorkflowService:
        """Get workflow service."""
        if self._workflow_service is None:
            self._workflow_service = WorkflowService(self.db)
        return self._workflow_service

    @property
    def agent_service(self) -> AgentService:
        """Get agent service."""
        if self._agent_service is None:
            self._agent_service = AgentService(self.db)
        return self._agent_service

    async def close_db(self) -> None:
        """Close database connections."""
        if self._db:
            self._db.close()
            self._db = None

        # Reset services
        self._event_service = None
        self._workflow_service = None
        self._agent_service = None


class EnhancedOrchestrator(DatabaseOrchestratorMixin):
    """Enhanced orchestrator with database persistence."""

    def __init__(self) -> None:
        super().__init__()
        self.agents: Dict[str, BaseAgent] = {}
        self.workflows: Dict[str, Workflow] = {}
        self.running_tasks: Dict[str, asyncio.Task[Any]] = {}
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self.is_running = False

    async def start(self) -> None:
        """Start the enhanced orchestration engine."""
        logger.info("Starting Enhanced DevOps Control Tower Orchestrator")
        self.is_running = True

        # Initialize database connections
        await self._initialize_database()

        # Load existing workflows and agents from database
        await self._load_from_database()

        # Start core processing tasks
        await self._start_core_tasks()

        logger.info("Enhanced Orchestrator started successfully")

    async def stop(self) -> None:
        """Stop the orchestration engine."""
        logger.info("Stopping Enhanced Orchestrator")
        self.is_running = False

        # Stop all agents
        for agent in self.agents.values():
            await agent.stop()

        # Cancel all running tasks
        for task in self.running_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)

        # Close database connections
        await self.close_db()

        logger.info("Enhanced Orchestrator stopped")

    async def _initialize_database(self) -> None:
        """Initialize database connections and verify tables exist."""
        try:
            # Test database connection
            db_agents = self.agent_service.get_agents()
            logger.info(
                f"Database connected successfully. Found {len(db_agents)} agents."
            )
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def _load_from_database(self) -> None:
        """Load existing workflows and agents from database."""
        try:
            # Load workflows
            db_workflows = self.workflow_service.get_workflows(active_only=True)
            logger.info(f"Loaded {len(db_workflows)} active workflows from database")

            # Load agents
            db_agents = self.agent_service.get_agents(enabled_only=True)
            logger.info(f"Loaded {len(db_agents)} enabled agents from database")

        except Exception as e:
            logger.error(f"Failed to load from database: {e}")
            raise

    async def _start_core_tasks(self) -> None:
        """Start core processing tasks."""
        # Event processor
        event_task = asyncio.create_task(self._process_events())
        self.running_tasks["event_processor"] = event_task

        # Agent health monitor
        health_task = asyncio.create_task(self._monitor_agent_health())
        self.running_tasks["health_monitor"] = health_task

        # Workflow scheduler
        workflow_task = asyncio.create_task(self._schedule_workflows())
        self.running_tasks["workflow_scheduler"] = workflow_task

    async def _process_events(self) -> None:
        """
        Spine v0 stub event loop.

        The enhanced orchestrator expects an event-processing coroutine,
        but for now we don't need any real event routing logic to prove
        the /tasks/enqueue → DB → worker → trace spine.
        """
        return

    async def _monitor_agent_health(self) -> None:
        """
        Spine v0 stub event loop.

        The enhanced orchestrator expects an event-processing coroutine,
        but for now we don't need any real event routing logic to prove
        the /tasks/enqueue → DB → worker → trace spine.
        """
        return

    async def _schedule_workflows(self) -> None:
        """
        Spine v0 stub event loop.

        The enhanced orchestrator expects an event-processing coroutine,
        but for now we don't need any real event routing logic to prove
        the /tasks/enqueue → DB → worker → trace spine.
        """
        return

    def register_agent(self, name: str, agent: BaseAgent) -> None:
        """Register an AI agent with the orchestrator."""
        self.agents[name] = agent

    async def submit_event(self, event: Event) -> str:
        """
        Submit an event for processing.

        For spine v0 this just persists to the database and returns the ID.
        """
        db_event = self.event_service.create_event(event)
        return str(db_event.id)
