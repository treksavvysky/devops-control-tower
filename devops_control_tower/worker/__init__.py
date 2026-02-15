"""
JCT Worker - processes queued tasks and produces trace folders.

v0 spine: queued task → Worker → trace folder

Usage:
    python -m devops_control_tower.worker

Components:
    - loop: Main worker loop (poll, claim, execute, complete) - v0 implementation
    - executor: Task executors (StubExecutor for v0)
    - storage: Trace storage abstraction (file:// for v0, s3:// for v2)
    - worker: Legacy Sprint-0 worker (kept for backward compatibility)
    - action_runner: Legacy action runner interface
"""

# v0 implementation (new)
from .executor import (
    Executor,
    ExecutionContext,
    ExecutionResult,
    StubExecutor,
    get_executor,
)
from .loop import WorkerLoop, run_worker
from .pipeline import apply_review_policy, run_prove
from .prover import Prover, ProofResult
from .storage import TraceStore, FileTraceStore, create_trace_store, get_trace_uri

# Legacy Sprint-0 (kept for backward compatibility)
from .worker import Worker
from .action_runner import ActionRunner, StubActionRunner

__all__ = [
    # v0 Loop
    "WorkerLoop",
    "run_worker",
    # v0 Executor
    "Executor",
    "ExecutionContext",
    "ExecutionResult",
    "StubExecutor",
    "get_executor",
    # v0 Pipeline (shared prove + review)
    "run_prove",
    "apply_review_policy",
    # v0 Prover
    "Prover",
    "ProofResult",
    # v0 Storage
    "TraceStore",
    "FileTraceStore",
    "create_trace_store",
    "get_trace_uri",
    # Legacy Sprint-0
    "Worker",
    "ActionRunner",
    "StubActionRunner",
]
