# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Control Tower (JCT - Jules Control Tower) is an orchestration backbone for AI-assisted development operations. It manages task execution and recording through a FastAPI-based system with database persistence.

**Current Focus (v0 Spine):** The minimal viable path is `/tasks/enqueue → DB row → Worker → Trace folder`. Advanced features (LLM workflows, monitoring agents, event routing) are disabled until this spine is validated.

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
pytest tests/test_tasks_enqueue.py        # task enqueue tests
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
│   ├── __init__.py          # Schema exports
│   └── task_v1.py           # V1 Task Pydantic models (TaskCreateV1, TaskResponseV1)
├── policies/
│   ├── __init__.py          # Policy exports
│   └── task_policy.py       # Task intake policy validation (allow/deny rules)
│   ├── task_v1.py 
├── db/
│   ├── base.py              # SQLAlchemy engine, SessionLocal, init_database()
│   ├── models.py            # ORM models (Event, Workflow, Agent, TaskModel)
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
- **Task Spec V1**: Canonical schema defined in `docs/specs/task-spec-v1.md`. All tasks use structured `requested_by` (kind/id/label), required `objective`, normalized `operation` (code_change|docs|analysis|ops), and conservative `constraints` defaults.

## API Endpoints

### System
- `GET /health`, `GET /healthz` - Health checks returning `{"status": "ok"}`
- `GET /status` - System status including orchestrator and agent states
- `GET /version` - Application version

### Tasks (JCT V1 Task Spec)
- `POST /tasks/enqueue` - Enqueue a task for execution (V0 spine: enqueue → DB row → Worker → Trace)
- `GET /tasks` - List tasks with optional filtering (status, operation, requester_kind, target_repo)
- `GET /tasks/{task_id}` - Get specific task details
- `PATCH /tasks/{task_id}/status` - Update task status and execution details

### Agents
- `GET /agents` - List all registered agents
- `GET /agents/{name}` - Get detailed agent information
- `POST /agents/{name}/start` - Start a specific agent
- `POST /agents/{name}/stop` - Stop a specific agent

### Events
- `GET /events` - List events with optional filtering
- `GET /events/{event_id}` - Get specific event
- `POST /events` - Create and queue events

### Workflows
- `GET /workflows` - List active workflows
- `POST /tasks/enqueue` - **Stage 1** Task intake endpoint (validates, persists, returns task_id)

### Task Enqueue Endpoint (V1)

`POST /tasks/enqueue` accepts a V1 Task spec (see `docs/specs/task-spec-v1.md`):

```json
{
  "type": "build",           // Required: build, deploy, test, scan, cleanup, notify
  "payload": {...},          // Required: task-specific data
  "priority": "medium",      // Optional: low, medium, high, critical
  "source": "api",           // Optional: origin identifier
  "target": {...},           // Optional: repository, ref, environment, path
  "options": {...},          // Optional: timeout, retries, sandbox settings
  "metadata": {...},         // Optional: arbitrary key-value data
  "tags": ["ci"],            // Optional: categorization tags
  "idempotency_key": "...",  // Optional: for deduplication
  "callback_url": "..."      // Optional: webhook on completion
}
```

Returns: `{"task_id": "uuid", "status": "queued", "created_at": "..."}`
- `GET /workflows/{workflow_id}` - Get specific workflow details

## Environment Configuration

Key settings from `config.py` (all have defaults):
- `DATABASE_URL` - Database connection (default: SQLite)
- `REDIS_URL` - Redis for caching/pubsub
- `DEBUG` - Enable debug mode
- `API_PORT` - Server port (default: 8000)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` - For AI agents

## JCT V1 Task Specification

The canonical task spec is fully documented in `docs/specs/task-spec-v1.md`. Key fields:

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

**Database Schema:**
- `TaskModel` in `db/models.py` - Flattened structure with all V1 fields
- `TaskService` in `db/services.py` - CRUD with idempotency support
- Statuses: `pending` → `queued` → `running` → `completed`/`failed`/`cancelled`
- Note: SQLAlchemy reserves `metadata`, so DB column is `task_metadata` (mapped back to `metadata` in `to_dict()`)

**Validation:**
- Pydantic models in `schemas/task_v1.py` enforce all constraints
- `operation` uses `Literal` type for strict validation (only 4 allowed values)
- Conservative defaults: 15min timeout, no network, no secrets

## Testing

pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.e2e`

Coverage target: 40% (configured in pyproject.toml)

Key test files:
- `tests/test_tasks_enqueue.py` - Task enqueue endpoint tests
- `tests/test_task_policy.py` - Policy validation tests

