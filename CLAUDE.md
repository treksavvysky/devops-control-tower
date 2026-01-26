# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Control Tower (JCT - Jules Control Tower) is an orchestration backbone for AI-assisted development operations. It manages task execution and recording through a FastAPI-based system with database persistence.

**Current Focus (v0 Spine):** The minimal viable path is `/tasks/enqueue → DB row → Worker → Trace folder`. Advanced features (LLM workflows, monitoring agents, event routing) are disabled until this spine is validated.

## Stage-Based Development

Development proceeds in stages. Each stage has a summary document tracking progress, decisions, and verification evidence.

**Stage Progress Documents:**
- `STAGE-01-SUMMARY.md` - Task Contract + Intake Gate (✅ COMPLETE)

**Stage 1 (Complete):** V1 Task Spec contract defined, policy gate implemented, `POST /tasks/enqueue` persists validated tasks, idempotency enforced, `GET /tasks/{id}` retrieves stored records.

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
│   ├── repo.py              # Repo schema
│   ├── issue.py             # Issue schema
│   ├── context_packet.py    # ContextPacket schema
│   ├── constraint_snapshot.py # ConstraintSnapshot schema
│   ├── doctrine_ref.py      # DoctrineRef schema
│   ├── run.py               # Run schema
│   └── artifact.py          # Artifact schema
├── policy/
│   ├── __init__.py          # Exports PolicyError, evaluate
│   └── task_gate.py         # Pure policy evaluation + normalization
├── db/
│   ├── base.py              # SQLAlchemy engine, SessionLocal, init_database()
│   ├── models.py            # ORM models (Event, Workflow, Agent, Task)
│   ├── cwom_models.py       # CWOM SQLAlchemy models (7 object types + 6 join tables)
│   ├── services.py          # EventService, WorkflowService, AgentService, TaskService
│   └── migrations/          # Alembic migrations
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
- `tests/test_contract_snapshot.py` - Schema contract tests
- `tests/test_cwom_contract.py` - CWOM Pydantic schema contract tests
- `tests/test_cwom_db_models.py` - CWOM SQLAlchemy model tests

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
