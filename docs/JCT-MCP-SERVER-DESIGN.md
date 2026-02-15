# JCT MCP Server Design

**Date**: 2026-02-15
**Status**: Design Draft
**Depends On**: v0 Pipeline (Steps 1-5 Complete)

---

## 1. The Idea

The original Claude Code executor roadmap (`docs/CLAUDE-CODE-EXECUTOR-ROADMAP.md`) proposes shelling out to `claude -p` as a subprocess. That works, but it requires building prompt synthesis, output parsing, environment sanitization, and subprocess lifecycle management — all machinery to bridge between the control tower and Claude Code.

The MCP approach flips the model: instead of the worker calling Claude Code, **Claude Code calls the worker**. The control tower exposes an MCP server with tools for claiming tasks, reading context, reporting artifacts, and completing work. Claude Code connects to this MCP server and *is* the executor — using its native Read/Write/Edit/Bash tools to do real work, and JCT MCP tools to manage the task lifecycle.

```
SUBPROCESS MODEL (original roadmap):
  Worker Loop → subprocess("claude -p ...") → parse output → update DB

MCP MODEL (this design):
  Claude Code → jct_claim_task → (does real work with native tools) → jct_complete_task
                    ↓                                                        ↓
              JCT MCP Server ←──────── shared DB ──────────→ JCT MCP Server
```

### What This Eliminates

| Subprocess Roadmap Phase | MCP Equivalent |
|--------------------------|----------------|
| Phase 2: Prompt Synthesis | Not needed — Claude Code reads context via `jct_get_context` and reasons about it natively |
| Phase 3.2: Subprocess invocation | Not needed — no subprocess, Claude Code is already running |
| Phase 3.3: Environment sanitization | Not needed — MCP tools mediate all DB access |
| Phase 3.4: Result parsing | Not needed — Claude Code reports structured results via `jct_report_artifact` and `jct_complete_task` |

### What This Preserves

The downstream pipeline is untouched:
- **Trace storage**: The MCP server writes to the same `TraceStore`
- **Prover**: Runs after task completion, evaluates the same `EvidencePack`
- **Review**: Same auto-approve / manual review flow
- **Audit**: All MCP operations go through the service layer, which auto-logs to `AuditLog`

### What This Adds

A new interaction model: Claude Code as a **pull-based agent** that claims work from a queue, rather than a subprocess that gets pushed work. This is more natural for an LLM agent — it can inspect the task, ask for clarification (via context packets), plan its approach, execute incrementally, and report back.

---

## 2. Architecture

### Where It Fits

The control tower already has two interfaces: CLI (worker) and REST API (FastAPI). The MCP server becomes the third, following the same triple interface pattern used by OrcaOps and AI_SSH_Charon in this workspace.

```
                    ┌─────────────────────────────────┐
                    │     Shared Core Layer            │
                    │                                  │
                    │  cwom/services.py                │
                    │  db/services.py                  │
                    │  db/audit_service.py             │
                    │  worker/prover.py                │
                    │  worker/storage.py               │
                    │  policy/task_gate.py             │
                    └──────┬──────────┬───────────┬────┘
                           │          │           │
                    ┌──────┴───┐ ┌────┴────┐ ┌────┴─────┐
                    │ REST API │ │ Worker  │ │ MCP      │
                    │ (FastAPI)│ │ (poll)  │ │ (Claude) │
                    │ api.py   │ │ loop.py │ │ mcp.py   │
                    └──────────┘ └─────────┘ └──────────┘
```

All three interfaces use the same service classes, the same DB session pattern, and the same audit logging. The MCP server does **not** import from the API or worker — it imports directly from the shared core.

### Session Management

Following the OrcaOps pattern, the MCP server uses lazy-initialized singletons for DB access:

```python
from mcp.server.fastmcp import FastMCP

server = FastMCP(
    name="jct",
    instructions=(
        "Jules Control Tower: AI-assisted development operations. "
        "Claim tasks from the queue, read context packets, execute work, "
        "report artifacts, and complete tasks with full audit trails."
    ),
)

_session_factory = None

def _get_db():
    """Lazy-initialized DB session factory."""
    global _session_factory
    if _session_factory is None:
        from devops_control_tower.db.base import get_session_local
        _session_factory = get_session_local()
    return _session_factory()
```

Each tool call opens a session, does its work, commits, and closes — same lifecycle as a FastAPI request.

---

## 3. Tool Inventory

### 3.1 Task Lifecycle Tools (Primary Workflow)

These are the tools Claude Code uses to execute work. They form a linear workflow:

```
jct_list_tasks → jct_claim_task → jct_get_context → (do work) → jct_report_artifact → jct_complete_task
```

---

#### `jct_list_tasks`

**Purpose**: Browse available tasks in the queue. Lets Claude Code see what's available before claiming.

```python
@server.tool(
    name="jct_list_tasks",
    description=(
        "List tasks available in the JCT queue. Shows queued tasks by default. "
        "Use this to see what work is available before claiming a task."
    ),
)
def jct_list_tasks(
    status: str = "queued",
    operation: Optional[str] = None,
    limit: int = 10,
) -> str:
```

**Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | str | `"queued"` | Filter by status: `queued`, `running`, `completed`, `failed` |
| `operation` | str? | None | Filter by operation: `code_change`, `docs`, `analysis`, `ops` |
| `limit` | int | 10 | Max tasks to return |

**Returns** (success):
```json
{
  "success": true,
  "tasks": [
    {
      "task_id": "uuid",
      "operation": "code_change",
      "objective": "Add input validation to user registration endpoint",
      "target_repo": "myorg/api-service",
      "target_ref": "main",
      "status": "queued",
      "priority": "P1",
      "time_budget_seconds": 3600,
      "queued_at": "2026-02-15T10:00:00Z",
      "cwom_issue_id": "uuid-or-null"
    }
  ],
  "count": 1
}
```

**Implementation**: Wraps `TaskService.get_tasks()`.

---

#### `jct_claim_task`

**Purpose**: Atomically claim a queued task for execution. This is the entry point for doing work.

```python
@server.tool(
    name="jct_claim_task",
    description=(
        "Claim a queued task for execution. Atomically transitions the task from "
        "'queued' to 'running' and creates a CWOM Run. Returns the full task context "
        "including objective, constraints, and context packet. If the task was already "
        "claimed by another worker, returns an error."
    ),
)
def jct_claim_task(
    task_id: str,
) -> str:
```

**Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `task_id` | str | ID of the task to claim |

**Returns** (success):
```json
{
  "success": true,
  "task_id": "uuid",
  "run_id": "uuid",
  "trace_id": "uuid",
  "objective": "Add input validation to user registration endpoint",
  "operation": "code_change",
  "target": {
    "repo": "myorg/api-service",
    "ref": "main",
    "path": "src/routes/users.py"
  },
  "constraints": {
    "time_budget_seconds": 3600,
    "allow_network": false,
    "allow_secrets": false
  },
  "context_packet": {
    "id": "uuid",
    "version": 1,
    "summary": "Registration endpoint currently accepts any string for email...",
    "prior_art": ["Issue #42 added basic email regex"],
    "files_of_interest": ["src/routes/users.py", "src/models/user.py"],
    "acceptance_criteria": [
      "Email must be validated against RFC 5322",
      "Password must be >= 8 characters"
    ]
  },
  "constraint_snapshot": {
    "id": "uuid",
    "rules": { ... }
  }
}
```

**Returns** (error — already claimed):
```json
{
  "success": false,
  "error": {
    "code": "TASK_ALREADY_CLAIMED",
    "message": "Task 'uuid' is no longer queued (current status: running).",
    "suggestion": "Use jct_list_tasks to find another available task."
  }
}
```

**Implementation**:
1. Wraps the same optimistic-locking UPDATE used by `WorkerLoop._claim_task()`
2. Creates CWOM Run via `RunService.create()` (with `mode="agent"`, not `"system"`)
3. Loads ContextPacket and ConstraintSnapshot if linked
4. Initializes TraceStore for the run
5. Audit logs: claim with `actor_kind="agent"`, `actor_id="claude-code"`

**Key difference from worker**: The worker uses `mode="system"` for its runs. MCP-claimed runs use `mode="agent"` to distinguish the execution model in audit trails.

---

#### `jct_get_context`

**Purpose**: Fetch the full context packet and constraint snapshot for a claimed task. Useful if Claude Code wants to re-read context mid-execution.

```python
@server.tool(
    name="jct_get_context",
    description=(
        "Get the full context packet and constraint snapshot for a task. "
        "Use this to understand the detailed requirements, prior art, "
        "acceptance criteria, and operating constraints for your current task."
    ),
)
def jct_get_context(
    task_id: str,
) -> str:
```

**Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `task_id` | str | ID of the claimed task |

**Returns** (success):
```json
{
  "success": true,
  "task_id": "uuid",
  "issue": {
    "id": "uuid",
    "title": "Add input validation",
    "type": "feature",
    "priority": "P1",
    "status": "running",
    "acceptance_criteria": [...]
  },
  "context_packet": {
    "id": "uuid",
    "version": 1,
    "summary": "...",
    "prior_art": [...],
    "files_of_interest": [...],
    "data": { ... }
  },
  "constraint_snapshot": {
    "id": "uuid",
    "scope": "run",
    "rules": { ... }
  },
  "doctrine_refs": [
    {
      "id": "uuid",
      "namespace": "myorg",
      "name": "code-style",
      "body": "All functions must have type hints..."
    }
  ]
}
```

**Implementation**: Wraps `IssueService.get()`, `ContextPacketService.get_latest_for_issue()`, `ConstraintSnapshotService.get()`, and doctrine ref queries through join tables.

---

#### `jct_report_artifact`

**Purpose**: Register an artifact produced during execution. Called one or more times as Claude Code creates outputs.

```python
@server.tool(
    name="jct_report_artifact",
    description=(
        "Report an artifact produced during task execution. Call this for each "
        "meaningful output: code patches, documentation, analysis reports, etc. "
        "The artifact content or URI is recorded in the CWOM and trace store."
    ),
)
def jct_report_artifact(
    task_id: str,
    title: str,
    artifact_type: str,
    content: Optional[str] = None,
    uri: Optional[str] = None,
    media_type: str = "text/plain",
) -> str:
```

**Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `task_id` | str | — | ID of the claimed task |
| `title` | str | — | Human-readable artifact title (e.g., "Code changes patch") |
| `artifact_type` | str | — | One of: `code_patch`, `commit`, `doc`, `report`, `log`, `trace` |
| `content` | str? | None | Inline content (for small artifacts like diffs, reports) |
| `uri` | str? | None | URI to artifact (for large files or external references) |
| `media_type` | str | `"text/plain"` | MIME type: `text/plain`, `text/markdown`, `application/x-patch`, etc. |

**Returns** (success):
```json
{
  "success": true,
  "artifact_id": "uuid",
  "task_id": "uuid",
  "run_id": "uuid",
  "title": "Code changes patch",
  "type": "code_patch",
  "uri": "file:///var/lib/jct/runs/{run_id}/artifacts/changes.patch"
}
```

**Implementation**:
1. Looks up the Run associated with this task
2. If `content` is provided, writes it to the trace store under `artifacts/{sanitized_title}`
3. Creates `CWOMArtifactModel` via `ArtifactService.create()`
4. Audit logs artifact creation

**Usage pattern**: Claude Code would typically call this after making changes:
- `jct_report_artifact(task_id, "Code changes", "code_patch", content=git_diff_output)`
- `jct_report_artifact(task_id, "Test results", "log", content=pytest_output)`

---

#### `jct_complete_task`

**Purpose**: Mark a task as completed (or failed). Triggers the prove and review pipeline.

```python
@server.tool(
    name="jct_complete_task",
    description=(
        "Complete a claimed task. Provide a summary of what was done and whether "
        "it succeeded. This triggers the proof evaluation and review pipeline. "
        "After calling this, the task enters the prove/review flow automatically."
    ),
)
def jct_complete_task(
    task_id: str,
    success: bool,
    summary: str,
    outputs: Optional[str] = None,
    error_message: Optional[str] = None,
) -> str:
```

**Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `task_id` | str | — | ID of the claimed task |
| `success` | bool | — | Whether the task succeeded |
| `summary` | str | — | Human-readable summary of what was done |
| `outputs` | str? | None | JSON string of structured outputs (optional) |
| `error_message` | str? | None | Error details if `success=false` |

**Returns** (success):
```json
{
  "success": true,
  "task_id": "uuid",
  "task_status": "completed",
  "run_id": "uuid",
  "run_status": "done",
  "evidence_pack": {
    "id": "uuid",
    "verdict": "pass",
    "verdict_reason": "All automated checks passed"
  },
  "review": {
    "status": "auto_approved",
    "review_id": "uuid"
  }
}
```

**Returns** (manual review needed):
```json
{
  "success": true,
  "task_id": "uuid",
  "task_status": "completed",
  "run_id": "uuid",
  "run_status": "under_review",
  "evidence_pack": {
    "id": "uuid",
    "verdict": "pass",
    "verdict_reason": "All automated checks passed"
  },
  "review": {
    "status": "awaiting_manual_review",
    "message": "Task completed but requires manual review before approval."
  }
}
```

**Implementation**:
1. Updates `TaskModel`: status → `completed` (or `failed`), sets `completed_at`, `result`
2. Updates `CWOMRunModel`: status → `done` (or `failed`), sets outputs, telemetry
3. Writes final manifest to trace store
4. Runs `Prover.prove()` — creates `EvidencePack` with verdict
5. Applies review policy (same `_apply_review_policy` logic from `WorkerLoop`)
6. Returns the full result chain: task status + run status + evidence + review outcome

This is the most complex tool because it triggers the entire downstream pipeline. It reuses the same `Prover` and review policy logic from `worker/loop.py` — extracted into shared functions callable from both the worker loop and the MCP server.

---

### 3.2 Observation Tools (Read-Only)

These tools let Claude Code inspect the state of tasks, runs, and evidence without modifying anything. Useful for understanding the current pipeline state.

---

#### `jct_get_task`

**Purpose**: Get full details of a specific task.

```python
@server.tool(
    name="jct_get_task",
    description=(
        "Get detailed information about a specific task, including its status, "
        "linked CWOM objects, and execution history."
    ),
)
def jct_get_task(
    task_id: str,
) -> str:
```

**Returns**: Full task dict including status, operation, objective, target, constraints, linked issue ID, trace path, result, error.

**Implementation**: Wraps `TaskService.get_task()` → `task.to_dict()` plus linked CWOM data.

---

#### `jct_get_run`

**Purpose**: Get full details of a CWOM Run.

```python
@server.tool(
    name="jct_get_run",
    description=(
        "Get detailed information about a CWOM Run, including its status, "
        "executor info, outputs, artifacts, and evidence pack."
    ),
)
def jct_get_run(
    run_id: str,
) -> str:
```

**Returns**: Full run dict including status, mode, executor, inputs, outputs, telemetry, failure, artifact_root_uri, linked evidence pack.

**Implementation**: Wraps `RunService.get()` → `run.to_dict()` plus `EvidencePackService.get_for_run()`.

---

#### `jct_get_evidence`

**Purpose**: Get the evidence pack for a run — the proof evaluation results.

