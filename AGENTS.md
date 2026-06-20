# DevOps Control Tower (JCT) — System Overview for AI Agents

## Purpose

The Jules Control Tower (JCT) is the orchestration backbone for an AI-assisted development environment.
Its job is to manage, execute, and record the flow of tasks through the system, eventually scaling to 60+ tasks per day across multiple agents and repos.

**Current Focus (v0 Spine):**
```
/tasks/enqueue → Create DB row → Worker picks → Writes trace folder
```

Once the spine is proven, the rest of the tower (agents, workflows, observability) becomes incremental muscle layered on top.

## Project Status (2026-02-15)

| Component | Status | Notes |
|-----------|--------|-------|
| Task API (`/tasks/enqueue`) | ✅ Complete | Stage 1 done |
| Policy Gate | ✅ Complete | Validates tasks before persistence |
| CWOM v0.1 Schemas | ✅ Complete | 9 Pydantic models (including EvidencePack & ReviewDecision) |
| CWOM v0.1 DB Models | ✅ Complete | SQLAlchemy + 6 join tables |
| CWOM API Endpoints | ✅ Complete | Full REST API under `/cwom` |
| Task-CWOM Integration | ✅ Complete | Bidirectional mapping |
| Worker Loop | ✅ Complete | Sprint-0 implementation complete |
| AuditLog | ✅ Complete | Forensics & event sourcing for all CWOM operations |
| JCT MCP Server | ✅ Complete | 12 tools for Claude Code integration |
| CI Verification | ✅ Complete | Fresh DB migrations verified in GitHub Actions |
| Integration Tests | ✅ Complete | 55 integration tests for full CRUD & causality |

---

## Core Components (Current)

### 1. FastAPI Application
- Provides REST endpoints
- Exposes:
  - `/health` → returns `{status: "ok"}`
  - `/tasks/enqueue` → accepts TaskSpec, returns task_id
  - `/tasks/{id}` → retrieves task by ID
  - `/cwom/*` → CWOM object CRUD endpoints

### 2. EnhancedOrchestrator
- Central object that coordinates task flow
- Responsible for:
  - Initializing DB and internal structures
  - Accepting/enqueueing new tasks
  - Dispatching tasks to a worker loop
  - Writing traces after execution
- For v0: `_process_events()` stubbed, LLM agents disabled

### 3. Database Models

**Core Models (`db/models.py`):**
| Model | Table | Purpose |
|-------|-------|---------|
| `TaskModel` | `tasks` | JCT V1 Task records |
| `EventModel` | `events` | Event queue |
| `WorkflowModel` | `workflows` | Workflow definitions |
| `AgentModel` | `agents` | Agent registry |
| `JobModel` | `jobs` | Sprint-0 execution tracking |
| `ArtifactModel` | `artifacts` | Sprint-0 output references |

**CWOM Models (`db/cwom_models.py`):**
| Model | Table | Purpose |
|-------|-------|---------|
| `CWOMRepoModel` | `cwom_repos` | Work containers |
| `CWOMIssueModel` | `cwom_issues` | Units of intent |
| `CWOMContextPacketModel` | `cwom_context_packets` | Versioned briefings (immutable) |
| `CWOMConstraintSnapshotModel` | `cwom_constraint_snapshots` | Operating constraints (immutable) |
| `CWOMDoctrineRefModel` | `cwom_doctrine_refs` | Governance rules |
| `CWOMRunModel` | `cwom_runs` | Execution attempts |
| `CWOMArtifactModel` | `cwom_artifacts` | Run outputs |
| `CWOMEvidencePackModel` | `cwom_evidence_packs` | Proof of correctness (verdict) |
| `CWOMReviewDecisionModel` | `cwom_review_decisions` | Merge gate approval decision |

Plus 6 join tables for many-to-many relationships.

**Audit Models (`db/audit_models.py`):**
| Model | Table | Purpose |
|-------|-------|---------|
| `AuditLogModel` | `audit_log` | Forensics and event sourcing |

### 4. Worker Loop (Sprint-0)
- Picks next queued task
- Executes handler via StubExecutor
- Writes trace folder: `manifest.json`, `events.jsonl`, `trace.log`, `artifacts/output.md`, `evidence/verdict.json`
- Location: configured `JCT_TRACE_ROOT` base path (default `file:///var/lib/jct/runs/{run_id}/`)
- Propagates `trace_id` for end-to-end causality

### 5. Database
- Default: SQLite (`sqlite:///./devops_control_tower.db`)
- Production: PostgreSQL via `DATABASE_URL`
- Migrations: Alembic in `devops_control_tower/db/migrations/`

### 6. Docker Compose
- `control-tower` - FastAPI runtime
- `worker` - Independent worker process
- `postgres` - Database
- `redis` - Optional, not required for v0
- Entry: `python -m devops_control_tower.main`

## Non-Goals for v0
- Infrastructure monitoring agent
- LLM-based workflows
- Jules Dev Kit agent
- Security scanning, deployment pipelines
- Event routing
- Workflow engine
- Observability stack (Prometheus/Grafana)

Do not work on these until the spine is validated.

---

## What Must Be Produced for v0

### A. Reliable API routes ✅
- `/health` route
- `/tasks/enqueue` route, returns task ID
- `/tasks/{id}` route, retrieves task

### B. Working orchestrator ✅
- `orchestrator.start()` must not crash
- `_process_events()` exists (stub)
- Task enqueue inserts DB row and returns ID

