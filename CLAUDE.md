# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Control Tower (JCT - Jules Control Tower) is an orchestration backbone for AI-assisted development operations. It manages task execution and recording through a FastAPI-based system with database persistence.

**Current Focus (v0 Spine):** The minimal viable path through all 5 pipeline steps. Advanced features (LLM workflows, monitoring agents, event routing) are disabled until the spine is validated.

**v0 Pipeline Status:** Steps 1-4 complete. Step 5 (Review) next.

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
python -m devops_control_tower.worker     # Start worker (processes queued tasks)
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
├── cwom/                # Canonical Work Object Model - 8 object types with causality
├── db/
│   ├── base.py          # SQLAlchemy engine, SessionLocal
│   ├── models.py        # ORM: Event, Workflow, Agent, Task, Job, Artifact
│   ├── cwom_models.py   # CWOM SQLAlchemy models + join tables
│   ├── audit_models.py  # AuditLog for event sourcing
│   └── migrations/      # Alembic migrations (single directory)
├── core/
│   └── enhanced_orchestrator.py  # Global singleton, DB-integrated
├── agents/base.py       # BaseAgent (abstract), AIAgent (LLM-enabled)
└── worker/              # v0 Worker
    ├── loop.py          # Main worker loop (poll, claim, execute, prove, complete)
    ├── executor.py      # Task executors (StubExecutor for v0)
    ├── prover.py        # Proof evaluation → EvidencePack creation
    └── storage.py       # Trace storage (file:// for v0, s3:// for v2)
```

### Key Patterns

- **Database**: SQLite by default. Set `DATABASE_URL` for Postgres.
- **Task Intake**: `POST /tasks/enqueue` → policy validation → DB persist with status `queued`
- **Worker**: Polls for `queued` tasks → creates CWOM Run → executes → proves → writes trace folder
- **Prove**: Evaluates Run outputs → creates EvidencePack with verdict (pass/fail/partial)
- **Trace Storage**: URI-based (`file://` v0, `s3://` v2). Run stores `artifact_root_uri`.
- **CWOM Causality**: `Issue + ContextPacket + ConstraintSnapshot + DoctrineRef → Run → Artifact → EvidencePack`
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
| `/cwom/evidence-packs/{id}` | GET | Get evidence pack |
| `/cwom/evidence-packs` | GET | List evidence packs |
| `/cwom/runs/{id}/evidence-pack` | GET | Get evidence pack for run |
| `/cwom/issues/{id}/evidence-packs` | GET | List evidence packs for issue |

Use `?create_cwom=true` on `/tasks/enqueue` to auto-create CWOM objects.

## Key Environment Variables

