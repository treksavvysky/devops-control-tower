"""
Database services for DevOps Control Tower.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import desc
from sqlalchemy.orm import Session


@dataclass
class TaskCreateResult:
    """Result of task creation, indicating if task was new or existing (idempotency)."""
    task: "TaskModel"
    created: bool  # True if newly created, False if existing (idempotency hit)

from ..data.models.events import Event
from ..schemas.task_v1 import TaskCreateV1, TaskCreateLegacyV1
from .models import AgentModel, ArtifactModel, EventModel, JobModel, TaskModel, WorkflowModel


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
            error=event.error,
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
        offset: int = 0,
    ) -> List[EventModel]:
        """Get events with optional filtering."""
        query = self.db.query(EventModel)

        if status:
            query = query.filter(EventModel.status == status)
        if event_type:
            query = query.filter(EventModel.type == event_type)
        if priority:
            query = query.filter(EventModel.priority == priority)

        return (
            query.order_by(desc(EventModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_event_status(
        self,
        event_id: str,
        status: str,
        processed_by: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
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
        return (
            self.db.query(EventModel)
            .filter(EventModel.status == "pending")
            .order_by(EventModel.priority.desc(), EventModel.created_at)
            .limit(limit)
            .all()
        )


class WorkflowService:
    """Service for managing workflows in the database."""

    def __init__(self, db: Session):
        self.db = db

    def create_workflow(
        self, name: str, description: str = "", **kwargs
    ) -> WorkflowModel:
        """Create a new workflow."""
        db_workflow = WorkflowModel(
            name=name,
            description=description,
            trigger_events=kwargs.get("trigger_events", []),
            steps=kwargs.get("steps", []),
            is_active=kwargs.get("is_active", True),
            timeout_seconds=kwargs.get("timeout_seconds", 3600),
        )

        self.db.add(db_workflow)
        self.db.commit()
        self.db.refresh(db_workflow)
        return db_workflow

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowModel]:
        """Get a workflow by ID."""
        return (
            self.db.query(WorkflowModel).filter(WorkflowModel.id == workflow_id).first()
        )

    def get_workflow_by_name(self, name: str) -> Optional[WorkflowModel]:
        """Get a workflow by name."""
        return self.db.query(WorkflowModel).filter(WorkflowModel.name == name).first()

    def get_workflows(self, active_only: bool = True) -> List[WorkflowModel]:
        """Get all workflows, optionally filtered by active status."""
        query = self.db.query(WorkflowModel)
        if active_only:
            query = query.filter(WorkflowModel.is_active.is_(True))
        return query.order_by(WorkflowModel.name).all()

    def get_workflows_for_event(self, event_type: str) -> List[WorkflowModel]:
        """Get workflows that should be triggered by an event type."""
        return (
            self.db.query(WorkflowModel)
            .filter(WorkflowModel.is_active.is_(True))
            .filter(WorkflowModel.trigger_events.contains([event_type]))
            .all()
        )

    def update_workflow_execution(
        self,
        workflow_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
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
            max_concurrent_tasks=kwargs.get("max_concurrent_tasks", 5),
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

    def get_agents(
        self, agent_type: Optional[str] = None, enabled_only: bool = True
    ) -> List[AgentModel]:
        """Get agents with optional filtering."""
        query = self.db.query(AgentModel)

        if agent_type:
            query = query.filter(AgentModel.type == agent_type)
        if enabled_only:
            query = query.filter(AgentModel.is_enabled.is_(True))

        return query.order_by(AgentModel.name).all()

    def update_agent_status(
        self,
        agent_id: str,
        status: str,
        health_status: Optional[str] = None,
        health_details: Optional[Dict[str, Any]] = None,
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


class TaskService:
    """Service for managing tasks in the database (JCT V1 Task Spec)."""

    def __init__(self, db: Session):
        self.db = db

    def create_task(
        self, task_spec: TaskCreateLegacyV1, trace_id: Optional[str] = None
    ) -> TaskCreateResult:
        """Create a new task from V1 spec.

        Args:
            task_spec: The V1 task specification
            trace_id: Optional trace_id for end-to-end causality tracking (Sprint-0)

        Returns:
            TaskCreateResult with task and created flag (False = idempotency hit)
        """
        # Check for existing task with same idempotency key
        if task_spec.idempotency_key:
            existing = self.get_task_by_idempotency_key(task_spec.idempotency_key)
            if existing:
                return TaskCreateResult(task=existing, created=False)

        db_task = TaskModel(
            version=task_spec.version,
            idempotency_key=task_spec.idempotency_key,
            # requested_by
            requested_by_kind=task_spec.requested_by.kind,
            requested_by_id=task_spec.requested_by.id,
            requested_by_label=task_spec.requested_by.label,
            # task definition
            objective=task_spec.objective,
            operation=task_spec.operation,
            # target
            target_repo=task_spec.target.repo,
            target_ref=task_spec.target.ref,
            target_path=task_spec.target.path,
            # constraints
            time_budget_seconds=task_spec.constraints.time_budget_seconds,
            allow_network=task_spec.constraints.allow_network,
            allow_secrets=task_spec.constraints.allow_secrets,
            # data
            inputs=task_spec.inputs,
            task_metadata=task_spec.metadata,
            # status
            status="pending",
            # Sprint-0: trace_id for causality tracking
            trace_id=trace_id,
        )

        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)
        return TaskCreateResult(task=db_task, created=True)

    def get_task(self, task_id: Union[str, uuid.UUID]) -> Optional[TaskModel]:
        """Get a task by ID."""
        # Convert string to UUID if needed for SQLite compatibility
        if isinstance(task_id, str):
            try:
                task_id = uuid.UUID(task_id)
            except ValueError:
                return None
        return self.db.query(TaskModel).filter(TaskModel.id == task_id).first()

    def get_task_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[TaskModel]:
        """Get a task by idempotency key."""
        return (
            self.db.query(TaskModel)
            .filter(TaskModel.idempotency_key == idempotency_key)
            .first()
        )

    def get_tasks(
        self,
        status: Optional[str] = None,
        operation: Optional[str] = None,
        requester_kind: Optional[str] = None,
        target_repo: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TaskModel]:
        """Get tasks with optional filtering."""
        query = self.db.query(TaskModel)

        if status:
            query = query.filter(TaskModel.status == status)
        if operation:
            query = query.filter(TaskModel.operation == operation)
        if requester_kind:
            query = query.filter(TaskModel.requested_by_kind == requester_kind)
        if target_repo:
            query = query.filter(TaskModel.target_repo == target_repo)

        return (
            query.order_by(desc(TaskModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_task_status(
        self,
        task_id: str,
        status: str,
        assigned_to: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        trace_path: Optional[str] = None,
    ) -> Optional[TaskModel]:
        """Update task status and execution details."""
        task = self.get_task(task_id)
        if not task:
            return None

        task.status = status

        # Update timestamps based on status
        now = datetime.utcnow()
        if status == "queued" and not task.queued_at:
            task.queued_at = now
        elif status == "running" and not task.started_at:
            task.started_at = now
        elif status in ["completed", "failed", "cancelled"] and not task.completed_at:
            task.completed_at = now

        # Update other fields
        if assigned_to:
            task.assigned_to = assigned_to
        if result:
            task.result = result
        if error:
            task.error = error
        if trace_path:
            task.trace_path = trace_path

        self.db.commit()
        self.db.refresh(task)
        return task

    def get_pending_tasks(self, limit: int = 50) -> List[TaskModel]:
        """Get pending tasks for processing."""
        return (
            self.db.query(TaskModel)
            .filter(TaskModel.status == "pending")
            .order_by(TaskModel.created_at)
            .limit(limit)
            .all()
        )

    def get_queued_tasks(self, limit: int = 50) -> List[TaskModel]:
        """Get queued tasks ready for execution."""
        return (
            self.db.query(TaskModel)
            .filter(TaskModel.status == "queued")
            .order_by(TaskModel.created_at)
            .limit(limit)
            .all()
        )

    def get_task_by_trace_id(self, trace_id: str) -> Optional[TaskModel]:
        """Get a task by trace_id (Sprint-0)."""
        return (
            self.db.query(TaskModel)
            .filter(TaskModel.trace_id == trace_id)
            .first()
        )

    def get_tasks_by_trace_id(self, trace_id: str) -> List[TaskModel]:
        """Get all tasks with a given trace_id (Sprint-0)."""
        return (
            self.db.query(TaskModel)
            .filter(TaskModel.trace_id == trace_id)
            .order_by(TaskModel.created_at)
            .all()
        )


class JobService:
    """Service for managing jobs in the database (Sprint-0).

    A job represents a single execution attempt of a task.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_job(
        self,
        task_id: str,
        trace_id: str,
        job_id: Optional[str] = None,
    ) -> JobModel:
        """Create a new job for a task.

        Args:
            task_id: The task ID this job is for
            trace_id: The trace_id for causality tracking
            job_id: Optional custom job ID (defaults to UUID)
        """
        db_job = JobModel(
            id=job_id or str(uuid.uuid4()),
            task_id=task_id,
            trace_id=trace_id,
            status="pending",
        )

        self.db.add(db_job)
        self.db.commit()
        self.db.refresh(db_job)
        return db_job

    def get_job(self, job_id: str) -> Optional[JobModel]:
        """Get a job by ID."""
        return self.db.query(JobModel).filter(JobModel.id == job_id).first()

    def get_jobs_by_task(self, task_id: str) -> List[JobModel]:
        """Get all jobs for a task."""
        return (
            self.db.query(JobModel)
            .filter(JobModel.task_id == task_id)
            .order_by(desc(JobModel.created_at))
            .all()
        )

    def get_jobs_by_trace_id(self, trace_id: str) -> List[JobModel]:
        """Get all jobs with a given trace_id."""
        return (
            self.db.query(JobModel)
            .filter(JobModel.trace_id == trace_id)
            .order_by(JobModel.created_at)
            .all()
        )

    def claim_job(self, job_id: str, worker_id: str) -> Optional[JobModel]:
        """Claim a job for processing by a worker.

        Uses optimistic locking - only claims if status is 'pending'.
        """
        job = self.get_job(job_id)
        if not job or job.status != "pending":
            return None

        job.status = "claimed"
        job.worker_id = worker_id
        job.claimed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(job)
        return job

    def claim_next_pending_job(self, worker_id: str) -> Optional[JobModel]:
        """Claim the next pending job (FIFO order).

        This is a simple implementation. For production, use
        SELECT ... FOR UPDATE SKIP LOCKED for proper concurrency.
        """
        job = (
            self.db.query(JobModel)
            .filter(JobModel.status == "pending")
            .order_by(JobModel.created_at)
            .first()
        )

        if not job:
            return None

        return self.claim_job(job.id, worker_id)

    def start_job(self, job_id: str) -> Optional[JobModel]:
        """Mark a job as running."""
        job = self.get_job(job_id)
        if not job or job.status != "claimed":
            return None

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(job)
        return job

    def complete_job(
        self,
        job_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[JobModel]:
        """Mark a job as completed."""
        job = self.get_job(job_id)
        if not job or job.status != "running":
            return None

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        if result:
            job.result = result

        self.db.commit()
        self.db.refresh(job)
        return job

    def fail_job(
        self,
        job_id: str,
        error: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[JobModel]:
        """Mark a job as failed."""
        job = self.get_job(job_id)
        if not job:
            return None

        job.status = "failed"
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        job.error = error
        if result:
            job.result = result

        self.db.commit()
        self.db.refresh(job)
        return job

    def get_pending_jobs(self, limit: int = 50) -> List[JobModel]:
        """Get pending jobs for processing."""
        return (
            self.db.query(JobModel)
            .filter(JobModel.status == "pending")
            .order_by(JobModel.created_at)
            .limit(limit)
            .all()
        )


class ArtifactService:
    """Service for managing artifacts in the database (Sprint-0).

    Artifacts are outputs produced during task/job execution.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_artifact(
        self,
        task_id: str,
        trace_id: str,
        kind: str,
        job_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
        uri: Optional[str] = None,
        ref: Optional[str] = None,
        content: Optional[str] = None,
        content_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        checksum: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ArtifactModel:
        """Create a new artifact.

        Args:
            task_id: The task ID this artifact belongs to
            trace_id: The trace_id for causality tracking
            kind: Type of artifact (log, diff, report, file, metric, error)
            job_id: Optional job ID if artifact was produced by a job
            artifact_id: Optional custom artifact ID (defaults to UUID)
            uri: External reference (S3, file path, etc.)
            ref: Internal reference
            content: Inline content for small artifacts
            content_type: MIME type or content type description
            size_bytes: Size of the artifact content
            checksum: SHA256 or other checksum of content
            meta: Additional metadata
        """
        db_artifact = ArtifactModel(
            id=artifact_id or str(uuid.uuid4()),
            task_id=task_id,
            job_id=job_id,
            trace_id=trace_id,
            kind=kind,
            uri=uri,
            ref=ref,
            content=content,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum=checksum,
            meta=meta,
        )

        self.db.add(db_artifact)
        self.db.commit()
        self.db.refresh(db_artifact)
        return db_artifact

    def get_artifact(self, artifact_id: str) -> Optional[ArtifactModel]:
        """Get an artifact by ID."""
        return (
            self.db.query(ArtifactModel)
            .filter(ArtifactModel.id == artifact_id)
            .first()
        )

    def get_artifacts_by_task(self, task_id: str) -> List[ArtifactModel]:
        """Get all artifacts for a task."""
        return (
            self.db.query(ArtifactModel)
            .filter(ArtifactModel.task_id == task_id)
            .order_by(ArtifactModel.created_at)
            .all()
        )

    def get_artifacts_by_job(self, job_id: str) -> List[ArtifactModel]:
        """Get all artifacts for a job."""
        return (
            self.db.query(ArtifactModel)
            .filter(ArtifactModel.job_id == job_id)
            .order_by(ArtifactModel.created_at)
            .all()
        )

    def get_artifacts_by_trace_id(self, trace_id: str) -> List[ArtifactModel]:
        """Get all artifacts with a given trace_id."""
        return (
            self.db.query(ArtifactModel)
            .filter(ArtifactModel.trace_id == trace_id)
            .order_by(ArtifactModel.created_at)
            .all()
        )

    def get_artifacts_by_kind(
        self, task_id: str, kind: str
    ) -> List[ArtifactModel]:
        """Get artifacts of a specific kind for a task."""
        return (
            self.db.query(ArtifactModel)
            .filter(ArtifactModel.task_id == task_id)
            .filter(ArtifactModel.kind == kind)
            .order_by(ArtifactModel.created_at)
            .all()
        )
