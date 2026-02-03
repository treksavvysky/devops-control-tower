# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Control Tower (JCT - Jules Control Tower) is an orchestration backbone for AI-assisted development operations. It manages task execution and recording through a FastAPI-based system with database persistence.

**Current Focus (v0 Spine):** The minimal viable path is `/tasks/enqueue → DB row → Worker → Trace folder`. Advanced features (LLM workflows, monitoring agents, event routing) are disabled until this spine is validated.

## Stage-Based Development

Development proceeds in stages. Each stage has a summary document tracking progress, decisions, and verification evidence.

**Stage Progress Documents:**
- `STAGE-01-SUMMARY.md` - Task Contract + Intake Gate (✅ COMPLETE)
- `docs/cwom/CWOM-IMPLEMENTATION-PLAN.md` - CWOM v0.1 implementation (✅ Phase 1-4 COMPLETE)
- `docs/cwom/CWOM-COMPLETION-ROADMAP.md` - Remaining CWOM work + AuditLog

**Stage 1 (Complete):** V1 Task Spec contract defined, policy gate implemented, `POST /tasks/enqueue` persists validated tasks, idempotency enforced, `GET /tasks/{id}` retrieves stored records.

**CWOM v0.1 (Phases 1-4 Complete):** Pydantic schemas, SQLAlchemy models, API endpoints, and Task-CWOM integration all implemented. See CWOM section below for details.

**CWOM Completion Phase 2 (Complete):** AuditLog model, migration, service, and integration with all CWOM services.

**Next Stage:** Worker implementation to process queued tasks and produce trace artifacts.

## Common Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env

# Database (defaults to SQLite)
alembic upgrade head

# Run application
python -m devops_control_tower.main

# Run with Docker
docker compose up

# Testing
pytest                                    # all tests
pytest tests/test_orchestrator.py         # single file
pytest -k "test_enqueue"                  # by test name pattern
pytest --cov=devops_control_tower         # with coverage

# Linting/Formatting
black .
isort .
flake8 .
mypy devops_control_tower
```

## Architecture

```
devops_control_tower/
├── main.py              # Entry point, imports app from api.py
├── api.py               # FastAPI app with lifespan, routes, orchestrator init
├── config.py            # Pydantic Settings from environment/.env
├── core/
│   ├── orchestrator.py          # Base orchestrator logic
│   └── enhanced_orchestrator.py # DB-integrated orchestrator (used in prod)
├── agents/
│   ├── base.py              # BaseAgent (abstract) and AIAgent (LLM-enabled)
│   └── implementations/     # Concrete agent implementations
├── schemas/
│   └── task_v1.py           # Pydantic models for V1 Task Spec
├── cwom/                    # Canonical Work Object Model (v0.1)
│   ├── __init__.py          # CWOM exports (all schemas, enums, primitives)
│   ├── enums.py             # Status, IssueType, ArtifactType, etc.
│   ├── primitives.py        # Actor, Ref, Source, Constraints, etc.
│   ├── repo.py, issue.py, run.py, artifact.py  # 7 CWOM object schemas
│   ├── context_packet.py, constraint_snapshot.py, doctrine_ref.py
│   ├── routes.py            # REST API endpoints (/cwom/*)
│   ├── services.py          # Service layer (CRUD + audit integration)
│   └── task_adapter.py      # Task ↔ CWOM bidirectional conversion
├── policy/
│   ├── __init__.py          # Exports PolicyError, evaluate
│   └── task_gate.py         # Pure policy evaluation + normalization
├── db/
│   ├── base.py              # SQLAlchemy engine, SessionLocal, init_database()
│   ├── models.py            # ORM models (Event, Workflow, Agent, Task, Job, Artifact)
│   ├── cwom_models.py       # CWOM SQLAlchemy models (7 object types + 6 join tables)
│   ├── audit_models.py      # AuditLog SQLAlchemy model
│   ├── audit_service.py     # AuditService for forensics and event sourcing
│   ├── services.py          # EventService, WorkflowService, AgentService, TaskService
│   └── migrations/          # Alembic migrations
├── worker/                  # Sprint-0 worker implementation (in progress)
│   └── ...                  # Task execution and trace artifact production
└── data/models/
    ├── events.py            # Event, EventTypes, EventPriority
    └── workflows.py         # Workflow definitions
