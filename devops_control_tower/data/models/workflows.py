"""
Workflow models for the DevOps Control Tower.
"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
import uuid
import asyncio

from .events import Event, EventTypes


class WorkflowStatus(Enum):
    """Workflow execution status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Individual step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStep:
    """Represents a single step in a workflow."""
    
    def __init__(
        self,
        name: str,
        action: Callable,
        description: str = "",
        timeout: int = 300,
        retry_count: int = 0,
        dependencies: Optional[List[str]] = None
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.action = action
        self.description = description
        self.timeout = timeout
        self.retry_count = retry_count
        self.dependencies = dependencies or []
        self.status = StepStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.attempts = 0
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        """Execute this workflow step."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.attempts += 1
        
        try:
            # Execute with timeout
            self.result = await asyncio.wait_for(
                self.action(context),
                timeout=self.timeout
            )
            
            self.status = StepStatus.COMPLETED
            self.completed_at = datetime.utcnow()
            return self.result
            
        except asyncio.TimeoutError:
            self.status = StepStatus.FAILED
            self.error = f"Step timed out after {self.timeout} seconds"
            raise
            
        except Exception as e:
            self.status = StepStatus.FAILED
            self.error = str(e)
            
            # Retry if attempts remaining
            if self.attempts <= self.retry_count:
                await asyncio.sleep(2 ** self.attempts)  # Exponential backoff
                return await self.execute(context)
            
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of this step."""
        duration = None
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
        
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": duration,
            "attempts": self.attempts,
            "error": self.error,
            "dependencies": self.dependencies
        }


class Workflow:
    """
    Represents a workflow - a series of automated steps triggered by events.
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        trigger_events: Optional[List[str]] = None,
        trigger_conditions: Optional[Callable[[Event], bool]] = None
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.trigger_events = trigger_events or []
        self.trigger_conditions = trigger_conditions
        self.steps: List[WorkflowStep] = []
        self.status = WorkflowStatus.IDLE
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.current_step_index = 0
        self.execution_context: Dict[str, Any] = {}
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.execution_count = 0
    
    def add_step(self, step: WorkflowStep) -> None:
        """Add a step to the workflow."""
        self.steps.append(step)
    
    def is_triggered_by(self, event: Event) -> bool:
        """Check if this workflow should be triggered by the given event."""
        # Check event type match
        if event.type not in self.trigger_events:
            return False
        
        # Check additional conditions if any
        if self.trigger_conditions:
            return self.trigger_conditions(event)
        
        return True
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        """Execute the workflow."""
        if self.status == WorkflowStatus.RUNNING:
            raise RuntimeError(f"Workflow {self.name} is already running")
        
        self.status = WorkflowStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.current_step_index = 0
        self.execution_context = context.copy()
        self.execution_count += 1
        
        try:
            # Execute each step in order
            for i, step in enumerate(self.steps):
                self.current_step_index = i
                
                # Check dependencies
                if not await self._check_dependencies(step):
                    step.status = StepStatus.SKIPPED
                    continue
                
                # Execute the step
                step_result = await step.execute(self.execution_context)
                
                # Add step result to context for subsequent steps
                self.execution_context[f"step_{step.name}_result"] = step_result
            
            self.status = WorkflowStatus.COMPLETED
            self.completed_at = datetime.utcnow()
            
            # Set final result as the context
            self.result = self.execution_context
            return self.result
            
        except Exception as e:
            self.status = WorkflowStatus.FAILED
            self.error = str(e)
            self.completed_at = datetime.utcnow()
            raise
    
    async def cancel(self) -> None:
        """Cancel the workflow execution."""
        if self.status == WorkflowStatus.RUNNING:
            self.status = WorkflowStatus.CANCELLED
            self.completed_at = datetime.utcnow()
    
    async def _check_dependencies(self, step: WorkflowStep) -> bool:
        """Check if all dependencies for a step are satisfied."""
        for dep_name in step.dependencies:
            # Find the dependency step
            dep_step = next((s for s in self.steps if s.name == dep_name), None)
            if not dep_step:
                raise ValueError(f"Dependency step '{dep_name}' not found")
            
            # Check if dependency completed successfully
            if dep_step.status != StepStatus.COMPLETED:
                return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the workflow."""
        duration = None
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
        
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": duration,
            "current_step_index": self.current_step_index,
            "total_steps": len(self.steps),
            "execution_count": self.execution_count,
            "error": self.error,
            "trigger_events": self.trigger_events,
            "steps": [step.get_status() for step in self.steps]
        }