```bash
DATABASE_URL=sqlite:///./devops_control_tower.db  # Or postgresql://...
JCT_ALLOWED_REPO_PREFIXES=myorg/,partnerorg/      # Empty = deny all repos
JCT_TRACE_ROOT=file:///var/lib/jct/runs           # Trace storage (file:// or s3://)
WORKER_POLL_INTERVAL=5                             # Seconds between polls
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

Integration test scripts:
- `scripts/test_intake.sh` - End-to-end intake flow (9 tests)
- `scripts/test_worker.sh` - End-to-end worker flow (7 tests)
- `scripts/test_prove.sh` - End-to-end prove flow (8 tests)

## v0 Pipeline Steps

The core operating model: **Turn fuzzy intent into audited, deterministic work.**

| Step | Name | Status | Description |
|------|------|--------|-------------|
| 1 | **Intake** | ✅ Complete | Task submission → Context Packet → Policy validation → DB persist |
| 2 | **Gate** | ✅ Complete | Policy + feasibility checks (repo allowlist, time budgets, no secrets/network) |
| 3 | **Work** | ✅ Complete | Worker claims task → creates Run → executes → writes trace folder |
| 4 | **Prove** | ✅ Complete | Prover evaluates Run → creates EvidencePack with verdict |
| 5 | **Review** | 🔲 Next | Merge gate - human/agent approval before PR merge |

### Step Details

**Step 1: Intake → Context Packet**
- `POST /tasks/enqueue` with task spec
- Creates CWOM Issue + ContextPacket (with `?create_cwom=true`)
- Idempotent via `idempotency_key`
- AuditLog records creation

**Step 2: Gate → Policy + Feasibility**
- Policy gate validates: operation type, repo allowlist, time budget, no network/secrets
- Returns structured error codes on rejection
- Runs synchronously during intake

**Step 3: Work → Trace Folder**
- Worker polls for `queued` tasks
- Claims task atomically (optimistic locking)
- Creates CWOM Run with `artifact_root_uri`
- Executes via executor (StubExecutor in v0)
- Writes trace folder: manifest.json, events.jsonl, trace.log, artifacts/

**Step 4: Prove → Evidence Pack**
- Prover evaluates Run outputs against acceptance criteria
- v0 automated checks: run status, no failure, evidence artifacts exist
- Acceptance criteria marked "unverified" (v1 will use LLM evaluation)
- Creates EvidencePack with verdict: `pass`, `fail`, `partial`, or `pending`
- Writes evidence folder: verdict.json, collected.json, criteria/

**Step 5: Review → Merge Gate** (Next)
- Human or agent reviews EvidencePack
- Approves/rejects based on verdict and criteria
- Gates PR merge (integration with GitHub)
- Records review decision in AuditLog

## Stage Progress

- **CWOM v0.1** (Complete): 8 object types with causality chain
- **AuditLog** (Complete): Event sourcing for all CWOM operations
- **v0 Pipeline** (Steps 1-4 Complete): Intake → Gate → Work → Prove

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
| **EvidencePack** | Proof that Run outputs meet acceptance criteria |

**Causality Chain:**
```
Issue + ContextPacket + ConstraintSnapshot + DoctrineRef → Run → Artifact → EvidencePack
```

```python
from devops_control_tower.cwom import (
    Repo, Issue, Run, Artifact, EvidencePack,
    Actor, Source, Ref, Verdict, CriterionStatus,
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
    ↓
g8b9c0d1e2f3 (FK tasks.cwom_issue_id)
    ↓
h9c0d1e2f3a4 (artifact_root_uri on runs)
    ↓
i0d1e2f3a4b5 (evidence_packs table)
```

## Worker Reference

```bash
# Start worker
python -m devops_control_tower.worker

# With options
python -m devops_control_tower.worker --poll-interval 10 --executor stub
```

### Trace Folder Structure

```
/var/lib/jct/runs/{run_id}/
├── manifest.json       # Run metadata, timestamps, status, result
├── events.jsonl        # Structured events (machine-parseable)
├── trace.log           # Human-readable execution log
├── context.json        # ContextPacket snapshot (if available)
├── constraints.json    # ConstraintSnapshot (if available)
├── artifacts/          # Output files from executor
│   └── output.md       # Stub executor placeholder
└── evidence/           # Proof artifacts (from Prover)
    ├── verdict.json    # Verdict and summary
    ├── collected.json  # Evidence items found/missing
    └── criteria/       # Per-criterion evaluation results
        └── criterion_N.json
```

### Worker Flow

```
1. Poll: Find tasks with status='queued'
2. Claim: Atomically update to 'running' (optimistic locking)
3. Create Run: CWOM Run with artifact_root_uri
4. Execute: StubExecutor (v0) or real executor (v1+)
5. Write trace: Folder with manifest, events, artifacts
6. Prove: Evaluate outputs → create EvidencePack with verdict
7. Complete: Update task/run/issue status to 'done'/'completed'
```

### EvidencePack Verdicts

| Verdict | Meaning |
|---------|---------|
| `pass` | All automated checks passed, evidence requirements met |
| `fail` | Run failed or errored |
| `partial` | Some evidence missing |
| `pending` | Awaiting evaluation (not used in v0) |

v0 marks acceptance criteria as "unverified" - LLM evaluation comes in v1.
