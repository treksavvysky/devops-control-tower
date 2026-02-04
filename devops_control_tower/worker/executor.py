"""
Task executors for JCT Worker.

v0: StubExecutor - proves pipeline works, creates placeholder artifacts
v1+: Real executors (LLM agents, external services, containers)

Design: Executor interface allows swapping implementations without
changing the worker loop.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .storage import TraceStore


@dataclass
class ExecutionContext:
    """Context passed to executor for a task run."""

    task_id: str
    run_id: str
    trace_id: Optional[str]

    # Task definition
    objective: str
    operation: str  # code_change, docs, analysis, ops

    # Target
    target_repo: str
    target_ref: str
    target_path: str

    # Constraints
    time_budget_seconds: int
    allow_network: bool
    allow_secrets: bool

    # Additional data
    inputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # CWOM context (if available)
    context_packet: Optional[Dict[str, Any]] = None
    constraint_snapshot: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionResult:
    """Result from executor after task execution."""

    success: bool
    status: str  # "succeeded", "failed", "timed_out"

    # Outputs
    outputs: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    # Failure info (if failed)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Telemetry
    telemetry: Dict[str, Any] = field(default_factory=dict)


class Executor(ABC):
    """Abstract base class for task executors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Executor name for logging and identification."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Executor version."""
        pass

    @abstractmethod
    def execute(
        self, context: ExecutionContext, store: TraceStore
    ) -> ExecutionResult:
        """Execute a task and produce results.

        Args:
            context: Execution context with task details
            store: TraceStore for writing trace logs and artifacts

        Returns:
            ExecutionResult with status and outputs
        """
        pass


class StubExecutor(Executor):
    """Stub executor for v0 - proves pipeline works.

    This executor:
    - Logs the task objective
    - Simulates work with a short sleep
    - Creates a placeholder artifact
    - Always succeeds (unless time budget is < 1s)
    """

    @property
    def name(self) -> str:
        return "stub"

    @property
    def version(self) -> str:
        return "0.1.0"

    def execute(
        self, context: ExecutionContext, store: TraceStore
    ) -> ExecutionResult:
        """Execute stub task."""
        started_at = datetime.now(timezone.utc)

        # Log start
        store.append_event({
            "event": "execution_started",
            "executor": self.name,
            "executor_version": self.version,
            "task_id": context.task_id,
            "run_id": context.run_id,
            "trace_id": context.trace_id,
        })

        store.append_line("trace.log", f"[{started_at.isoformat()}] Execution started")
        store.append_line("trace.log", f"  Executor: {self.name} v{self.version}")
        store.append_line("trace.log", f"  Task ID: {context.task_id}")
        store.append_line("trace.log", f"  Operation: {context.operation}")
        store.append_line("trace.log", f"  Objective: {context.objective}")
        store.append_line("trace.log", f"  Target: {context.target_repo}:{context.target_ref}")
        store.append_line("trace.log", f"  Time budget: {context.time_budget_seconds}s")

        # Log context packet summary if available
        if context.context_packet:
            store.append_line("trace.log", "  Context packet: present")
            store.append_event({
                "event": "context_packet_loaded",
                "context_packet_id": context.context_packet.get("id"),
                "version": context.context_packet.get("version"),
            })

        # Simulate work (1 second or 10% of time budget, whichever is smaller)
        work_duration = min(1.0, context.time_budget_seconds * 0.1)
        store.append_line("trace.log", f"  Simulating work for {work_duration:.1f}s...")

        store.append_event({
            "event": "work_simulation_started",
            "duration_seconds": work_duration,
        })

        time.sleep(work_duration)

        store.append_event({
            "event": "work_simulation_completed",
        })

        # Create stub artifact
        artifact_content = f"""# Stub Execution Result

Task ID: {context.task_id}
Run ID: {context.run_id}
Operation: {context.operation}

## Objective
{context.objective}

## Target
- Repository: {context.target_repo}
- Ref: {context.target_ref}
- Path: {context.target_path or "(root)"}

## Result
This is a stub execution. In a real execution, this file would contain
the actual output of the task (code diff, documentation, analysis report, etc.).

## Constraints Applied
- Time budget: {context.time_budget_seconds}s
- Network access: {"allowed" if context.allow_network else "denied"}
- Secrets access: {"allowed" if context.allow_secrets else "denied"}

---
Generated by StubExecutor v{self.version}
"""

        store.write_text("artifacts/output.md", artifact_content)

        store.append_event({
            "event": "artifact_created",
            "path": "artifacts/output.md",
            "type": "stub_output",
        })

        completed_at = datetime.now(timezone.utc)
        duration = (completed_at - started_at).total_seconds()

        store.append_line("trace.log", f"[{completed_at.isoformat()}] Execution completed")
        store.append_line("trace.log", f"  Duration: {duration:.2f}s")
        store.append_line("trace.log", f"  Status: succeeded")

        store.append_event({
            "event": "execution_completed",
            "status": "succeeded",
            "duration_seconds": duration,
        })

        return ExecutionResult(
            success=True,
            status="succeeded",
            outputs={
                "message": "Stub execution completed successfully",
                "artifact_path": "artifacts/output.md",
            },
            artifacts=[
                {
                    "type": "doc",
                    "title": "Stub Output",
                    "path": "artifacts/output.md",
                    "media_type": "text/markdown",
                }
            ],
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            telemetry={
                "executor": self.name,
                "executor_version": self.version,
                "simulated_work_seconds": work_duration,
            },
        )


def get_executor(executor_type: str = "stub") -> Executor:
    """Factory function to get executor by type.

    Args:
        executor_type: Type of executor ("stub", "llm", "container", etc.)

    Returns:
        Executor instance

    Raises:
        ValueError: If executor type is not supported
    """
    if executor_type == "stub":
        return StubExecutor()
    else:
        raise ValueError(
            f"Unsupported executor type: {executor_type}. "
            f"Supported: stub"
        )
