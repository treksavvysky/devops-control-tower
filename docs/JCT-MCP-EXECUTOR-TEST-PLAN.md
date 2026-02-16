# JCT MCP Server — Live Executor Test Plan

## Overview

This test plan covers **live testing** of the JCT MCP server with Claude Code as the executor. The MCP server (`devops_control_tower/mcp.py`) exposes 12 tools that let Claude Code claim tasks, do work, and report results — replacing the StubExecutor with a real agent.

Unit tests exist in `tests/test_mcp_server.py` (35 tests, all passing). This plan covers integration testing with the actual MCP connection.

## Prerequisites

### Docker stack running

```bash
docker compose up -d postgres redis        # Start infra
docker compose run --rm --entrypoint "" control-tower alembic upgrade head  # Migrate (first time only)
docker compose up -d                       # Start API + worker
```

Verify: `curl http://localhost:8000/health` returns `{"status":"ok"}`

### MCP server configured

The JCT MCP server should be configured in the project's `.claude/settings.local.json` or the workspace `.mcp.json`:

```json
{
  "mcpServers": {
    "jct": {
      "command": "python3",
      "args": ["-m", "devops_control_tower.mcp"],
      "cwd": "/root/projects/devops-control-tower",
      "env": {
        "DATABASE_URL": "postgresql+psycopg2://devops:devops@localhost:5432/devops_control_tower",
        "JCT_ALLOWED_REPO_PREFIXES": "testorg/,myorg/",
        "JCT_TRACE_ROOT": "file:///tmp/jct-traces",
        "JCT_REVIEW_AUTO_APPROVE": "true",
        "JCT_REVIEW_AUTO_APPROVE_VERDICTS": "pass"
      }
    }
  }
}
```

**Important:** The MCP server connects directly to the same Postgres as the Docker stack, so use `localhost:5432` (not `postgres:5432` which is the Docker-internal hostname).

## Test Scenarios

### Test 1: List empty queue

**Goal:** Verify the MCP connection works and the tool returns structured data.

**Steps:**
1. Call `jct_list_tasks()` (no arguments, defaults to status=queued)
2. Expect: `{"success": true, "tasks": [], "count": 0}`

### Test 2: Enqueue a task

**Goal:** Submit a task through the MCP server and verify it appears in the queue.

**Steps:**
1. Call `jct_enqueue_task` with:
   ```json
   {
     "objective": "Add a README.md to the test repo",
     "operation": "docs",
     "repo": "testorg/sample-repo",
     "requester_kind": "agent",
     "requester_id": "claude-code-test"
   }
   ```
2. Expect: `{"success": true, "task_id": "...", "trace_id": "..."}`
3. Call `jct_list_tasks()` — should show 1 queued task
4. Call `jct_get_task(task_id)` — should return full task details

### Test 3: Full agent workflow (happy path)

**Goal:** Walk through the complete claim → work → complete cycle.

**Steps:**
1. **Enqueue:** `jct_enqueue_task(...)` — get `task_id`
2. **Claim:** `jct_claim_task(task_id)` — expect run_id, trace_uri, context
3. **Get context:** `jct_get_context(task_id)` — expect context_packet and constraint_snapshot
4. **Report artifact:** `jct_report_artifact(task_id, "output.md", "# Hello World\n\nTest output.", "text/markdown")` — expect artifact_id
5. **Complete:** `jct_complete_task(task_id, success=true, summary="Created README")` — expect evidence_pack verdict and review status
6. **Verify:** `jct_get_task(task_id)` — status should be `completed`
7. **Verify:** `jct_get_run(run_id)` — status should be `done` (auto-approved) or `under_review`
8. **Verify:** `jct_get_evidence(evidence_pack_id)` — verdict should be `pass`

### Test 4: Failed task workflow

**Goal:** Verify the failure path works correctly.

**Steps:**
1. Enqueue a task
2. Claim it
3. Complete with `success=false, summary="Could not find the target file"`
4. Verify task status = `completed`, run status = `failed`, evidence verdict = `fail`

