"""
Sprint-0 Worker.

The Worker claims queued tasks, executes them via ActionRunner,
and creates artifacts with trace_id propagation throughout.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.orm import Session

from ..db.models import TaskModel
from ..db.services import ArtifactService, JobService, TaskService
from .action_runner import ActionRunner, StubActionRunner

logger = structlog.get_logger()


class Worker:
    """Sprint-0 Worker for processing queued tasks.

    The worker:
    1. Claims a queued task
    2. Creates a job record
    3. Executes the task via ActionRunner
    4. Creates artifact records
    5. Updates task/job status

    All operations propagate trace_id for end-to-end causality tracking.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        action_runner_class: type = StubActionRunner,
    ):
        """Initialize the worker.

        Args:
            worker_id: Unique identifier for this worker instance
            action_runner_class: Class to use for action execution
        """
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.action_runner_class = action_runner_class
        self.is_running = False
        self.logger = logger.bind(worker_id=self.worker_id)

    def process_task(self, db: Session, task: TaskModel) -> Dict[str, Any]:
        """Process a single task.

        Args:
            db: Database session
            task: The task to process

        Returns:
            Dict with processing results including job_id, artifacts, etc.
        """
        trace_id = task.trace_id or str(uuid.uuid4())
        task_id = str(task.id)

        # Bind trace_id to logger for all subsequent logs
        task_logger = self.logger.bind(trace_id=trace_id, task_id=task_id)
        task_logger.info("task_process_start", operation=task.operation)

        # Initialize services
        task_service = TaskService(db)
        job_service = JobService(db)
        artifact_service = ArtifactService(db)

        # Step 1: Create job record
        job = job_service.create_job(task_id=task_id, trace_id=trace_id)
        job_id = job.id
        task_logger = task_logger.bind(job_id=job_id)
        task_logger.info("job_created")

        # Step 2: Claim the job
        job = job_service.claim_job(job_id, self.worker_id)
        if not job:
            task_logger.error("job_claim_failed")
            return {"error": "Failed to claim job"}

        task_logger.info("job_claimed")

        # Step 3: Mark task and job as running
        task_service.update_task_status(task_id, "running", assigned_to=self.worker_id)
        job = job_service.start_job(job_id)
        task_logger.info("task_running")

        # Step 4: Execute the task via ActionRunner
        try:
            action_runner = self.action_runner_class(
                trace_id=trace_id,
                task_id=task_id,
                job_id=job_id,
            )

            # Prepare inputs and constraints
            inputs = task.inputs or {}
            constraints = {
                "time_budget_seconds": task.time_budget_seconds,
                "allow_network": task.allow_network,
                "allow_secrets": task.allow_secrets,
            }

            # Execute the action (using operation as action name)
            action_result = action_runner.execute(
                action_name=task.operation,
                inputs=inputs,
                constraints=constraints,
            )

            task_logger.info(
                "action_executed",
                success=action_result.success,
                artifacts_count=len(action_result.artifacts),
            )

            # Step 5: Create artifact records
            created_artifacts = []
            for artifact_data in action_result.artifacts:
                artifact = artifact_service.create_artifact(
                    task_id=task_id,
                    job_id=job_id,
                    trace_id=trace_id,
                    kind=artifact_data.get("kind", "log"),
                    uri=artifact_data.get("uri"),
                    ref=artifact_data.get("ref"),
                    content=artifact_data.get("content"),
                    content_type=artifact_data.get("content_type"),
                    size_bytes=artifact_data.get("size_bytes"),
                    checksum=artifact_data.get("checksum"),
                    meta=artifact_data.get("meta"),
                )
                created_artifacts.append(artifact.to_dict())
                task_logger.info(
                    "artifact_created",
                    artifact_id=artifact.id,
                    kind=artifact.kind,
                )

            # Step 6: Update task and job status based on result
            if action_result.success:
                job = job_service.complete_job(job_id, result=action_result.result)
                task_service.update_task_status(
                    task_id,
                    "completed",
                    result=action_result.result,
                )
                task_logger.info("task_completed")
            else:
                job = job_service.fail_job(
                    job_id,
                    error=action_result.error or "Unknown error",
                    result=action_result.result,
                )
                task_service.update_task_status(
                    task_id,
                    "failed",
                    error=action_result.error,
                    result=action_result.result,
                )
                task_logger.info("task_failed", error=action_result.error)

            return {
                "task_id": task_id,
                "job_id": job_id,
                "trace_id": trace_id,
                "status": "completed" if action_result.success else "failed",
                "result": action_result.result,
                "error": action_result.error,
                "artifacts": created_artifacts,
            }

        except Exception as e:
            task_logger.exception("task_process_error", error=str(e))

            # Mark job and task as failed
            job_service.fail_job(job_id, error=str(e))
            task_service.update_task_status(task_id, "failed", error=str(e))

            # Create error artifact
            error_artifact = artifact_service.create_artifact(
                task_id=task_id,
                job_id=job_id,
                trace_id=trace_id,
                kind="error",
                ref=f"worker_exception_{job_id}",
                content=f"Worker exception: {str(e)}",
                content_type="text/plain",
            )

            return {
                "task_id": task_id,
                "job_id": job_id,
                "trace_id": trace_id,
                "status": "failed",
                "error": str(e),
                "artifacts": [error_artifact.to_dict()],
            }

    def claim_and_process_one(self, db: Session) -> Optional[Dict[str, Any]]:
        """Claim and process one queued task.

        This is the main entry point for single-task processing.

        Args:
            db: Database session

        Returns:
            Processing result dict, or None if no tasks available
        """
        self.logger.info("worker_looking_for_task")

        # Find a queued task
        task_service = TaskService(db)
        tasks = task_service.get_queued_tasks(limit=1)

        if not tasks:
            self.logger.info("no_queued_tasks")
            return None

        task = tasks[0]
        self.logger.info(
            "task_found",
            task_id=str(task.id),
            trace_id=task.trace_id,
            operation=task.operation,
        )

        return self.process_task(db, task)

    async def run_loop(
        self,
        db_session_factory,
        poll_interval: float = 1.0,
        max_tasks: Optional[int] = None,
    ):
        """Run the worker in a continuous loop.

        Args:
            db_session_factory: Factory function that returns a new DB session
            poll_interval: Seconds between polling for new tasks
            max_tasks: Maximum tasks to process (None = unlimited)
        """
        self.is_running = True
        tasks_processed = 0

        self.logger.info("worker_loop_started", poll_interval=poll_interval)

        try:
            while self.is_running:
                if max_tasks and tasks_processed >= max_tasks:
                    self.logger.info(
                        "worker_max_tasks_reached",
                        tasks_processed=tasks_processed,
                    )
                    break

                # Get a new session for each iteration
                db = db_session_factory()
                try:
                    result = self.claim_and_process_one(db)
                    if result:
                        tasks_processed += 1
                        self.logger.info(
                            "worker_task_processed",
                            task_id=result.get("task_id"),
                            trace_id=result.get("trace_id"),
                            status=result.get("status"),
                            total_processed=tasks_processed,
                        )
                    else:
                        # No tasks available, wait before polling again
                        await asyncio.sleep(poll_interval)
                finally:
                    db.close()

        except Exception as e:
            self.logger.exception("worker_loop_error", error=str(e))
            raise
        finally:
            self.is_running = False
            self.logger.info(
                "worker_loop_stopped",
                tasks_processed=tasks_processed,
            )

    def stop(self):
        """Signal the worker to stop."""
        self.logger.info("worker_stop_requested")
        self.is_running = False
