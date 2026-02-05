"""
JCT Worker Loop - processes queued tasks.

v0 spine: queued task → Worker → trace folder

Flow:
1. Poll: Find tasks with status='queued'
2. Claim: Atomically update status to 'running'
3. Create Run: CWOM Run with status='running'
4. Execute: Run through executor (StubExecutor for v0)
5. Write trace: Trace folder with manifest, events, artifacts
6. Complete: Update task and run status
"""
from __future__ import annotations

import logging
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.base import SessionLocal
from ..db.cwom_models import (
    CWOMRunModel,
    CWOMArtifactModel,
    CWOMContextPacketModel,
    CWOMConstraintSnapshotModel,
    CWOMIssueModel,
)
from ..db.models import TaskModel
from ..db.audit_service import AuditService
from .executor import ExecutionContext, ExecutionResult, get_executor
from .prover import Prover
from .storage import create_trace_store, get_trace_uri

logger = logging.getLogger(__name__)


class WorkerLoop:
    """Main worker loop for processing queued tasks."""

    def __init__(
        self,
        executor_type: str = "stub",
        poll_interval: Optional[int] = None,
        claim_limit: Optional[int] = None,
    ):
        """Initialize worker loop.

        Args:
            executor_type: Type of executor to use
            poll_interval: Seconds between poll cycles (default from config)
            claim_limit: Max tasks to claim per cycle (default from config)
        """
        self.settings = get_settings()
        self.executor = get_executor(executor_type)
        self.poll_interval = poll_interval or self.settings.worker_poll_interval
        self.claim_limit = claim_limit or self.settings.worker_claim_limit
        self.running = False
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"

        logger.info(
            f"Worker initialized: id={self.worker_id}, "
            f"executor={self.executor.name}, "
            f"poll_interval={self.poll_interval}s, "
            f"claim_limit={self.claim_limit}"
        )

    def start(self) -> None:
        """Start the worker loop. Runs until stopped."""
        self.running = True
        logger.info(f"Worker {self.worker_id} starting...")

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            while self.running:
                try:
                    tasks_processed = self._poll_and_process()
                    if tasks_processed == 0:
                        # No tasks found, sleep before next poll
                        time.sleep(self.poll_interval)
                except Exception as e:
                    logger.exception(f"Error in worker loop: {e}")
                    # Sleep on error to avoid tight loop
                    time.sleep(self.poll_interval)
        finally:
            logger.info(f"Worker {self.worker_id} stopped")

    def stop(self) -> None:
        """Signal the worker to stop after current task."""
        logger.info(f"Worker {self.worker_id} stopping...")
        self.running = False

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def _poll_and_process(self) -> int:
        """Poll for queued tasks and process them.

        Returns:
            Number of tasks processed
        """
        db = SessionLocal()
        try:
            # Find and claim queued tasks
            task = self._claim_task(db)
            if task is None:
                return 0

            logger.info(f"Claimed task {task.id}")

            # Process the task
            self._process_task(db, task)
            return 1

        finally:
            db.close()

    def _claim_task(self, db: Session) -> Optional[TaskModel]:
        """Atomically claim a queued task.

        Uses optimistic locking via status check in UPDATE.

        Args:
            db: Database session

        Returns:
            TaskModel if claimed, None if no tasks available
        """
        # Find oldest queued task
        task = (
            db.query(TaskModel)
            .filter(TaskModel.status == "queued")
            .order_by(TaskModel.queued_at.asc())
            .first()
        )

        if task is None:
            return None

        # Atomically claim it (optimistic locking)
        # Only update if status is still 'queued'
        result = db.execute(
            text("""
                UPDATE tasks
                SET status = 'running',
                    started_at = :started_at,
                    assigned_to = :worker_id
                WHERE id = :task_id AND status = 'queued'
            """),
            {
                "task_id": str(task.id),
                "started_at": datetime.now(timezone.utc),
                "worker_id": self.worker_id,
            }
        )
        db.commit()

        if result.rowcount == 0:
            # Another worker claimed it
            logger.debug(f"Task {task.id} claimed by another worker")
            return None

        # Refresh to get updated values
        db.refresh(task)
        return task

    def _process_task(self, db: Session, task: TaskModel) -> None:
        """Process a claimed task.

        Args:
            db: Database session
            task: Task to process
        """
        run: Optional[CWOMRunModel] = None
        store = None

        try:
            # Create CWOM Run if task has linked issue
            run = self._create_run(db, task)

            # Set up trace storage
            trace_uri = get_trace_uri(
                self.settings.jct_trace_root,
                str(run.id) if run else str(task.id)
            )
            store = create_trace_store(
                self.settings.jct_trace_root,
                str(run.id) if run else str(task.id)
            )

            # Update run with artifact URI
            if run:
                run.artifact_root_uri = trace_uri
                db.commit()

            # Build execution context
            context = self._build_context(db, task, run)

            # Write initial manifest
            self._write_initial_manifest(store, task, run, context)

            # Execute
            logger.info(f"Executing task {task.id} with {self.executor.name} executor")
            result = self.executor.execute(context, store)

            # Handle result
            self._handle_result(db, task, run, store, result)

        except Exception as e:
            logger.exception(f"Error processing task {task.id}: {e}")
            self._handle_failure(db, task, run, store, str(e))

    def _create_run(self, db: Session, task: TaskModel) -> Optional[CWOMRunModel]:
        """Create CWOM Run for the task.

        Args:
            db: Database session
            task: Task to create run for

        Returns:
            CWOMRunModel if task has linked issue, None otherwise
        """
        if not task.cwom_issue_id:
            logger.info(f"Task {task.id} has no CWOM issue, skipping run creation")
            return None

        # Get linked issue
        issue = db.query(CWOMIssueModel).filter(
            CWOMIssueModel.id == task.cwom_issue_id
        ).first()

        if not issue:
            logger.warning(
                f"Task {task.id} references missing issue {task.cwom_issue_id}"
            )
            return None

        # Create run
        run_id = str(uuid.uuid4())
        run = CWOMRunModel(
            id=run_id,
            kind="Run",
            trace_id=task.trace_id,
            for_issue_id=issue.id,
            for_issue_kind="Issue",
            repo_id=issue.repo_id,
            repo_kind="Repo",
            status="running",
            mode="system",  # Worker is system-driven
            executor={
                "type": self.executor.name,
                "version": self.executor.version,
                "worker_id": self.worker_id,
            },
            inputs={
                "task_id": str(task.id),
                "operation": task.operation,
            },
            plan={},
            telemetry={},
            cost={},
            outputs={},
        )

        db.add(run)

        # Update issue status to running
        issue.status = "running"

        # Audit log
        audit = AuditService(db)
        audit.log_create(
            entity_kind="Run",
            entity_id=run_id,
            after=run.to_dict(),
            actor_kind="system",
            actor_id=self.worker_id,
            note=f"Run created for task {task.id}",
            trace_id=task.trace_id,
        )

        db.commit()
        logger.info(f"Created run {run_id} for task {task.id}")

        return run

    def _build_context(
        self, db: Session, task: TaskModel, run: Optional[CWOMRunModel]
    ) -> ExecutionContext:
        """Build execution context from task and CWOM objects.

        Args:
            db: Database session
            task: Task being executed
            run: CWOM Run (if created)

        Returns:
            ExecutionContext for executor
        """
        context_packet = None
        constraint_snapshot = None

        if run:
            # Load context packet if available
            cp = db.query(CWOMContextPacketModel).filter(
                CWOMContextPacketModel.for_issue_id == run.for_issue_id
            ).first()
            if cp:
                context_packet = cp.to_dict()

            # Load constraint snapshot if linked
            if run.constraint_snapshot_id:
                cs = db.query(CWOMConstraintSnapshotModel).filter(
                    CWOMConstraintSnapshotModel.id == run.constraint_snapshot_id
                ).first()
                if cs:
                    constraint_snapshot = cs.to_dict()

        return ExecutionContext(
            task_id=str(task.id),
            run_id=str(run.id) if run else str(task.id),
            trace_id=task.trace_id,
            objective=task.objective,
            operation=task.operation,
            target_repo=task.target_repo,
            target_ref=task.target_ref,
            target_path=task.target_path,
            time_budget_seconds=task.time_budget_seconds,
            allow_network=task.allow_network,
            allow_secrets=task.allow_secrets,
            inputs=task.inputs or {},
            metadata=task.task_metadata or {},
            context_packet=context_packet,
            constraint_snapshot=constraint_snapshot,
        )

    def _write_initial_manifest(
        self,
        store,
        task: TaskModel,
        run: Optional[CWOMRunModel],
        context: ExecutionContext,
    ) -> None:
        """Write initial manifest.json to trace folder.

        Args:
            store: TraceStore instance
            task: Task being executed
            run: CWOM Run (if created)
            context: Execution context
        """
        manifest = {
            "version": "1.0",
            "task_id": str(task.id),
            "run_id": str(run.id) if run else None,
            "trace_id": task.trace_id,
            "worker_id": self.worker_id,
            "executor": {
                "name": self.executor.name,
                "version": self.executor.version,
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "task": {
                "objective": task.objective,
                "operation": task.operation,
                "target": {
                    "repo": task.target_repo,
                    "ref": task.target_ref,
                    "path": task.target_path,
                },
                "constraints": {
                    "time_budget_seconds": task.time_budget_seconds,
                    "allow_network": task.allow_network,
                    "allow_secrets": task.allow_secrets,
                },
            },
        }

        store.write_json("manifest.json", manifest)

        # Write context snapshot if available
        if context.context_packet:
            store.write_json("context.json", context.context_packet)

        if context.constraint_snapshot:
            store.write_json("constraints.json", context.constraint_snapshot)

    def _handle_result(
        self,
        db: Session,
        task: TaskModel,
        run: Optional[CWOMRunModel],
        store,
        result: ExecutionResult,
    ) -> None:
        """Handle successful execution result.

        Args:
            db: Database session
            task: Task that was executed
            run: CWOM Run (if created)
            store: TraceStore instance
            result: Execution result from executor
        """
        now = datetime.now(timezone.utc)

        # Update manifest
        manifest = {
            "version": "1.0",
            "task_id": str(task.id),
            "run_id": str(run.id) if run else None,
            "trace_id": task.trace_id,
            "worker_id": self.worker_id,
            "executor": {
                "name": self.executor.name,
                "version": self.executor.version,
            },
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": now.isoformat(),
            "duration_seconds": result.duration_seconds,
            "status": "completed" if result.success else "failed",
            "result": {
                "success": result.success,
                "status": result.status,
                "outputs": result.outputs,
                "artifacts": result.artifacts,
                "error_code": result.error_code,
                "error_message": result.error_message,
            },
            "telemetry": result.telemetry,
        }
        store.write_json("manifest.json", manifest)

        # Update task
        task.status = "completed" if result.success else "failed"
        task.completed_at = now
        task.result = result.outputs
        task.trace_path = store.get_uri()

        if not result.success:
            task.error = result.error_message

        # Update CWOM Run if exists
        if run:
            run.status = "done" if result.success else "failed"
            run.outputs = result.outputs
            run.telemetry = result.telemetry

            if not result.success:
                run.failure = {
                    "code": result.error_code or "EXECUTION_FAILED",
                    "message": result.error_message,
                }

            # Update linked issue status
            issue = db.query(CWOMIssueModel).filter(
                CWOMIssueModel.id == run.for_issue_id
            ).first()
            if issue:
                issue.status = "done" if result.success else "failed"

            # Create artifacts in CWOM
            for artifact_data in result.artifacts:
                artifact = CWOMArtifactModel(
                    id=str(uuid.uuid4()),
                    kind="Artifact",
                    trace_id=task.trace_id,
                    produced_by_id=run.id,
                    produced_by_kind="Run",
                    for_issue_id=run.for_issue_id,
                    for_issue_kind="Issue",
                    type=artifact_data.get("type", "doc"),
                    title=artifact_data.get("title", "Output"),
                    uri=f"{store.get_uri()}/{artifact_data.get('path', 'output')}",
                    media_type=artifact_data.get("media_type"),
                )
                db.add(artifact)

            # Audit log
            audit = AuditService(db)
            audit.log_status_change(
                entity_kind="Run",
                entity_id=run.id,
                old_status="running",
                new_status="done" if result.success else "failed",
                actor_kind="system",
                actor_id=self.worker_id,
                note=f"Execution {'completed' if result.success else 'failed'}",
                trace_id=task.trace_id,
            )

            # Step 4: Prove - Create Evidence Pack
            db.commit()  # Commit artifacts first so prover can find them
            db.refresh(run)  # Refresh run to get updated state

            prover = Prover(prover_id=self.worker_id)
            evidence_pack = prover.prove(
                db=db,
                run=run,
                task=task,
                trace_store=store,
            )
            logger.info(
                f"Evidence pack {evidence_pack.id} created with verdict: {evidence_pack.verdict}"
            )

        db.commit()
        logger.info(
            f"Task {task.id} {'completed' if result.success else 'failed'}: "
            f"{result.outputs.get('message', '')}"
        )

    def _handle_failure(
        self,
        db: Session,
        task: TaskModel,
        run: Optional[CWOMRunModel],
        store,
        error: str,
    ) -> None:
        """Handle execution failure.

        Args:
            db: Database session
            task: Task that failed
            run: CWOM Run (if created)
            store: TraceStore instance (may be None)
            error: Error message
        """
        now = datetime.now(timezone.utc)

        # Update task
        task.status = "failed"
        task.completed_at = now
        task.error = error

        # Write error to trace if store available
        if store:
            store.append_line("trace.log", f"[{now.isoformat()}] FATAL ERROR: {error}")
            store.append_event({
                "event": "execution_failed",
                "error": error,
            })

            manifest = {
                "version": "1.0",
                "task_id": str(task.id),
                "run_id": str(run.id) if run else None,
                "trace_id": task.trace_id,
                "worker_id": self.worker_id,
                "completed_at": now.isoformat(),
                "status": "failed",
                "error": error,
            }
            store.write_json("manifest.json", manifest)
            task.trace_path = store.get_uri()

        # Update CWOM Run if exists
        if run:
            run.status = "failed"
            run.failure = {
                "code": "WORKER_ERROR",
                "message": error,
            }

            # Update linked issue status
            issue = db.query(CWOMIssueModel).filter(
                CWOMIssueModel.id == run.for_issue_id
            ).first()
            if issue:
                issue.status = "failed"

            # Audit log
            audit = AuditService(db)
            audit.log_status_change(
                entity_kind="Run",
                entity_id=run.id,
                old_status="running",
                new_status="failed",
                actor_kind="system",
                actor_id=self.worker_id,
                note=f"Worker error: {error}",
                trace_id=task.trace_id,
            )

        db.commit()
        logger.error(f"Task {task.id} failed: {error}")


def run_worker(
    executor_type: str = "stub",
    poll_interval: Optional[int] = None,
    claim_limit: Optional[int] = None,
) -> None:
    """Run the worker loop.

    Args:
        executor_type: Type of executor to use
        poll_interval: Seconds between poll cycles
        claim_limit: Max tasks to claim per cycle
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    worker = WorkerLoop(
        executor_type=executor_type,
        poll_interval=poll_interval,
        claim_limit=claim_limit,
    )
    worker.start()
