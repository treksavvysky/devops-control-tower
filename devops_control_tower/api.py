"""
Enhanced FastAPI application with full API endpoints.
"""

from __future__ import annotations

import importlib.metadata
import asyncio
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import structlog

from .core.enhanced_orchestrator import EnhancedOrchestrator
from .agents.implementations import InfrastructureMonitoringAgent
from .db.base import get_db, init_database
from .db.services import EventService, WorkflowService, AgentService
from .data.models.events import Event, EventTypes, EventPriority
from .config import get_settings

# Initialize structured logging
logger = structlog.get_logger()

# Global orchestrator instance
orchestrator: Optional[EnhancedOrchestrator] = None

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    lifespan=lifespan
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
            "running_tasks": len(orchestrator.running_tasks)
        },
        "agents": {
            name: {"status": agent.status, "health": getattr(agent, '_health_status', 'unknown')}
            for name, agent in orchestrator.agents.items()
        },
        "settings": {
            "environment": settings.environment,
            "debug": settings.debug,
            "max_concurrent_agents": settings.max_concurrent_agents
        }
    }


# Agent Management Endpoints
@app.get("/agents")
async def list_agents() -> List[Dict[str, Any]]:
    """List all registered agents."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    agents = []
    for name, agent in orchestrator.agents.items():
        agents.append({
            "name": name,
            "type": agent.__class__.__name__,
            "status": agent.status,
            "health": getattr(agent, '_health_status', 'unknown'),
            "capabilities": getattr(agent, 'capabilities', []),
            "description": getattr(agent, 'description', '')
        })
    
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
        "health": getattr(agent, '_health_status', 'unknown'),
        "capabilities": getattr(agent, 'capabilities', []),
        "description": getattr(agent, 'description', ''),
        "config": getattr(agent, 'config', {}),
        "error_count": getattr(agent, 'error_count', 0),
        "last_error": getattr(agent, 'last_error', None)
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
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List events with optional filtering."""
    event_service = EventService(db)
    events = event_service.get_events(
        status=status,
        event_type=event_type,
        priority=priority,
        limit=limit,
        offset=offset
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
    tags: Optional[Dict[str, str]] = None
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
            tags=tags or {}
        )
        
        # Submit to orchestrator
        event_id = await orchestrator.submit_event(event)
        
        return {
            "status": "success",
            "event_id": event_id,
            "message": "Event created and queued for processing"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid event data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")


# Workflow Management Endpoints  
@app.get("/workflows")
async def list_workflows(
    active_only: bool = True,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List all workflows."""
    workflow_service = WorkflowService(db)
    workflows = workflow_service.get_workflows(active_only=active_only)
    
    return [workflow.to_dict() for workflow in workflows]


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get a specific workflow by ID."""
    workflow_service = WorkflowService(db)
    workflow = workflow_service.get_workflow(workflow_id)
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return workflow.to_dict()


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
            "message": "CPU usage critically high on test system"
        },
        priority=EventPriority.HIGH,
        tags={"environment": "test", "component": "cpu"}
    )
    
    event_id = await orchestrator.submit_event(event)
    return {"status": "success", "event_id": event_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