```python
@server.tool(
    name="jct_get_evidence",
    description=(
        "Get the evidence pack for a run. Shows the verdict (pass/fail/partial), "
        "criteria evaluations, collected evidence, and any missing items."
    ),
)
def jct_get_evidence(
    run_id: str,
) -> str:
```

**Returns**: Full evidence pack dict including verdict, verdict_reason, criteria_results, evidence_collected, evidence_missing, checks summary.

**Implementation**: Wraps `EvidencePackService.get_for_run()`.

---

#### `jct_get_audit_trail`

**Purpose**: Get the audit trail for an entity — full history of all changes.

```python
@server.tool(
    name="jct_get_audit_trail",
    description=(
        "Get the audit trail for a task, issue, or run. Shows all state changes, "
        "who made them, and when. Useful for debugging or understanding history."
    ),
)
def jct_get_audit_trail(
    entity_kind: str,
    entity_id: str,
    limit: int = 50,
) -> str:
```

**Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `entity_kind` | str | — | Entity type: `Task`, `Issue`, `Run`, `Artifact`, `EvidencePack` |
| `entity_id` | str | — | Entity ID |
| `limit` | int | 50 | Max audit entries to return |

**Returns**: List of audit log entries with timestamps, actors, actions, before/after diffs.

**Implementation**: Wraps `AuditService.query_by_entity()`.

---

### 3.3 Review Tools

These tools let Claude Code (or another agent) participate in the review step.

---

#### `jct_submit_review`

**Purpose**: Submit a review decision for an evidence pack.

```python
@server.tool(
    name="jct_submit_review",
    description=(
        "Submit a review decision for a completed task's evidence pack. "
        "Use 'approved' to accept, 'rejected' to reject, or 'needs_changes' "
        "to request modifications. This transitions the Issue and Run status."
    ),
)
def jct_submit_review(
    evidence_pack_id: str,
    decision: str,
    reason: str,
    reviewer_name: str = "claude-code",
) -> str:
```

**Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `evidence_pack_id` | str | — | ID of the evidence pack to review |
| `decision` | str | — | One of: `approved`, `rejected`, `needs_changes` |
| `reason` | str | — | Explanation for the decision |
| `reviewer_name` | str | `"claude-code"` | Display name for the reviewer |

**Returns** (success):
```json
{
  "success": true,
  "review_id": "uuid",
  "decision": "approved",
  "issue_status": "done",
  "run_status": "done"
}
```

**Implementation**: Wraps `ReviewDecisionService.create()` with `actor_kind="agent"`.

---

#### `jct_list_pending_reviews`

**Purpose**: List evidence packs awaiting manual review.

```python
@server.tool(
    name="jct_list_pending_reviews",
    description=(
        "List tasks that are under review and awaiting a decision. "
        "Use this to find work that needs review approval."
    ),
)
def jct_list_pending_reviews(
    limit: int = 10,
) -> str:
```

**Returns**: List of evidence packs whose linked Issue has `status="under_review"`, with verdict, run summary, and issue details.

**Implementation**: Queries Issues with `status="under_review"`, loads their EvidencePacks.

---

### 3.4 Task Creation Tools

These tools let Claude Code submit new tasks into the pipeline — enabling agent-to-agent workflows where one agent's output creates work for another.

---

#### `jct_enqueue_task`

**Purpose**: Submit a new task to the queue.

```python
@server.tool(
    name="jct_enqueue_task",
    description=(
        "Submit a new task to the JCT queue. The task goes through policy "
        "validation and, if accepted, is persisted with status 'queued'. "
        "Optionally creates CWOM objects (Issue, ContextPacket) automatically."
    ),
)
def jct_enqueue_task(
    objective: str,
    operation: str,
    target_repo: str,
    target_ref: str = "main",
    target_path: str = "",
    time_budget_seconds: int = 3600,
    priority: str = "P2",
    acceptance_criteria: Optional[List[str]] = None,
    context_summary: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    create_cwom: bool = True,
) -> str:
```

**Parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `objective` | str | — | What the task should accomplish |
| `operation` | str | — | One of: `code_change`, `docs`, `analysis`, `ops` |
| `target_repo` | str | — | Repository (must match `JCT_ALLOWED_REPO_PREFIXES`) |
| `target_ref` | str | `"main"` | Git ref (branch, tag, commit) |
| `target_path` | str | `""` | Scope within repo (empty = full repo) |
| `time_budget_seconds` | int | 3600 | Time budget (30-86400) |
| `priority` | str | `"P2"` | Priority: `P0`-`P4` |
| `acceptance_criteria` | list[str]? | None | Criteria for the prover to evaluate |
| `context_summary` | str? | None | Briefing for the executor |
| `idempotency_key` | str? | None | Prevents duplicate submission |
| `create_cwom` | bool | True | Auto-create Issue + ContextPacket |

**Returns** (success):
```json
{
  "success": true,
  "task_id": "uuid",
  "trace_id": "uuid",
  "status": "queued",
  "cwom_issue_id": "uuid"
}
```

**Returns** (policy rejection):
```json
{
  "success": false,
  "error": {
    "code": "REPO_NOT_ALLOWED",
    "message": "Repository 'badorg/repo' is not in the allowed prefixes.",
    "suggestion": "Check JCT_ALLOWED_REPO_PREFIXES configuration."
  }
}
```

