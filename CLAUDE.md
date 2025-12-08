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

## API Endpoints

- `GET /health`, `GET /healthz` - Health checks returning `{"status": "ok"}`
- `GET /status` - System status including orchestrator and agent states
- `GET /agents`, `GET /agents/{name}` - Agent listing and details
- `POST /events` - Create and queue events
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

## Environment Configuration

Key settings from `config.py` (all have defaults):
- `DATABASE_URL` - Database connection (default: SQLite)
- `REDIS_URL` - Redis for caching/pubsub
- `DEBUG` - Enable debug mode
- `API_PORT` - Server port (default: 8000)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` - For AI agents

## Testing

pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.e2e`

Coverage target: 40% (configured in pyproject.toml)

Key test files:
- `tests/test_tasks_enqueue.py` - Task enqueue endpoint tests
- `tests/test_task_policy.py` - Policy validation tests