### Test 5: Observation tools

**Goal:** Verify read-only observation tools work.

**Steps:**
1. After completing Test 3, use:
   - `jct_get_audit_trail(entity_kind="Run", entity_id=run_id)` — should show status transitions
   - `jct_get_evidence(evidence_pack_id)` — should show verdict details
   - `jct_list_pending_reviews()` — should be empty if auto-approve is on

### Test 6: Review workflow (manual review)

**Goal:** Test the manual review path.

**Setup:** Set `JCT_REVIEW_AUTO_APPROVE=false` in the MCP server env (requires restart).

**Steps:**
1. Enqueue, claim, report artifact, complete (success)
2. Run and Issue should be `under_review`
3. `jct_list_pending_reviews()` — should show the evidence pack
4. `jct_submit_review(evidence_pack_id, decision="approved", reason="Looks good", reviewer_id="reviewer-1")` — should transition to done
5. Verify run/issue status = `done`

### Test 7: Double-claim prevention

**Goal:** Verify optimistic locking prevents double-claiming.

**Steps:**
1. Enqueue a task
2. Claim it — should succeed
3. Claim the same task_id again — should return error `TASK_NOT_QUEUED`

### Test 8: Idempotency

**Goal:** Verify idempotent enqueue via `idempotency_key`.

**Steps:**
1. `jct_enqueue_task(..., idempotency_key="test-key-1")` — should succeed
2. `jct_enqueue_task(..., idempotency_key="test-key-1")` — should return 409 / conflict error

## Key Implementation Details

### Architecture

```
Claude Code ←→ MCP (stdio) ←→ jct MCP server ←→ Postgres
                                      ↓
                              worker/pipeline.py (prove + review)
                                      ↓
                              Trace storage (file://)
```

### Files

| File | Purpose |
|------|---------|
| `devops_control_tower/mcp.py` | FastMCP server, 12 tools |
| `devops_control_tower/worker/pipeline.py` | Shared `run_prove()` + `apply_review_policy()` |
| `tests/test_mcp_server.py` | 35 unit tests (in-memory SQLite) |
| `docs/JCT-MCP-SERVER-DESIGN.md` | Full design doc with tool specs |

### Tool Inventory

| Tool | Category | Description |
|------|----------|-------------|
| `jct_list_tasks` | Lifecycle | List tasks by status (default: queued) |
| `jct_claim_task` | Lifecycle | Atomically claim a queued task, creates Run with mode=agent |
| `jct_get_context` | Lifecycle | Get ContextPacket + ConstraintSnapshot for a claimed task |
| `jct_report_artifact` | Lifecycle | Upload artifact to trace store |
| `jct_complete_task` | Lifecycle | Mark done/failed, triggers prove + review pipeline |
| `jct_get_task` | Observation | Get task details |
| `jct_get_run` | Observation | Get run details |
| `jct_get_evidence` | Observation | Get evidence pack |
| `jct_get_audit_trail` | Observation | Get audit log for any entity |
| `jct_submit_review` | Review | Approve/reject evidence pack |
| `jct_list_pending_reviews` | Review | List evidence packs awaiting review |
| `jct_enqueue_task` | Creation | Submit new task (policy validated) |

### Response Format

All tools return JSON strings:
- Success: `{"success": true, ...data...}`
- Error: `{"success": false, "error": {"code": "...", "message": "...", "suggestion": "..."}}`

### Run Mode

- Worker creates runs with `mode="system"`
- MCP server creates runs with `mode="agent"` — this is how you differentiate human-initiated vs automated work in the audit trail

### Docker Startup Sequence

```bash
docker compose up -d postgres redis
docker compose run --rm --entrypoint "" control-tower alembic upgrade head
docker compose up -d
```

The entrypoint script waits for Postgres health but does NOT run migrations automatically. Migrations must be run manually before the first startup.