class WorkflowBuilder:
    """Builder class for creating workflows with a fluent interface."""
    
    def __init__(self, name: str, description: str = ""):
        self.workflow = Workflow(name, description)
    
    def triggered_by(self, *event_types: str) -> "WorkflowBuilder":
        """Set the event types that trigger this workflow."""
        self.workflow.trigger_events.extend(event_types)
        return self
    
    def with_condition(self, condition: Callable[[Event], bool]) -> "WorkflowBuilder":
        """Add a trigger condition function."""
        self.workflow.trigger_conditions = condition
        return self
    
    def add_step(
        self,
        name: str,
        action: Callable,
        description: str = "",
        timeout: int = 300,
        retry_count: int = 0,
        dependencies: Optional[List[str]] = None
    ) -> "WorkflowBuilder":
        """Add a step to the workflow."""
        step = WorkflowStep(
            name=name,
            action=action,
            description=description,
            timeout=timeout,
            retry_count=retry_count,
            dependencies=dependencies
        )
        self.workflow.add_step(step)
        return self
    
    def build(self) -> Workflow:
        """Build and return the completed workflow."""
        return self.workflow


# Pre-built workflow templates
class WorkflowTemplates:
    """Common workflow templates."""
    
    @staticmethod
    def incident_response() -> Workflow:
        """Create an incident response workflow."""
        return (WorkflowBuilder("incident_response", "Automated incident response workflow")
                .triggered_by(EventTypes.INFRASTRUCTURE_FAILURE, EventTypes.SERVICE_DOWN)
                .add_step("assess_impact", lambda ctx: {"severity": "high"})
                .add_step("notify_team", lambda ctx: {"notified": True}, dependencies=["assess_impact"])
                .add_step("start_mitigation", lambda ctx: {"mitigated": True}, dependencies=["notify_team"])
                .build())
    
    @staticmethod
    def deployment_pipeline() -> Workflow:
        """Create a deployment pipeline workflow."""
        return (WorkflowBuilder("deployment_pipeline", "Automated deployment pipeline")
                .triggered_by(EventTypes.CODE_COMMIT)
                .add_step("run_tests", lambda ctx: {"tests_passed": True})
                .add_step("build_image", lambda ctx: {"image": "app:latest"}, dependencies=["run_tests"])
                .add_step("deploy_staging", lambda ctx: {"deployed": True}, dependencies=["build_image"])
                .add_step("run_e2e_tests", lambda ctx: {"e2e_passed": True}, dependencies=["deploy_staging"])
                .add_step("deploy_production", lambda ctx: {"production_deployed": True}, dependencies=["run_e2e_tests"])
                .build())
    
    @staticmethod
    def security_scan() -> Workflow:
        """Create a security scanning workflow."""
        return (WorkflowBuilder("security_scan", "Automated security scanning workflow")
                .triggered_by(EventTypes.CODE_COMMIT, EventTypes.DEPLOYMENT_COMPLETED)
                .add_step("scan_vulnerabilities", lambda ctx: {"vulnerabilities": []})
                .add_step("scan_secrets", lambda ctx: {"secrets_found": False})
                .add_step("compliance_check", lambda ctx: {"compliant": True})
                .add_step("generate_report", lambda ctx: {"report": "security_report.pdf"}, 
                         dependencies=["scan_vulnerabilities", "scan_secrets", "compliance_check"])
                .build())