```

### Key Patterns

- **EnhancedOrchestrator**: Global singleton initialized in `api.py` lifespan. Manages agents, workflows, and event queue. Stubs `_process_events()` for v0.
- **Database**: SQLite by default (`sqlite:///./devops_control_tower.db`). Set `DATABASE_URL` env var for Postgres. Alembic auto-converts async drivers to sync.
- **Agents**: Inherit from `BaseAgent` (simple) or `AIAgent` (LLM-powered). Must implement `_initialize()`, `_cleanup()`, `handle_event()`.
- **Task Intake (Stage 1)**: Tasks are submitted via `POST /tasks/enqueue`, validated against schema and policy, persisted with status `queued`. No execution yet.
- **Policy Gate**: Pure policy module (`policy/task_gate.py`) validates and normalizes tasks before persistence. The `evaluate()` function returns a normalized `TaskCreateLegacyV1` or raises `PolicyError` with stable error codes.

## JCT V1 Task Specification

The canonical task spec is documented in `docs/specs/task-spec-v1.md`. Key fields:

```json
{
  "version": "1.0",
  "requested_by": {"kind": "human|agent|system", "id": "...", "label": "..."},
  "objective": "Clear statement of success criteria",
  "operation": "code_change|docs|analysis|ops",
  "target": {"repo": "owner/name", "ref": "main", "path": ""},
  "constraints": {
    "time_budget_seconds": 900,
    "allow_network": false,
    "allow_secrets": false
  },
  "inputs": {},
  "metadata": {}
}
```

**Database Notes:**
- `TaskModel` in `db/models.py` - Flattened structure with all V1 fields
- SQLAlchemy reserves `metadata`, so DB column is `task_metadata` (mapped back to `metadata` in `to_dict()`)
- Statuses: `pending` → `queued` → `running` → `completed`/`failed`/`cancelled`

**Policy Gate Rules (`policy/task_gate.py`):**
- `operation` must be one of: `code_change`, `docs`, `analysis`, `ops`
- `target.repo` must match allowed prefixes (via `JCT_ALLOWED_REPO_PREFIXES` env var, comma-separated). Empty = deny all.
- `constraints.time_budget_seconds` must be 30-86400
- `allow_network=true` is DENIED in V1
- `allow_secrets=true` is DENIED in V1
- Error codes: `INVALID_OPERATION`, `REPO_NOT_ALLOWED`, `TIME_BUDGET_TOO_LOW`, `TIME_BUDGET_TOO_HIGH`, `NETWORK_ACCESS_DENIED`, `SECRETS_ACCESS_DENIED`

**Compatibility Layer (temporary, will be removed in V2):**
- `type` accepted as alias for `operation`
- `payload` accepted as alias for `inputs`
- `target.repository` accepted as alias for `target.repo`

## Contract Governance (IMPORTANT)

**Source of Truth:** The Pydantic model `TaskCreateLegacyV1` in `schemas/task_v1.py` is the contract for `POST /tasks/enqueue`. The code is the source of truth, not the markdown documentation. Changing the model shape is a breaking change.

**Read-Only Spec Document:** Do NOT modify `docs/specs/task-spec-v1.md` unless explicitly asked by the user. This document is read-only by convention to prevent spec drift.

**Contract Snapshot Test:** The test `tests/test_contract_snapshot.py` asserts the canonical fields exist in the JSON schema. If CI turns red on this test, a breaking change was introduced.

## Environment Configuration

Key settings from `config.py` (all have defaults):
- `DATABASE_URL` - Database connection (default: SQLite)
- `REDIS_URL` - Redis for caching/pubsub
- `DEBUG` - Enable debug mode
- `API_PORT` - Server port (default: 8000)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` - For AI agents
- `JCT_ALLOWED_REPO_PREFIXES` - Comma-separated list of allowed repo prefixes (e.g., `myorg/,partnerorg/`). Empty = deny all.

## Testing

pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.e2e`

