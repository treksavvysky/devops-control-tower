"""
Sprint-0 Action Runner.

The ActionRunner executes task actions and propagates trace_id
to all downstream calls. This module provides:
- Abstract ActionRunner interface
- StubActionRunner for Sprint-0 validation
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    action_name: str
    trace_id: str
    started_at: datetime
    completed_at: datetime
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: List[Dict[str, Any]] = field(default_factory=list)


class ActionRunner(ABC):
    """Abstract base class for action execution.

    All action runners must propagate trace_id to downstream calls.
    """

    def __init__(self, trace_id: str, task_id: str, job_id: str):
        self.trace_id = trace_id
        self.task_id = task_id
        self.job_id = job_id
        self.logger = logger.bind(
            trace_id=trace_id,
            task_id=task_id,
            job_id=job_id,
        )

    @abstractmethod
    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        constraints: Dict[str, Any],
    ) -> ActionResult:
        """Execute an action and return the result.

        Args:
            action_name: Name of the action to execute
            inputs: Input parameters for the action
            constraints: Execution constraints (time budget, network, etc.)

        Returns:
            ActionResult with success/failure status and any artifacts
        """
        pass

    def get_headers(self) -> Dict[str, str]:
        """Get headers to propagate trace_id to downstream calls."""
        return {
            "X-Trace-Id": self.trace_id,
            "X-Task-Id": self.task_id,
            "X-Job-Id": self.job_id,
        }


class StubActionRunner(ActionRunner):
    """Stub action runner for Sprint-0 validation.

    This runner simulates action execution and produces log artifacts
    to prove trace_id propagation works end-to-end.
    """

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        constraints: Dict[str, Any],
    ) -> ActionResult:
        """Execute a stub action.

        In Sprint-0, this simply:
        1. Logs the action start with trace_id
        2. Simulates work
        3. Creates a log artifact
        4. Returns success
        """
        started_at = datetime.utcnow()

        self.logger.info(
            "action_start",
            action_name=action_name,
            inputs_keys=list(inputs.keys()),
        )

        # Simulate the action execution
        try:
            # In Sprint-0, we just simulate success
            # Later: actual action implementations
            result_data = self._simulate_action(action_name, inputs)

            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            self.logger.info(
                "action_complete",
                action_name=action_name,
                duration_ms=duration_ms,
                success=True,
            )

            # Create log artifact
            log_content = self._create_execution_log(
                action_name, started_at, completed_at, result_data
            )

            artifacts = [
                {
                    "kind": "log",
                    "ref": f"worker_log_{action_name}_{self.job_id}",
                    "content": log_content,
                    "content_type": "text/plain",
                }
            ]

            return ActionResult(
                success=True,
                action_name=action_name,
                trace_id=self.trace_id,
                started_at=started_at,
                completed_at=completed_at,
                result=result_data,
                artifacts=artifacts,
            )

        except Exception as e:
            completed_at = datetime.utcnow()
            self.logger.error(
                "action_failed",
                action_name=action_name,
                error=str(e),
            )

            # Create error artifact
            error_content = self._create_error_log(action_name, started_at, completed_at, e)

            artifacts = [
                {
                    "kind": "error",
                    "ref": f"worker_error_{action_name}_{self.job_id}",
                    "content": error_content,
                    "content_type": "text/plain",
                }
            ]

            return ActionResult(
                success=False,
                action_name=action_name,
                trace_id=self.trace_id,
                started_at=started_at,
                completed_at=completed_at,
                error=str(e),
                artifacts=artifacts,
            )

    def _simulate_action(
        self, action_name: str, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate an action execution.

        In Sprint-0, this returns mock results based on action type.
        """
        return {
            "action": action_name,
            "status": "simulated",
            "trace_id": self.trace_id,
            "message": f"Stub execution of {action_name} completed successfully",
            "inputs_received": list(inputs.keys()),
        }

    def _create_execution_log(
        self,
        action_name: str,
        started_at: datetime,
        completed_at: datetime,
        result: Dict[str, Any],
    ) -> str:
        """Create a structured execution log."""
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        return f"""=== Action Execution Log ===
trace_id: {self.trace_id}
task_id: {self.task_id}
job_id: {self.job_id}
action: {action_name}
started_at: {started_at.isoformat()}
completed_at: {completed_at.isoformat()}
duration_ms: {duration_ms}
status: SUCCESS
result: {result}
==========================="""

    def _create_error_log(
        self,
        action_name: str,
        started_at: datetime,
        completed_at: datetime,
        error: Exception,
    ) -> str:
        """Create a structured error log."""
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        return f"""=== Action Error Log ===
trace_id: {self.trace_id}
task_id: {self.task_id}
job_id: {self.job_id}
action: {action_name}
started_at: {started_at.isoformat()}
completed_at: {completed_at.isoformat()}
duration_ms: {duration_ms}
status: FAILED
error_type: {type(error).__name__}
error_message: {str(error)}
========================"""


class HttpActionRunner(ActionRunner):
    """Action runner that makes HTTP calls to downstream services.

    This runner propagates trace_id via X-Trace-Id header.
    For Sprint-0, this is a placeholder for future implementation.
    """

    def __init__(
        self,
        trace_id: str,
        task_id: str,
        job_id: str,
        base_url: Optional[str] = None,
    ):
        super().__init__(trace_id, task_id, job_id)
        self.base_url = base_url

    def execute(
        self,
        action_name: str,
        inputs: Dict[str, Any],
        constraints: Dict[str, Any],
    ) -> ActionResult:
        """Execute an action via HTTP call.

        For Sprint-0, this falls back to stub behavior.
        In later sprints, this will make actual HTTP calls.
        """
        started_at = datetime.utcnow()

        self.logger.info(
            "http_action_start",
            action_name=action_name,
            base_url=self.base_url,
        )

        # Sprint-0: Fall back to stub behavior
        # Later: Make actual HTTP calls with self.get_headers()
        stub_runner = StubActionRunner(self.trace_id, self.task_id, self.job_id)
        return stub_runner.execute(action_name, inputs, constraints)