**Implementation**: Wraps the same flow as `POST /tasks/enqueue` — policy gate validation, `TaskService.create_task()`, optional CWOM object creation via `task_to_cwom()`.

---

### Tool Summary Table

| Tool | Category | Mutates State | Description |
|------|----------|:---:|-------------|
| `jct_list_tasks` | Lifecycle | No | Browse the task queue |
| `jct_claim_task` | Lifecycle | Yes | Claim a task for execution |
| `jct_get_context` | Lifecycle | No | Read context packet + constraints |
| `jct_report_artifact` | Lifecycle | Yes | Register an execution output |
| `jct_complete_task` | Lifecycle | Yes | Finish task, trigger prove + review |
| `jct_get_task` | Observation | No | Inspect a task |
| `jct_get_run` | Observation | No | Inspect a CWOM Run |
| `jct_get_evidence` | Observation | No | Read evidence pack |
| `jct_get_audit_trail` | Observation | No | Read audit history |
| `jct_submit_review` | Review | Yes | Approve/reject evidence pack |
| `jct_list_pending_reviews` | Review | No | Find tasks awaiting review |
| `jct_enqueue_task` | Creation | Yes | Submit new task to queue |

**12 tools total**. Intentionally small surface area — one tool per distinct action.

---

## 4. Implementation

### 4.1 File Structure

```
devops_control_tower/
├── mcp.py                    # MCP server (all tool definitions)
├── mcp_helpers.py            # Shared helpers: _success(), _error(), _get_db()
└── ...existing files...
```

Following the OrcaOps pattern: all tools in a single file with lazy-initialized singletons. No new directories needed.

### 4.2 Entry Point

**File**: `devops_control_tower/mcp.py`

```python
"""
JCT MCP Server — exposes control tower operations to Claude Code.

Usage:
    python -m devops_control_tower.mcp          # stdio transport
    jct-mcp                                      # via pyproject.toml entry point

Claude Code configuration (.claude/settings.local.json):
    {
      "mcpServers": {
        "jct": {
          "command": "python",
          "args": ["-m", "devops_control_tower.mcp"]
        }
      }
    }
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

server = FastMCP(
    name="jct",
    instructions=(
        "Jules Control Tower: AI-assisted development operations. "
        "Claim tasks from the queue, read context and constraints, "
        "execute work, report artifacts, and complete tasks. "
        "All operations are audited with full causality tracking."
    ),
)


# ---------------------------------------------------------------------------
# Lazy-initialized singletons
# ---------------------------------------------------------------------------

_session_factory = None


def _get_db():
    """Get a new DB session. Caller must close it."""
    global _session_factory
    if _session_factory is None:
        from devops_control_tower.db.base import get_session_local
        _session_factory = get_session_local()
    return _session_factory()


def _success(**kwargs) -> str:
    """Format a success response."""
    return json.dumps({"success": True, **kwargs}, default=str)


def _error(code: str, message: str, suggestion: str = "") -> str:
    """Format an error response."""
    err = {"code": code, "message": message}
    if suggestion:
        err["suggestion"] = suggestion
    return json.dumps({"success": False, "error": err})


# ---------------------------------------------------------------------------
# Tools defined below (see Section 3 for full specs)
# ---------------------------------------------------------------------------

# ... tool implementations ...


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the JCT MCP server (stdio transport)."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
```

### 4.3 pyproject.toml Entry Point

```toml
[project.scripts]
jct-mcp = "devops_control_tower.mcp:main"
```

### 4.4 Claude Code Configuration

To connect Claude Code to the JCT MCP server, add to `.claude/settings.local.json`:

```json
{
  "mcpServers": {
    "jct": {
      "command": "python",
      "args": ["-m", "devops_control_tower.mcp"],
      "cwd": "/root/projects/devops-control-tower",
      "env": {
        "DATABASE_URL": "sqlite:///./devops_control_tower.db",
        "JCT_ALLOWED_REPO_PREFIXES": "myorg/,testorg/",
        "JCT_TRACE_ROOT": "file:///var/lib/jct/runs",
        "JCT_REVIEW_AUTO_APPROVE": "true",
        "JCT_REVIEW_AUTO_APPROVE_VERDICTS": "pass"
      }
    }
  }
}
```

### 4.5 Tool Implementation Pattern

Every tool follows this structure:

```python
@server.tool(
    name="jct_<action>",
    description="<description for Claude Code to understand when to use this tool>",
)
def jct_<action>(
    param1: str,
    param2: Optional[str] = None,
) -> str:
    """Brief docstring."""
    db = _get_db()
    try:
        # 1. Validate inputs
        # 2. Call service layer
        # 3. Format response
        return _success(...)
    except SomeSpecificError as exc:
        return _error("SPECIFIC_CODE", str(exc))
    except Exception as exc:
        return _error("INTERNAL_ERROR", str(exc))
    finally:
        db.close()
```

Key rules:
- **Always** close the DB session in `finally`
- **Always** return JSON via `_success()` or `_error()`
- **Never** raise exceptions — all errors are returned as structured JSON
- **Always** use service classes for DB operations (never raw ORM)
- **Always** include `actor_kind="agent"`, `actor_id="claude-code"` in audit-logged operations