Coverage target: 40% (configured in pyproject.toml)

Key test files:
- `tests/test_api_tasks.py` - Task enqueue endpoint tests
- `tests/test_policy.py` - Policy validation tests
- `tests/test_contract_snapshot.py` - Schema contract tests (prevents breaking changes)
- `tests/test_cwom_*.py` - CWOM schemas, DB models, API, integration
- `tests/test_audit_log.py` - AuditLog model and service tests
- `tests/test_sprint0.py` - Sprint-0 worker and trace tests

## Quick API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks/enqueue` | POST | Submit task (policy validated) |
| `/tasks/{id}` | GET | Retrieve task by ID |
| `/cwom/repos` | POST, GET | Create/list repos |
| `/cwom/issues` | POST, GET | Create/list issues |
| `/cwom/issues/{id}` | GET, PATCH | Get/update issue |
| `/cwom/runs` | POST, GET | Create/list runs |
| `/cwom/runs/{id}` | GET, PATCH | Get/update run |
| `/cwom/artifacts` | POST | Create artifact |
| `/cwom/context-packets` | POST | Create (immutable) |
| `/cwom/constraint-snapshots` | POST | Create (immutable) |
| `/cwom/doctrine-refs` | POST, GET | Create/list |

Use `?create_cwom=true` on `/tasks/enqueue` to auto-create CWOM objects.

## Canonical Work Object Model (CWOM) v0.1

CWOM is the "wiring standard" that makes features, agents, and automation composable. It defines 7 canonical object types with explicit causality.

**Spec:** `docs/cwom/cwom-spec-v0.1.md`
**Implementation Plan:** `docs/cwom/CWOM-IMPLEMENTATION-PLAN.md`
**Schemas:** `devops_control_tower/cwom/`

### Causality Chain
```
Issue + ContextPacket + ConstraintSnapshot + DoctrineRef → Run → Artifact
```

### Object Types
| Object | Purpose |
|--------|---------|
| **Repo** | Work container (codebase, docs base, project boundary) |
| **Issue** | Unit of intent (what we want) |
| **ContextPacket** | Versioned briefing (what we know + assumptions + instructions) |
| **ConstraintSnapshot** | Operating envelope (time, budget, health, tool limits) |
| **DoctrineRef** | Governing rules ("how we decide / how we work") |
| **Run** | Execution attempt (agent/human/CI doing work) |
| **Artifact** | Output of a Run (PR, commit, report, build) with verification |

### Key Principles
1. **Stable identity:** Every object has a globally unique ID (ULID)
2. **Explicit linkage:** Cross-object relationships use `Ref` type
3. **Immutability:** ContextPacket and ConstraintSnapshot are immutable once created
4. **Auditability:** Run inputs and outputs are explicit

### Usage Example
```python
from devops_control_tower.cwom import (
    Repo, Issue, Run, Artifact, Actor, Source, Ref,
    ObjectKind, IssueType, RunMode, ArtifactType, Executor
)

# Create Repo
source = Source(system="github", external_id="myorg/myrepo")
repo = Repo(name="My Repo", slug="myorg/myrepo", source=source)

# Create Issue
issue = Issue(
    repo=Ref(kind=ObjectKind.REPO, id=repo.id),
    title="Add /healthz endpoint",
    type=IssueType.FEATURE
)

# Create Run
actor = Actor(actor_kind="agent", actor_id="claude")
run = Run(
    for_issue=Ref(kind=ObjectKind.ISSUE, id=issue.id),
    repo=Ref(kind=ObjectKind.REPO, id=repo.id),
    mode=RunMode.AGENT,
    executor=Executor(actor=actor, runtime="container")
)

# Create Artifact
artifact = Artifact(
    produced_by=Ref(kind=ObjectKind.RUN, id=run.id),
    for_issue=Ref(kind=ObjectKind.ISSUE, id=issue.id),
    type=ArtifactType.PR,
    title="Add /healthz endpoint",
    uri="https://github.com/myorg/myrepo/pull/42"
)
```

### Database Models (Phase 2)