### C. Worker loop ✅
- Picks pending tasks
- Executes handler (StubExecutor for v0)
- Writes trace directory, generates evidence, evaluates review policy
- Propagates `trace_id` for end-to-end causality

### D. Clean startup ✅
- No abstract class instantiation
- No missing coroutine errors
- No missing routers
- App stays running

---

## Architectural Intent

JCT functions as the brainstem of the automated development ecosystem.
Once the spine works, it grows into:
- A multi-agent orchestrator
- A workflow engine
- A DevOps automation hub
- The primary ingestion point for AI-driven technical work

v0 must be extremely small and correct—all later scaling depends on it.

---

## Success Criteria

v0 spine is complete when:
1. `docker compose up` → server starts with zero crashes
2. `GET /health` → `{status:"ok"}`
3. `POST /tasks/enqueue` → returns valid task ID
4. Database contains the new task row
5. Worker processes task and produces trace folder
6. Logs show no unexpected exceptions

Only after all of these are true should work proceed to v1 and beyond.

---

## Canonical Work Object Model (CWOM) v0.1

CWOM bridges the task spine to a richer work representation with 9 canonical object types and explicit causality.

**Current Status:** Phase 4 Complete, Phase 1 Remediation Complete, Phase 3 Integration Tests Complete, Phase 4 CI Verification Complete

### Causality Chain
```
Issue + ContextPacket + ConstraintSnapshot + DoctrineRef → Run → Artifact → EvidencePack → ReviewDecision
```

### Object Types
| Object | Purpose |
|--------|---------|
| **Repo** | Work container (codebase, docs base, project boundary) |
| **Issue** | Unit of intent (what we want) |
| **ContextPacket** | Versioned briefings (immutable) |
| **ConstraintSnapshot** | Operating envelope (immutable) |
| **DoctrineRef** | Governing rules |
| **Run** | Execution attempt |
| **Artifact** | Output of a Run |
| **EvidencePack** | Proof that Run outputs meet acceptance criteria |
| **ReviewDecision** | Approval decision for an EvidencePack |

### Implementation Status

| Phase | Status | Location |
|-------|--------|----------|
| 1. Pydantic Schemas | ✅ Complete | `devops_control_tower/cwom/` |
| 2. SQLAlchemy Models | ✅ Complete | `devops_control_tower/db/cwom_models.py` |
| 3. API Endpoints | ✅ Complete | `devops_control_tower/cwom/routes.py` |
| 4. Task-CWOM Integration | ✅ Complete | `devops_control_tower/cwom/task_adapter.py` |
| 5. AuditLog | ✅ Complete | `devops_control_tower/db/audit_service.py` |

### Resolved Issues (Phase 1 Complete)

1. ~~**trace_id mismatch**~~ ✅ All 7 CWOM models now have `trace_id` column
2. ~~**Two migration directories**~~ ✅ Consolidated to single `devops_control_tower/db/migrations/`
3. ~~**Core tables via init_database()**~~ ✅ New migration `a1b2c3d4e5f6` creates events, workflows, agents

### Task-CWOM Integration

```bash
# Enqueue with CWOM object creation
POST /tasks/enqueue?create_cwom=true
```

Creates: Repo, Issue, ContextPacket, ConstraintSnapshot
Links: `task.cwom_issue_id` → Issue

### CWOM API Endpoints

| Endpoint | Methods | Notes |
|----------|---------|-------|
| `/cwom/repos` | POST, GET | CRUD |
| `/cwom/issues` | POST, GET, PATCH | CRUD |
| `/cwom/context-packets` | POST, GET | Immutable |
| `/cwom/constraint-snapshots` | POST, GET | Immutable |
| `/cwom/doctrine-refs` | POST, GET | CRUD |
| `/cwom/runs` | POST, GET, PATCH | CRUD |
| `/cwom/artifacts` | POST, GET | CRUD |
| `/cwom/evidence-packs` | GET | CRUD |
| `/cwom/reviews` | POST, GET | CRUD |

---

## Key Documentation

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Detailed technical reference |
| `docs/cwom/CWOM-IMPLEMENTATION-PLAN.md` | Original CWOM implementation phases |
| `docs/cwom/CWOM-COMPLETION-ROADMAP.md` | Gap analysis and remediation plan |
| `docs/cwom/CWOM-DELIVERABLE-CHECKLIST.md` | Definition of Done for CWOM |
| `STAGE-01-SUMMARY.md` | Stage 1 completion evidence |

---

## AuditLog

Every CWOM state change is recorded in `audit_log` for forensics and event sourcing.

**Logged Actions:**
- `created` - Object creation
- `updated` - Object modification
- `status_changed` - Status transitions
- `deleted` - Object deletion
- `linked` - Relationship creation
- `unlinked` - Relationship removal

**Schema:**
```
audit_log:
  id, ts, actor_kind, actor_id, action,
  entity_kind, entity_id, before, after,
  note, trace_id
```

**Usage in CWOM services:**
All CWOM service methods accept `actor_kind`, `actor_id`, and `trace_id` parameters for audit tracking.

---

## Next Steps (Priority Order)

1. **Implement Real Executor (Claude Code)** - Replace `StubExecutor` with `ClaudeCodeExecutor` using subprocess calling `claude` CLI
2. **Setup Workspace Management** - Prepare repository checkouts for executor runs (git clones/worktrees)
3. **Refine Acceptance Criteria & Evidence Verification** - Leverage LLM-based verification for v1