---

## 5. The Agent Workflow

Here is how Claude Code would use the MCP tools to execute a complete task, end to end.

### 5.1 Happy Path

```
User: "Process the next task in the JCT queue"

Claude Code:
  1. jct_list_tasks(status="queued")
     → sees task: "Add input validation to user registration"

  2. jct_claim_task(task_id="abc-123")
     → gets objective, context packet, constraints
     → context says: "files of interest: src/routes/users.py, src/models/user.py"
     → acceptance criteria: "Email validated against RFC 5322"

  3. Read("src/routes/users.py")           # native tool
     → reads the current code

  4. Edit("src/routes/users.py", ...)      # native tool
     → adds email validation

  5. Bash("cd /repo && pytest tests/")     # native tool
     → runs tests, captures output

  6. Bash("cd /repo && git diff HEAD")     # native tool
     → captures the diff

  7. jct_report_artifact(
       task_id="abc-123",
       title="Code changes",
       artifact_type="code_patch",
       content=<the diff>
     )

  8. jct_report_artifact(
       task_id="abc-123",
       title="Test results",
       artifact_type="log",
       content=<pytest output>
     )

  9. jct_complete_task(
       task_id="abc-123",
       success=True,
       summary="Added RFC 5322 email validation to registration endpoint. All tests pass."
     )
     → Prover runs: verdict=pass
     → Review policy: auto-approved
     → Returns: {"success": true, "review": {"status": "auto_approved"}}

Claude Code → User: "Task completed and auto-approved. Added email validation..."
```

### 5.2 Failure Path

```
Claude Code:
  1. jct_claim_task(task_id="def-456")
  2. Read/Edit/Bash... → something goes wrong, tests fail

  3. jct_report_artifact(
       task_id="def-456",
       title="Failed test output",
       artifact_type="log",
       content=<pytest output with failures>
     )

  4. jct_complete_task(
       task_id="def-456",
       success=False,
       summary="Unable to implement feature - dependency conflict in package.json",
       error_message="npm install fails with peer dependency conflict between react@18 and react-dom@17"
     )
     → Prover runs: verdict=fail
     → Run/Issue → failed
```

### 5.3 Multi-Task Agent Loop

Claude Code could also operate as a continuous agent:

```
User: "Process all queued tasks"

Claude Code:
  while True:
    tasks = jct_list_tasks(status="queued")
    if tasks.count == 0:
      break
    claim → work → report → complete
    # repeat
```

### 5.4 Review Agent

A separate Claude Code session could act as a reviewer:

```
User: "Review pending tasks"

Claude Code:
  1. jct_list_pending_reviews()
     → sees evidence pack for task abc-123

  2. jct_get_evidence(run_id="...")
     → reads verdict, criteria, collected evidence

  3. jct_get_run(run_id="...")
     → reads the run outputs and artifacts

  4. (reads the actual code changes using native tools)

  5. jct_submit_review(
       evidence_pack_id="...",
       decision="approved",
       reason="Code changes look correct. Tests pass. Email validation follows RFC 5322."
     )
```

This separates execution from review — two different Claude Code sessions with different roles, coordinated through the JCT queue.

---

## 6. Shared Code Extraction

The `jct_complete_task` tool needs to run the prover and apply review policy — the same logic currently embedded in `WorkerLoop._handle_result()` and `WorkerLoop._apply_review_policy()`. This code needs to be extracted into shared functions.

### Current State (in `worker/loop.py`)

```python
class WorkerLoop:
    def _handle_result(self, db, task, run, result, store):
        # ... update task, run, create artifacts ...
        # ... run prover ...
        # ... apply review policy ...

    def _apply_review_policy(self, db, task, run, evidence_pack, store):
        # ... auto-approve or set under_review ...
```

### Proposed Extraction

**New file**: `devops_control_tower/worker/pipeline.py`

```python
"""
Shared pipeline functions used by both WorkerLoop and MCP server.

These functions implement the prove → review flow that runs after
task execution, regardless of whether the executor was the worker's
subprocess or Claude Code via MCP.
"""

def run_prove(
    db: Session,
    run: CWOMRunModel,
    task: TaskModel,
    store: TraceStore,
    prover_id: str = "prover-v0",
) -> CWOMEvidencePackModel:
    """Run the prover and create an EvidencePack."""
    prover = Prover(prover_id=prover_id)
    return prover.prove(db, run, task, store)


def apply_review_policy(
    db: Session,
    task: TaskModel,
    run: CWOMRunModel,
    evidence_pack: CWOMEvidencePackModel,
    store: TraceStore,
    actor_kind: str = "system",
    actor_id: str = "worker",
) -> Dict[str, Any]:
    """Apply review policy: auto-approve or set under_review.

    Returns:
        Dict with keys: status ("auto_approved" | "awaiting_manual_review"),
        review_id (if auto-approved), message
    """
    settings = get_settings()
    auto_approve = settings.jct_review_auto_approve
    allowed_verdicts = [
        v.strip()
        for v in settings.jct_review_auto_approve_verdicts.split(",")
    ]

    if auto_approve and evidence_pack.verdict in allowed_verdicts:
        # Auto-approve flow
        # ... create ReviewDecision, transition to done ...
        return {"status": "auto_approved", "review_id": review.id}
    else:
        # Manual review flow
        # ... set under_review ...
        return {"status": "awaiting_manual_review", "message": "..."}
```