CWOM objects are persisted via SQLAlchemy models in `db/cwom_models.py`:

| Model | Table | Purpose |
|-------|-------|---------|
| `CWOMRepoModel` | `cwom_repos` | Work containers |
| `CWOMIssueModel` | `cwom_issues` | Units of intent |
| `CWOMContextPacketModel` | `cwom_context_packets` | Versioned briefings |
| `CWOMConstraintSnapshotModel` | `cwom_constraint_snapshots` | Operating constraints |
| `CWOMDoctrineRefModel` | `cwom_doctrine_refs` | Governance rules |
| `CWOMRunModel` | `cwom_runs` | Execution attempts |
| `CWOMArtifactModel` | `cwom_artifacts` | Run outputs |

**Join Tables** (for many-to-many relationships):
- `cwom_issue_context_packets`
- `cwom_issue_doctrine_refs`
- `cwom_issue_constraint_snapshots`
- `cwom_run_context_packets`
- `cwom_run_doctrine_refs`
- `cwom_context_packet_doctrine_refs`

**Migration:** `c3e8f9a21b4d_create_cwom_tables.py`

### Contract Governance
The Pydantic models in `cwom/` are the source of truth. `tests/test_cwom_contract.py` ensures schema stability. Database model tests are in `tests/test_cwom_db_models.py`.

### Task-CWOM Integration (Phase 4)

The task adapter (`cwom/task_adapter.py`) provides bidirectional mapping between JCT V1 Tasks and CWOM objects.

**Mapping Strategy:**
| JCT V1 Task | CWOM Equivalent |
|-------------|-----------------|
| `Task.objective` | `Issue.description` + `Issue.acceptance.criteria` |
| `Task.operation` | `Issue.type` (code_change→feature, docs→doc, analysis→research, ops→ops) |
| `Task.target` | `Repo` + `Issue.repo` ref |
| `Task.constraints` | `ConstraintSnapshot` |
| `Task.inputs` | `ContextPacket.inputs` |
| `Task.requested_by` | `Actor` on Issue/Run |

**Using CWOM with Tasks:**
```python
from devops_control_tower.cwom.task_adapter import task_to_cwom, issue_to_task

# Convert Task to CWOM objects
cwom_objects = task_to_cwom(task_spec, db_session)
# Returns: CWOMObjects(repo, issue, context_packet, constraint_snapshot)

# Convert CWOM objects back to Task format (for API compatibility)
task_dict = issue_to_task(issue, context_packet, constraint_snapshot, repo)
```

**API Usage:**
```bash
# Enqueue task with CWOM object creation
POST /tasks/enqueue?create_cwom=true

# Response includes CWOM IDs:
{
  "status": "success",
  "task_id": "...",
  "task": {...},
  "cwom": {
    "repo_id": "...",
    "issue_id": "...",
    "context_packet_id": "...",
    "constraint_snapshot_id": "..."
  }
}
```

**Database Link:**
- `TaskModel.cwom_issue_id` links tasks to their corresponding CWOM Issue
- Migration: `d4a9b8c2e5f6_add_cwom_issue_id_to_tasks.py`

### CWOM API Endpoints (Phase 3)

All CWOM objects are accessible via REST API under `/cwom` prefix. See Quick API Reference above for the full endpoint table.

**Immutability:** ContextPacket and ConstraintSnapshot return 405 Method Not Allowed for PUT/PATCH operations.

### CWOM Completion Status

**Assessment Date:** 2026-01-26 (Updated after Phase 1)

| Requirement | Status |
|------------|--------|
| Models for all 7 objects | ✅ Complete |
| Join tables (6 total) | ✅ Complete |
| Migrations apply cleanly | ✅ Complete (consolidated) |
| trace_id in models | ✅ Complete |
| CRUD tests cover linkage | 🟡 Partial (structure tests, not full round-trip) |
| AuditLog | ✅ Complete (Phase 2) |

**Migration Chain (after Phase 2):**
```
a1b2c3d4e5f6 (core: events, workflows, agents)
    ↓
b2f6a732d137 (tasks table)
    ↓
c3e8f9a21b4d (CWOM tables)
    ↓
d4a9b8c2e5f6 (cwom_issue_id to tasks)
    ↓
e5f6a7b8c9d0 (trace_id, jobs, artifacts)
    ↓
f7a8b9c0d1e2 (audit_log table)
```

