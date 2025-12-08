"""
Enhanced FastAPI application with full API endpoints.
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import structlog
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import get_settings
from .core.enhanced_orchestrator import EnhancedOrchestrator
from .data.models.events import Event, EventPriority, EventTypes
from .db.base import get_db, init_database
from .db.services import EventService, TaskService, WorkflowService
from .policies import PolicyResult, validate_task
from .schemas.task_v1 import (
    TaskCreateV1,
    TaskErrorDetail,
    TaskErrorResponse,
    TaskResponseV1,
    TaskStatus,
)

# Initialize structured logging
logger = structlog.get_logger()

# Global orchestrator instance
orchestrator: Optional[EnhancedOrchestrator] = None

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting DevOps Control Tower")

    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized")

        # Create and start orchestrator
        global orchestrator
        orchestrator = EnhancedOrchestrator()
        # ...
        # Temporary: disable infra monitoring agent for spine v0
        # infra_agent = InfrastructureMonitoringAgent()
        # orchestrator.register_agent("infrastructure_monitor", infra_agent)
        # ...
        await orchestrator.start()
        logger.info("Orchestrator started successfully")

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down DevOps Control Tower")
    if orchestrator:
        await orchestrator.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title="DevOps Control Tower",
    description="Centralized command center for AI-powered development operations",
    version=importlib.metadata.version("devops-control-tower"),
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """
    Basic health check endpoint.

    For spine v0 we just confirm the API is reachable and the app started.
    Later we can extend this to check DB/Redis, orchestrator, etc.
    """
    return {"status": "ok"}


# Health and Info Endpoints
@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    """Return the version of the application."""
    return {"version": importlib.metadata.version("devops-control-tower")}


@app.get("/status")
async def get_system_status() -> dict[str, Any]:
    """Get comprehensive system status."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    return {
        "orchestrator": {
            "status": "running" if orchestrator.is_running else "stopped",
            "agents_count": len(orchestrator.agents),
            "workflows_count": len(orchestrator.workflows),
            "running_tasks": len(orchestrator.running_tasks),
        },
        "agents": {
            name: {
                "status": agent.status,
                "health": getattr(agent, "_health_status", "unknown"),
            }
            for name, agent in orchestrator.agents.items()
        },
        "settings": {
            "environment": settings.environment,
            "debug": settings.debug,
            "max_concurrent_agents": settings.max_concurrent_agents,
        },
    }


# Agent Management Endpoints
@app.get("/agents")
async def list_agents() -> List[Dict[str, Any]]:
    """List all registered agents."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    agents = []
    for name, agent in orchestrator.agents.items():
        agents.append(
            {
                "name": name,
                "type": agent.__class__.__name__,
                "status": agent.status,
                "health": getattr(agent, "_health_status", "unknown"),
                "capabilities": getattr(agent, "capabilities", []),
                "description": getattr(agent, "description", ""),
            }
        )

    return agents


@app.get("/agents/{agent_name}")
async def get_agent(agent_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific agent."""
    if not orchestrator or agent_name not in orchestrator.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent = orchestrator.agents[agent_name]
    return {
        "name": agent.name,
        "type": agent.__class__.__name__,
        "status": agent.status,
        "health": getattr(agent, "_health_status", "unknown"),
        "capabilities": getattr(agent, "capabilities", []),
        "description": getattr(agent, "description", ""),
        "config": getattr(agent, "config", {}),
        "error_count": getattr(agent, "error_count", 0),
        "last_error": getattr(agent, "last_error", None),
    }


@app.post("/agents/{agent_name}/start")
async def start_agent(agent_name: str) -> Dict[str, str]:
    """Start a specific agent."""
    if not orchestrator or agent_name not in orchestrator.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        agent = orchestrator.agents[agent_name]
        await agent.start()
        return {"status": "success", "message": f"Agent {agent_name} started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")


@app.post("/agents/{agent_name}/stop")
async def stop_agent(agent_name: str) -> Dict[str, str]:
    """Stop a specific agent."""
    if not orchestrator or agent_name not in orchestrator.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        agent = orchestrator.agents[agent_name]
        await agent.stop()
        return {"status": "success", "message": f"Agent {agent_name} stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop agent: {str(e)}")