Then both `WorkerLoop` and `jct_complete_task` call these shared functions:

```python
# In worker/loop.py:
from .pipeline import run_prove, apply_review_policy

# In mcp.py:
from devops_control_tower.worker.pipeline import run_prove, apply_review_policy
```

This is the only refactor needed to existing code.

---

## 7. Run-to-Task Mapping

The MCP server needs to track which Run belongs to which claimed task, so that `jct_report_artifact` and `jct_complete_task` can find the right Run. Two options:

### Option A: In-Memory Map (Simpler)

```python
# Module-level state in mcp.py
_active_claims: Dict[str, Dict[str, str]] = {}
# { task_id: { "run_id": "...", "trace_uri": "...", "store": TraceStore } }
```

On `jct_claim_task`: store the mapping.
On `jct_complete_task`: read and clear the mapping.

**Downside**: Lost on MCP server restart. But since the MCP server lifecycle is tied to the Claude Code session, this is acceptable — a restarted session wouldn't have context to continue a previous task anyway.

### Option B: DB Query (More Robust)

Look up the Run by querying `CWOMRunModel` where `for_issue_id = task.cwom_issue_id` and `status = 'running'`.

**Downside**: Slightly more DB chatter. But more robust across restarts.

**Recommendation**: Use Option A with Option B as fallback.

```python
def _get_active_run(task_id: str, db: Session) -> Optional[Dict]:
    """Get active run for a claimed task."""
    # Try in-memory first
    if task_id in _active_claims:
        return _active_claims[task_id]

    # Fallback: query DB
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if task and task.cwom_issue_id:
        run = db.query(CWOMRunModel).filter(
            CWOMRunModel.for_issue_id == task.cwom_issue_id,
            CWOMRunModel.status == "running",
        ).first()
        if run:
            store = create_trace_store(
                get_settings().jct_trace_root, run.id
            )
            claim = {
                "run_id": run.id,
                "trace_uri": run.artifact_root_uri,
                "store": store,
            }
            _active_claims[task_id] = claim
            return claim
    return None
```

---

## 8. Testing Strategy

### 8.1 Unit Tests (Mocked DB)

**File**: `tests/test_mcp_server.py`

Test each tool in isolation with a mocked DB session:

```python
import json
from unittest.mock import MagicMock, patch

from devops_control_tower.mcp import (
    jct_list_tasks,
    jct_claim_task,
    jct_report_artifact,
    jct_complete_task,
)


class TestListTasks:
    def test_returns_queued_tasks(self, db_session):
        # Seed a queued task
        # Call jct_list_tasks
        # Assert response shape and content

    def test_empty_queue(self, db_session):
        result = json.loads(jct_list_tasks())
        assert result["success"] is True
        assert result["count"] == 0

    def test_filters_by_operation(self, db_session):
        # Seed tasks with different operations
        # Filter by "code_change"
        # Assert only matching tasks returned


class TestClaimTask:
    def test_claim_creates_run(self, db_session):
        # Seed a queued task with CWOM issue
        # Claim it
        # Assert run created with mode="agent"

    def test_claim_already_claimed(self, db_session):
        # Seed a running task
        # Try to claim
        # Assert TASK_ALREADY_CLAIMED error

    def test_claim_returns_context_packet(self, db_session):
        # Seed task + issue + context packet
        # Claim
        # Assert context_packet in response


class TestReportArtifact:
    def test_inline_content_written_to_trace(self, db_session):
        # Claim a task
        # Report artifact with content
        # Assert file exists in trace store

    def test_creates_cwom_artifact(self, db_session):
        # Report artifact
        # Query DB for CWOMArtifactModel
        # Assert linked to run


class TestCompleteTask:
    def test_success_triggers_prove(self, db_session):
        # Claim task, report artifact, complete
        # Assert EvidencePack created

    def test_failure_sets_run_failed(self, db_session):
        # Claim task, complete with success=False
        # Assert run.status == "failed"

    def test_auto_approve_flow(self, db_session):
        # Enable auto-approve
        # Complete task
        # Assert ReviewDecision created, issue.status == "done"

    def test_manual_review_flow(self, db_session):
        # Disable auto-approve
        # Complete task
        # Assert issue.status == "under_review"
```

### 8.2 Integration Tests (Real DB, Mocked MCP Transport)

**File**: `tests/test_mcp_integration.py`

End-to-end flow using the test DB from `conftest.py`:

```python
class TestMCPWorkflow:
    def test_full_lifecycle(self, db_session):
        """Enqueue → claim → report → complete → prove → review."""
        # 1. Enqueue task via jct_enqueue_task
        # 2. List tasks, verify it appears
        # 3. Claim task
        # 4. Report artifact
        # 5. Complete task
        # 6. Verify: task=completed, run=done, evidence=pass, review=auto_approved

    def test_review_agent_workflow(self, db_session):
        """Complete task → manual review → approve."""
        # Disable auto-approve
        # Enqueue + claim + complete
        # List pending reviews
        # Submit review (approved)
        # Verify: issue=done, run=done
```