**Resolved Issues (Phase 1):**
- ~~trace_id column mismatch~~ - All 7 CWOM models now have `trace_id` column
- ~~Two migration directories~~ - Consolidated to single `devops_control_tower/db/migrations/`
- ~~Core tables rely on init_database()~~ - New migration `a1b2c3d4e5f6` creates core tables

**Remaining Work:** See `docs/cwom/CWOM-COMPLETION-ROADMAP.md` for Phases 3-4 (integration tests, CI verification).

### Sprint-0: Trace ID and Worker

Sprint-0 adds end-to-end causality tracking via `trace_id`:

**New Tables (migration `e5f6a7b8c9d0`):**
- `jobs` - Execution tracking with worker assignment
- `artifacts` - Sprint-0 style outputs (simpler than CWOM artifacts)

**New Columns:**
- `tasks.trace_id` - Links task to trace
- `cwom_*.trace_id` - All CWOM tables get trace_id for unified traceability

**Models:** `JobModel` and `ArtifactModel` in `db/models.py`

## AuditLog (Phase 2)

AuditLog provides forensics and event sourcing for all CWOM operations. Every significant state change is recorded with before/after snapshots.

**Files:**
- `devops_control_tower/db/audit_models.py` - SQLAlchemy model
- `devops_control_tower/db/audit_service.py` - Service layer
- Migration: `f7a8b9c0d1e2_create_audit_log.py`

### AuditLogModel Schema

```python
AuditLogModel:
    id: str              # ULID
    ts: datetime         # Timestamp (indexed)
    actor_kind: str      # "human" | "agent" | "system"
    actor_id: str        # Who performed the action (indexed)
    action: str          # "created" | "updated" | "status_changed" | "deleted" | "linked" | "unlinked"
    entity_kind: str     # "Repo" | "Issue" | "Run" | etc. (indexed)
    entity_id: str       # ID of affected entity (indexed)
    before: dict | None  # State before action (JSON)
    after: dict | None   # State after action (JSON)
    note: str | None     # Human-readable note
    trace_id: str | None # For distributed tracing (indexed)
```

### AuditService Usage

```python
from devops_control_tower.db.audit_service import AuditService

audit = AuditService(db_session)

# Log operations
audit.log_create(entity_kind="Issue", entity_id=issue.id, after=issue.to_dict(), actor_kind="agent", actor_id="worker-1", trace_id="trace-123")
audit.log_status_change(entity_kind="Run", entity_id=run.id, old_status="planned", new_status="running", actor_kind="system", actor_id="worker-loop")
audit.log_update(entity_kind="Issue", entity_id=issue.id, before=old_state, after=new_state, actor_kind="human", actor_id="user-1")
audit.log_link(entity_kind="Issue", entity_id=issue.id, linked_kind="ContextPacket", linked_id=packet.id)

# Query operations
history = audit.query_by_entity("Issue", issue.id)
trace_events = audit.query_by_trace("trace-123")
user_actions = audit.query_by_actor("human", "user-1")
recent = audit.query_recent(limit=50, entity_kind="Run")
```

### CWOM Service Integration

All CWOM services automatically create audit log entries for create, status_change, update, and link operations. Pass `actor_kind`, `actor_id`, and `trace_id` to service methods for full traceability.

```python
from devops_control_tower.cwom.services import IssueService

issue_service = IssueService(db_session)
issue = issue_service.create(issue_data, actor_kind="human", actor_id="user-1", trace_id="trace-123")
issue_service.update_status(issue.id, "running", actor_kind="agent", actor_id="worker-1")
```

### Audit Indexes

The `audit_log` table has indexes on: `ts`, `actor_id`, `action`, `entity_kind`, `entity_id`, `trace_id`, plus composite indexes for common query patterns (`entity_kind + entity_id`, `actor_kind + actor_id`, `ts + action`, `entity_kind + entity_id + ts`).
