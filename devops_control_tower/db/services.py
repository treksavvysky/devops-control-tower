"""
Database services for DevOps Control Tower.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from .models import EventModel, WorkflowModel, AgentModel
from ..data.models.events import Event, EventPriority, EventStatus


class EventService:
    """Service for managing events in the database."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_event(self, event: Event) -> EventModel:
        """Create a new event in the database."""
        db_event = EventModel(
            id=event.id,
            type=event.type,
            source=event.source,
            data=event.data,
            priority=event.priority.value,
            tags=event.tags,
            status=event.status.value,
            created_at=event.created_at,
            processed_at=event.processed_at,
            processed_by=event.processed_by,
            result=event.result,
            error=event.error
        )
        
        self.db.add(db_event)
        self.db.commit()
        self.db.refresh(db_event)
        return db_event
    
    def get_event(self, event_id: str) -> Optional[EventModel]:
        """Get an event by ID."""
        return self.db.query(EventModel).filter(EventModel.id == event_id).first()
    
    def get_events(
        self, 
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[EventModel]:
        """Get events with optional filtering."""
        query = self.db.query(EventModel)
        
        if status:
            query = query.filter(EventModel.status == status)
        if event_type:
            query = query.filter(EventModel.type == event_type)
        if priority:
            query = query.filter(EventModel.priority == priority)
        
        return query.order_by(desc(EventModel.created_at)).offset(offset).limit(limit).all()
    
    def update_event_status(
        self, 
        event_id: str, 
        status: str,
        processed_by: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Optional[EventModel]:
        """Update event status and processing details."""
        event = self.get_event(event_id)
        if not event:
            return None
        
        event.status = status
        if processed_by:
            event.processed_by = processed_by
            event.processed_at = datetime.utcnow()
        if result:
            event.result = result
        if error:
            event.error = error
        
        self.db.commit()
        self.db.refresh(event)
        return event
    
    def get_pending_events(self, limit: int = 50) -> List[EventModel]:
        """Get pending events for processing."""
        return (self.db.query(EventModel)
                .filter(EventModel.status == "pending")
                .order_by(EventModel.priority.desc(), EventModel.created_at)
                .limit(limit)
                .all())


class WorkflowService:
    """Service for managing workflows in the database."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_workflow(self, name: str, description: str = "", **kwargs) -> WorkflowModel:
        """Create a new workflow."""
        db_workflow = WorkflowModel(
            name=name,
            description=description,
            trigger_events=kwargs.get("trigger_events", []),
            steps=kwargs.get("steps", []),
            is_active=kwargs.get("is_active", True),
            timeout_seconds=kwargs.get("timeout_seconds", 3600)
        )
        
        self.db.add(db_workflow)
        self.db.commit()
        self.db.refresh(db_workflow)
        return db_workflow
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowModel]:
        """Get a workflow by ID."""
        return self.db.query(WorkflowModel).filter(WorkflowModel.id == workflow_id).first()
    
    def get_workflow_by_name(self, name: str) -> Optional[WorkflowModel]:
        """Get a workflow by name."""
        return self.db.query(WorkflowModel).filter(WorkflowModel.name == name).first()
    
    def get_workflows(self, active_only: bool = True) -> List[WorkflowModel]:
        """Get all workflows, optionally filtered by active status."""
        query = self.db.query(WorkflowModel)
        if active_only:
            query = query.filter(WorkflowModel.is_active == True)
        return query.order_by(WorkflowModel.name).all()
    
    def get_workflows_for_event(self, event_type: str) -> List[WorkflowModel]:
        """Get workflows that should be triggered by an event type."""
        return (self.db.query(WorkflowModel)
                .filter(WorkflowModel.is_active == True)
                .filter(WorkflowModel.trigger_events.contains([event_type]))
                .all())
    
    def update_workflow_execution(
        self, 
        workflow_id: str, 
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Optional[WorkflowModel]:
        """Update workflow execution status."""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None
        
        workflow.status = status
        workflow.last_executed_at = datetime.utcnow()
        
        if status == "running":
            workflow.execution_count += 1
        elif status in ["completed", "failed"]:
            workflow.last_result = result
            workflow.last_error = error
        
        self.db.commit()
        self.db.refresh(workflow)
        return workflow


class AgentService:
    """Service for managing agents in the database."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_agent(self, name: str, agent_type: str, **kwargs) -> AgentModel:
        """Create a new agent."""
        db_agent = AgentModel(
            name=name,
            type=agent_type,
            description=kwargs.get("description", ""),
            config=kwargs.get("config", {}),
            capabilities=kwargs.get("capabilities", []),
            is_enabled=kwargs.get("is_enabled", True),
            max_concurrent_tasks=kwargs.get("max_concurrent_tasks", 5)
        )
        
        self.db.add(db_agent)
        self.db.commit()
        self.db.refresh(db_agent)
        return db_agent
    
    def get_agent(self, agent_id: str) -> Optional[AgentModel]:
        """Get an agent by ID."""
        return self.db.query(AgentModel).filter(AgentModel.id == agent_id).first()
    
    def get_agent_by_name(self, name: str) -> Optional[AgentModel]:
        """Get an agent by name."""
        return self.db.query(AgentModel).filter(AgentModel.name == name).first()
    
    def get_agents(self, agent_type: Optional[str] = None, enabled_only: bool = True) -> List[AgentModel]:
        """Get agents with optional filtering."""
        query = self.db.query(AgentModel)
        
        if agent_type:
            query = query.filter(AgentModel.type == agent_type)
        if enabled_only:
            query = query.filter(AgentModel.is_enabled == True)
        
        return query.order_by(AgentModel.name).all()
    
    def update_agent_status(
        self, 
        agent_id: str, 
        status: str,
        health_status: Optional[str] = None,
        health_details: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentModel]:
        """Update agent status and health."""
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        agent.status = status
        agent.last_activity_at = datetime.utcnow()
        
        if status == "running":
            agent.started_at = datetime.utcnow()
            agent.last_heartbeat = datetime.utcnow()
        
        if health_status:
            agent.health_status = health_status
        if health_details:
            agent.health_details = health_details
        
        self.db.commit()
        self.db.refresh(agent)
        return agent
    
    def record_agent_heartbeat(self, agent_id: str) -> Optional[AgentModel]:
        """Record agent heartbeat."""
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        agent.last_heartbeat = datetime.utcnow()
        agent.last_activity_at = datetime.utcnow()
        
        self.db.commit()
        return agent