# Event Management Endpoints
@app.get("/events")
async def list_events(
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List events with optional filtering."""
    event_service = EventService(db)
    events = event_service.get_events(
        status=status,
        event_type=event_type,
        priority=priority,
        limit=limit,
        offset=offset,
    )

    return [event.to_dict() for event in events]


@app.get("/events/{event_id}")
async def get_event(event_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific event by ID."""
    event_service = EventService(db)
    event = event_service.get_event(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event.to_dict()


@app.post("/events")
async def create_event(
    event_type: str,
    source: str,
    data: Dict[str, Any],
    priority: str = "medium",
    tags: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Create a new event."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        # Create event object
        event_priority = EventPriority(priority.lower())
        event = Event(
            event_type=event_type,
            source=source,
            data=data,
            priority=event_priority,
            tags=tags or {},
        )

        # Submit to orchestrator
        event_id = await orchestrator.submit_event(event)

        return {
            "status": "success",
            "event_id": event_id,
            "message": "Event created and queued for processing",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid event data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")


# Task Management Endpoints (JCT V1 Task Spec)
@app.post("/tasks/enqueue", status_code=201)
async def enqueue_task(
    task_spec: TaskCreateV1, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Enqueue a task for execution.

    This endpoint implements the JCT V1 Task Spec. It creates a database row
    for the task and queues it for processing by a worker.

    For v0 spine: /tasks/enqueue → DB row → Worker → Trace folder
    """
    try:
        task_service = TaskService(db)
        db_task = task_service.create_task(task_spec)

        # For v0 spine, we create the DB row and immediately mark it as queued
        # Later: actual worker orchestration will be implemented
        task_service.update_task_status(str(db_task.id), "queued")

        return {
            "status": "success",
            "task_id": str(db_task.id),
            "message": "Task enqueued successfully",
            "task": db_task.to_dict(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid task data: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to enqueue task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue task: {str(e)}")


@app.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    operation: Optional[str] = None,
    requester_kind: Optional[str] = None,
    target_repo: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List tasks with optional filtering."""
    task_service = TaskService(db)
    tasks = task_service.get_tasks(
        status=status,
        operation=operation,
        requester_kind=requester_kind,
        target_repo=target_repo,
        limit=limit,
        offset=offset,
    )

    return [task.to_dict() for task in tasks]


@app.get("/tasks/{task_id}")
async def get_task(task_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific task by ID."""
    task_service = TaskService(db)
    task = task_service.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task.to_dict()


@app.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    status: str,
    assigned_to: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    trace_path: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update task status and execution details."""
    task_service = TaskService(db)
    task = task_service.update_task_status(
        task_id,
        status=status,
        assigned_to=assigned_to,
        result=result,
        error=error,
        trace_path=trace_path,
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"status": "success", "task": task.to_dict()}


# Workflow Management Endpoints
@app.get("/workflows")
async def list_workflows(
    active_only: bool = True, db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List all workflows."""
    workflow_service = WorkflowService(db)
    workflows = workflow_service.get_workflows(active_only=active_only)

    return [workflow.to_dict() for workflow in workflows]


@app.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get a specific workflow by ID."""
    workflow_service = WorkflowService(db)
    workflow = workflow_service.get_workflow(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return workflow.to_dict()


# Task Intake Endpoints (V1)
@app.post(
    "/tasks/enqueue",
    response_model=TaskResponseV1,
    status_code=201,
    tags=["tasks"],
    responses={
        201: {"description": "Task created and queued successfully"},
        400: {"description": "Invalid request (schema validation failed)"},
        403: {"description": "Policy violation"},
        409: {"description": "Conflict (duplicate idempotency_key)"},
        422: {"description": "Unprocessable entity"},
    },
)
async def enqueue_task(
    task: TaskCreateV1,
    db: Session = Depends(get_db),
) -> TaskResponseV1:
    """
    Enqueue a new task for processing.

    This is the intake endpoint for the task queue. It validates the task
    against schema and policy rules, persists it to the database with status
    'queued', and returns the task_id for tracking.

    No work is executed at this stage - this is a pure "courthouse" intake gate.
    """
    task_service = TaskService(db)

    # Check for idempotency key collision
    if task.idempotency_key:
        existing = task_service.get_task_by_idempotency_key(task.idempotency_key)
        if existing:
            # Return existing task info (idempotent behavior)
            logger.info(
                "Returning existing task for idempotency key",
                idempotency_key=task.idempotency_key,
                task_id=str(existing.id),
            )
            return TaskResponseV1(
                task_id=existing.id,
                status=TaskStatus(existing.status),
                created_at=existing.created_at,
            )

    # Validate against policy rules
    policy_result: PolicyResult = validate_task(task)
    if policy_result.denied:
        violation = policy_result.violations[0]
        logger.warning(
            "Task rejected by policy",
            violation_type=violation.violation_type.value,
            field=violation.field,
            value=violation.value,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": violation.violation_type.value,
                    "message": violation.message,
                    "details": {
                        "field": violation.field,
                        "value": violation.value,
                        "allowed": violation.allowed,
                    },
                }
            },
        )

    # Persist task to database
    try:
        db_task = task_service.create_task(task)
        logger.info(
            "Task enqueued successfully",
            task_id=str(db_task.id),
            type=task.type,
            priority=task.priority.value,
            source=task.source,
        )

        return TaskResponseV1(
            task_id=db_task.id,
            status=TaskStatus.QUEUED,
            created_at=db_task.created_at,
        )

    except Exception as e:
        logger.error("Failed to enqueue task", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to enqueue task",
                }
            },
        )


# Quick Actions and Testing Endpoints
@app.post("/test/infrastructure-alert")
async def create_test_infrastructure_alert() -> Dict[str, str]:
    """Create a test infrastructure alert for testing purposes."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    # Create a test event
    event = Event(
        event_type=EventTypes.INFRASTRUCTURE_ALERT,
        source="test-system",
        data={
            "alert_type": "high_cpu",
            "value": 95.5,
            "threshold": 80.0,
            "message": "CPU usage critically high on test system",
        },
        priority=EventPriority.HIGH,
        tags={"environment": "test", "component": "cpu"},
    )

    event_id = await orchestrator.submit_event(event)
    return {"status": "success", "event_id": event_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