### 8.3 Live Smoke Test

With the server running and Claude Code connected:

```bash
# 1. Seed a task via REST API
curl -X POST http://localhost:8000/tasks/enqueue \
  -H "Content-Type: application/json" \
  -d '{"objective": "Add a hello world endpoint", "operation": "code_change", ...}'

# 2. In Claude Code, the jct tools are now available
# Claude Code: jct_list_tasks → sees the task → jct_claim_task → does work → jct_complete_task
```

---

## 9. Implementation Order

| Step | Task | Effort | Blocks |
|------|------|--------|--------|
| 1 | Extract `pipeline.py` from `worker/loop.py` | 2h | — |
| 2 | Create `mcp.py` with server skeleton + helpers | 1h | — |
| 3 | Implement `jct_list_tasks`, `jct_get_task` | 1h | 2 |
| 4 | Implement `jct_claim_task` | 2h | 2 |
| 5 | Implement `jct_get_context` | 1h | 4 |
| 6 | Implement `jct_report_artifact` | 1.5h | 4 |
| 7 | Implement `jct_complete_task` | 3h | 1, 6 |
| 8 | Implement observation tools (`get_run`, `get_evidence`, `get_audit_trail`) | 1.5h | 2 |
| 9 | Implement review tools (`submit_review`, `list_pending_reviews`) | 1.5h | 2 |
| 10 | Implement `jct_enqueue_task` | 1.5h | 2 |
| 11 | Add pyproject.toml entry point | 0.5h | 2 |
| 12 | Unit tests | 3h | 3-10 |
| 13 | Integration tests | 2h | 12 |
| 14 | Claude Code config + live smoke test | 1h | 11, 13 |

**Total estimated effort**: ~22h

---

## 10. New and Modified Files

### New Files

| File | Purpose |
|------|---------|
| `devops_control_tower/mcp.py` | MCP server with all 12 tool definitions |
| `devops_control_tower/worker/pipeline.py` | Shared prove + review logic extracted from loop.py |
| `tests/test_mcp_server.py` | Unit tests for each MCP tool |
| `tests/test_mcp_integration.py` | End-to-end MCP workflow tests |

### Modified Files

| File | Change |
|------|--------|
| `devops_control_tower/worker/loop.py` | Import from `pipeline.py` instead of inline prove/review logic |
| `pyproject.toml` | Add `jct-mcp` entry point, add `mcp` dependency |
| `CLAUDE.md` | Document MCP server, tool inventory, config |

### NOT Modified

Everything downstream of task completion is untouched:
- `worker/prover.py` — called from `pipeline.py`, same interface
- `worker/storage.py` — trace store used by MCP tools the same way
- `cwom/services.py` — services called by MCP tools the same way
- `db/audit_service.py` — audit logging integrated the same way
- `cwom/routes.py` — REST API remains independent
- `config.py` — no new config needed (MCP uses existing settings)

---

## 11. Comparison: MCP vs. Subprocess Approach

| Dimension | Subprocess (`claude -p`) | MCP Server |
|-----------|-------------------------|------------|
| **Prompt engineering** | Must synthesize prompt from context | Not needed — Claude reasons natively |
| **Output parsing** | Parse JSON stdout | Not needed — structured tool responses |
| **Env isolation** | Manual env sanitization | MCP mediates all access |
| **Workspace management** | Must clone/worktree per run | Claude Code already has repo access |
| **Error handling** | Parse subprocess stderr | Structured error codes in tool responses |
| **Observability** | Read trace folder after completion | Real-time via `jct_get_run`, audit trail |
| **Token tracking** | Parse from claude JSON output | Could track via API key usage (separate concern) |
| **Concurrency** | Multiple subprocesses | Multiple Claude Code sessions |
| **Complexity** | ~6 new files, subprocess mgmt | ~4 new files, 1 refactor |
| **Testing** | Must mock subprocess.run | Mock DB session (standard pattern) |
| **Agent autonomy** | Worker controls execution | Agent controls execution |
| **Extensibility** | New executor class per backend | Same tools, any MCP-capable agent |

The MCP approach is simpler to build, easier to test, and more aligned with how Claude Code naturally works. The subprocess approach has one advantage: stronger isolation (the executor runs in a separate process). For v1, the MCP approach is the right trade-off.

---

## 12. Future Extensions

Things deliberately left out of v1 but enabled by the architecture:

- **Token/cost tracking**: Add a `jct_report_telemetry` tool for agents to self-report token usage
- **Progress streaming**: Add a `jct_report_progress` tool for long-running tasks to post status updates
- **Multi-agent coordination**: One agent enqueues via `jct_enqueue_task`, another claims and executes — agents coordinate through the queue
- **Approval chains**: Reviewer agent uses `jct_submit_review(needs_changes)` → original agent picks up the feedback → resubmits
- **Resource prompts**: Expose CWOM resources (issues, runs, evidence) as MCP resources, not just tools — enabling richer context injection
- **SSE transport**: Switch from stdio to SSE for server mode, enabling multiple Claude Code sessions to connect to one JCT MCP server
