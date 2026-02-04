# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Control Tower (JCT - Jules Control Tower) is an orchestration backbone for AI-assisted development operations. It manages task execution and recording through a FastAPI-based system with database persistence.

**Current Focus (v0 Spine):** The minimal viable path is `/tasks/enqueue → DB row → Worker → Trace folder`. Advanced features (LLM workflows, monitoring agents, event routing) are disabled until this spine is validated.

**Next Stage:** Worker implementation to process queued tasks and produce trace artifacts.

## Common Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env

# Database
alembic upgrade head                      # Apply migrations

# Run
python -m devops_control_tower.main       # Start FastAPI server
docker compose up                         # Run with Docker

# Testing
pytest                                    # All tests
pytest tests/test_file.py                 # Single file
pytest tests/test_file.py::test_name -v   # Single test
pytest -k "pattern"                       # By name pattern
pytest --cov=devops_control_tower         # With coverage (40% minimum)

# Linting (also runs in CI via pre-commit)
black .
isort .
flake8 .
mypy devops_control_tower
```

## Architecture

```
devops_control_tower/
├── main.py              # Entry point
├── api.py               # FastAPI app with lifespan, routes, orchestrator init
├── config.py            # Pydantic Settings from environment/.env
├── schemas/task_v1.py   # V1 Task Spec contract (source of truth for POST /tasks/enqueue)
├── policy/task_gate.py  # Pure policy evaluation + normalization
├── cwom/                # Canonical Work Object Model - 7 object types with causality
├── db/
│   ├── base.py          # SQLAlchemy engine, SessionLocal
│   ├── models.py        # ORM: Event, Workflow, Agent, Task, Job, Artifact
│   ├── cwom_models.py   # CWOM SQLAlchemy models + join tables
│   ├── audit_models.py  # AuditLog for event sourcing
│   └── migrations/      # Alembic migrations (single directory)
├── core/
│   └── enhanced_orchestrator.py  # Global singleton, DB-integrated
├── agents/base.py       # BaseAgent (abstract), AIAgent (LLM-enabled)
└── worker/              # Sprint-0 worker (in progress)
```

### Key Patterns

- **Database**: SQLite by default. Set `DATABASE_URL` for Postgres.
- **Task Intake**: `POST /tasks/enqueue` → policy validation → DB persist with status `queued`
- **CWOM Causality**: `Issue + ContextPacket + ConstraintSnapshot + DoctrineRef → Run → Artifact`
- **AuditLog**: All CWOM operations auto-logged with before/after snapshots

## Contract Governance

**Source of Truth:** Pydantic models are the contract. Code is truth, not markdown.

- `TaskCreateLegacyV1` in `schemas/task_v1.py` - Task intake contract
- CWOM schemas in `cwom/` - Work object contracts
- `tests/test_contract_snapshot.py` - Prevents breaking schema changes
- `tests/test_cwom_contract.py` - CWOM schema stability

**Read-Only:** Do NOT modify `docs/specs/task-spec-v1.md` unless explicitly asked.

## Policy Gate Rules

The policy gate (`policy/task_gate.py`) validates tasks before persistence:

- `operation`: must be `code_change`, `docs`, `analysis`, or `ops`
- `target.repo`: must match `JCT_ALLOWED_REPO_PREFIXES` (empty = deny all)
- `constraints.time_budget_seconds`: 30-86400
- `allow_network=true`: DENIED in V1
- `allow_secrets=true`: DENIED in V1

Error codes: `INVALID_OPERATION`, `REPO_NOT_ALLOWED`, `TIME_BUDGET_TOO_LOW`, `TIME_BUDGET_TOO_HIGH`, `NETWORK_ACCESS_DENIED`, `SECRETS_ACCESS_DENIED`

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

## Key Environment Variables

```bash
DATABASE_URL=sqlite:///./devops_control_tower.db  # Or postgresql://...
JCT_ALLOWED_REPO_PREFIXES=myorg/,partnerorg/      # Empty = deny all repos
DEBUG=false
API_PORT=8000
OPENAI_API_KEY=...     # For AI agents
ANTHROPIC_API_KEY=...  # For AI agents
```

## Testing Notes

- pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.e2e`
- Coverage minimum: 40%
- CI uses Postgres; local dev uses SQLite by default

Key test files:
- `tests/test_api_tasks.py` - Task enqueue endpoint
- `tests/test_policy.py` - Policy validation
- `tests/test_contract_snapshot.py` - Schema contract (prevents breaking changes)
- `tests/test_cwom_*.py` - CWOM schemas, DB, API, integration
- `tests/test_audit_log.py` - AuditLog model and service

## Stage Progress

- **Stage 1** (Complete): Task Contract + Intake Gate
- **CWOM v0.1** (Phases 1-4 Complete): Schemas, DB models, API, Task-CWOM integration
- **AuditLog** (Complete): Event sourcing for all CWOM operations

Progress docs:
- `STAGE-01-SUMMARY.md`
- `docs/cwom/CWOM-IMPLEMENTATION-PLAN.md`
- `docs/cwom/CWOM-COMPLETION-ROADMAP.md`

## CWOM Reference

CWOM is the "wiring standard" for composable work objects. Full spec: `docs/cwom/cwom-spec-v0.1.md`

| Object | Purpose |
|--------|---------|
| **Repo** | Work container (codebase, project boundary) |
| **Issue** | Unit of intent (what we want) |
| **ContextPacket** | Versioned briefing (immutable once created) |
| **ConstraintSnapshot** | Operating envelope (immutable once created) |
| **DoctrineRef** | Governing rules |
| **Run** | Execution attempt |
| **Artifact** | Output of a Run |

```python
from devops_control_tower.cwom import (
    Repo, Issue, Run, Artifact, Actor, Source, Ref,
    ObjectKind, IssueType, RunMode, ArtifactType, Executor
)
```

### Task-CWOM Adapter

```python
from devops_control_tower.cwom.task_adapter import task_to_cwom, issue_to_task

# Task → CWOM objects
cwom_objects = task_to_cwom(task_spec, db_session)

# CWOM → Task format
task_dict = issue_to_task(issue, context_packet, constraint_snapshot, repo)
```

### AuditService

```python
from devops_control_tower.db.audit_service import AuditService

audit = AuditService(db_session)
audit.log_create(entity_kind="Issue", entity_id=id, after=data, actor_kind="agent", actor_id="worker-1")
audit.log_status_change(entity_kind="Run", entity_id=id, old_status="planned", new_status="running", ...)
history = audit.query_by_entity("Issue", issue_id)
```

## Migration Chain

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
