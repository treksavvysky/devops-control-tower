# DevOps Control Tower

> **The centralized command center for AI-powered development operations**

A next-generation DevOps orchestration platform that integrates and manages all your AI development tools, workflows, and infrastructure from a single control plane.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![codecov](https://codecov.io/gh/your-org/devops-control-tower/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/devops-control-tower)

## 🎯 Vision & v0 Spine

DevOps Control Tower serves as the **nerve center** for modern AI-powered development operations. The project is currently focused on the **v0 Spine**—the minimal viable path through task intake, execution, proof evaluation, and review gating, turning fuzzy human/agent intent into audited, deterministic work.

```
/tasks/enqueue → Create DB row → Worker picks → Executes (Stub) → Writes trace folder → Prove & Review Gating
```

Once the spine is proven, the rest of the tower (observability, multi-agent workflows) becomes incremental muscle layered on top.

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DevOps Control Tower                     │
├─────────────────────────────────────────────────────────────┤
│  🎛️  FastAPI REST API (/tasks/enqueue, /tasks/{id})         │
├─────────────────────────────────────────────────────────────┤
│  🤖  JCT Worker Loop (Atomic Claims, Trace Folders)         │
├─────────────────────────────────────────────────────────────┤
│  🔗  Canonical Work Object Model (CWOM) v0.1                │
│     ├── Repo, Issue, ContextPacket, ConstraintSnapshot, DR  │
│     └── Run, Artifact, EvidencePack, ReviewDecision         │
├─────────────────────────────────────────────────────────────┤
│  📊  AuditLog & DB Layer (SQLite / PostgreSQL)              │
│     └── Forensics & Event Sourcing for state changes        │
├─────────────────────────────────────────────────────────────┘
```

## 🚀 Core Features

### 🎛️ Centralized Task Intake & Policy Gate
- **Governed Enqueueing**: API validates time budget, repo permissions, and blocks network/secrets access before persistence.
- **Task-CWOM Mapping**: Ingestion automatically creates matching work objects.
- **Idempotency**: Prevents duplicate executions via client-supplied idempotency keys.

### 🤖 Worker Loop (Sprint-0)
- **Atomic Claiming**: Uses optimistic locking to prevent double-claiming by concurrent workers.
- **Trace Storage**: Writes structured manifests, execution logs, and output artifacts under `/var/lib/jct/runs/{run_id}/` (configurable URI).
- **Prover & Review Gate**: Evaluates execution outputs against acceptance criteria to generate an `EvidencePack` and trigger auto-approval or manual `ReviewDecision`.

### 🔗 JCT MCP Server
- **Claude Code Integration**: Exposes 12 lifecycle, creation, observation, and review tools directly to Claude Code.
- **Agent Executions**: Lets agents list, claim, work, and complete JCT tasks natively.

### 📊 Audit Log
- **Event Sourcing**: Automatically captures `created`, `updated`, `status_changed`, `linked`, and `unlinked` events for all CWOM objects with before/after state snapshots.

## 🛠 Technology Stack

### Backend Core
- **Python 3.10+** (Python 3.12 recommended)
- **FastAPI** for API routes
- **SQLAlchemy 2.0** with **Alembic** migrations
- **PostgreSQL** (production) or **SQLite** (development)
- **Redis** for celery/broker tasks (optional)

### AI & Integrations
- **Model Context Protocol (MCP)** for Claude Code integration
- **LangChain / OpenAI / Claude APIs** (future phases)

## 📁 Project Structure

```
devops-control-tower/
├── devops_control_tower/          # Main application package
│   ├── api.py                     # FastAPI router & app lifespan
│   ├── config.py                  # Pydantic environment configuration
│   ├── core/                      # Core orchestrator singleton
│   ├── cwom/                      # CWOM schemas, routes, & service layers
│   │   ├── primitives.py          # Actor, Source, Ref definitions
│   │   ├── services.py            # Business logic validation & CRUD
│   │   └── task_adapter.py        # Bidirectional Task-to-CWOM mapper
│   ├── db/                        # Database connectivity & models
│   │   ├── cwom_models.py         # CWOM SQLAlchemy tables & join tables
│   │   ├── audit_models.py        # AuditLog table schema
│   │   └── migrations/            # Unified Alembic migration chain
│   ├── policy/                    # Policy gate logic (allowed operations/repos)
│   ├── mcp.py                     # FastMCP server for Claude Code
│   └── worker/                    # JCT Worker loop
│       ├── loop.py                # Poll, claim, and dispatch loop
│       ├── executor.py            # Execution drivers (StubExecutor)
│       └── pipeline.py            # Shared prove + review logic
├── docs/                          # Specs, test plans, and setup guides
├── scripts/                       # CLI scripts & verification tools
└── tests/                         # Full Pytest test suite (100+ tests)
```

## 🚦 Getting Started

### Prerequisites

- Python 3.10+ (Python 3.12 recommended)
- Git
- Docker & Docker Compose (optional)

### Quick Setup

Ensure you copy the environment file and initialize the database before running the tower.

```bash
# Clone the repository
git clone https://github.com/treksavvysky/devops-control-tower.git
cd devops-control-tower

# Setup virtual environment and dependencies using Poetry (recommended)
poetry install
cp .env.example .env

# Or using pip alternative
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt && pip install -e .
cp .env.example .env

# Apply migrations to create the database schema (defaults to SQLite)
alembic upgrade head
```

### Running the Services

1. **Start the API Server**:
   ```bash
   python3 -m devops_control_tower.main
   ```
   The API will be available at `http://localhost:8000`. Exposes `/health`, `/tasks`, and `/cwom` endpoints.

2. **Start the Worker**:
   ```bash
   python3 -m devops_control_tower.worker
   ```
   This will poll the database and process queued tasks.

3. **Start the MCP Server**:
   ```bash
   python3 -m devops_control_tower.mcp
   # Or using the command entrypoint
   jct-mcp
   ```

### Running Tests & Verification

Verify the entire setup works with:
```bash
# Run the test suite
pytest

# Verify Alembic migration path is clean and linear on a fresh DB
bash scripts/verify_db_fresh.sh
```

## 🤖 ChatGPT Custom GPT Integration

You can connect a ChatGPT custom GPT to the Control Tower so it can submit and track tasks via natural language. See the full setup guide:
**[docs/chatgpt-custom-gpt-setup.md](docs/chatgpt-custom-gpt-setup.md)**

## 🛡️ Security & Compliance

- **Policy Gating**: Strict enforcement of time budgets, operation filters, and repo prefixes.
- **Secrets & Network Isolation**: Blocked by default in v0 to ensure security boundaries.
- **Audit Trails**: Full transaction/history log in the `audit_log` table for compliance audits.

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.
