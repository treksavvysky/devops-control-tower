DevOps Control Tower (JCT) — System Overview for Codex

Purpose

The Jules Control Tower (JCT) is the orchestration backbone for an AI-assisted development environment.
Its job is to manage, execute, and record the flow of tasks through the system, eventually scaling to 60+ tasks per day across multiple agents and repos.

For v0, we only care about the spine:

/tasks/enqueue → Create DB row → Worker picks → Writes trace folder`

Once the spine is proven, the rest of the tower (agents, workflows, observability) becomes incremental muscle layered on top.

⸻

Core Components (Current)

1. FastAPI Application
	•	Provides REST endpoints.
	•	For v0, must expose:
	•	/health → returns {status: "ok"}
	•	/tasks/enqueue → accepts a minimal TaskSpec and returns a task_id.

2. EnhancedOrchestrator
	•	Central object that coordinates task flow.
	•	Responsible for:
	•	Initializing DB and internal structures.
	•	Accepting/enqueueing new tasks.
	•	Dispatching tasks to a worker loop.
	•	Writing traces after execution.
	•	For v0:
	•	We stubbed _process_events.
	•	We disabled agents that require LLM clients.

3. Task Model
	•	Stored in Postgres.
	•	Minimal required fields:
	•	id
	•	type
	•	payload
	•	status
	•	timestamps

4. Worker Loop
	•	Runs inside orchestrator (or later as a separate service).
	•	Picks the next queued task.
	•	Executes a simple handler.
	•	Writes a trace folder containing:
	•	input.json
	•	log.txt
	•	output.json
	•	Location: mounted volume /app/logs/<task_id>/…

5. Postgres
	•	Stores all task rows.
	•	Must be reachable via DATABASE_URL env variable.
	•	Local development should default to a sandboxed SQLite database (sqlite:///./devops_control_tower.db); point DATABASE_URL at Postgres only when explicitly targeting an external instance.

6. Docker Compose
	•	Runs:
	•	control-tower (FastAPI runtime)
	•	postgres
	•	redis (optional, not required for v0)
	•	Dockerfile must run:
    python -m devops_control_tower.main

Non-Goals for v0 (Codex should ignore for now)
	•	Infrastructure monitoring agent
	•	LLM-based workflows
	•	Jules Dev Kit agent
	•	Security scanning, deployment pipelines
	•	Event routing
	•	Workflow engine
	•	Observability stack (Prometheus/Grafana)

Codex must not work on these until the spine is validated.

⸻

What Codex Must Produce for v0

A. Reliable API routes
	•	/health route
	•	/tasks/enqueue route, returns task ID

B. Working orchestrator
	•	orchestrator.start() must not crash
	•	_process_events() must exist (stub is fine)
	•	Task enqueue method must:
	•	Insert DB row
	•	Return ID

C. Worker loop that:
	•	Picks pending tasks
	•	Executes a simple handler (e.g. echo payload)
	•	Writes a trace directory

D. Clean startup
	•	No abstract class instantiation
	•	No missing coroutine errors
	•	No missing routers
	•	App must stay running (no exit code 1/3 loops)

⸻

Architectural Intent

The JCT is meant to function as the brainstem of the entire automated development ecosystem.
Once the spine works, Codex will grow JCT into:
	•	A multi-agent orchestrator
	•	A workflow engine
	•	A DevOps automation hub
	•	The primary ingestion point for all AI-driven technical work

But v0 must be extremely small and correct, otherwise all later scaling becomes unstable.

⸻

Codex Success Criteria

Codex should consider the v0 spine complete when:
	1.	docker compose up → server starts with zero crashes
	2.	GET /health → {status:"ok"}
	3.	POST /tasks/enqueue → returns valid task ID
	4.	Postgres contains the new task row
	5.	Worker processes the task and produces a trace folder
	6.	Logs show no unexpected exceptions

Only after all of these are true should Codex move to v1 and beyond.

---

## Canonical Work Object Model (CWOM) v0.1

CWOM is the data model layer that will eventually bridge the task spine to a richer work representation. It provides 7 canonical object types with explicit causality.

**Current Status:** Phase 2 Complete (Pydantic schemas + SQLAlchemy models)

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

### Implementation Status
- **Phase 1 ✅:** Pydantic schemas in `devops_control_tower/cwom/`
- **Phase 2 ✅:** SQLAlchemy models in `devops_control_tower/db/cwom_models.py`
- **Phase 3 (Pending):** Services + API endpoints
- **Phase 4 (Pending):** Integration with existing Task system

### CWOM is NOT Required for v0 Spine

The v0 spine (`/tasks/enqueue → DB row → Worker → Trace folder`) does not depend on CWOM. CWOM is being built in parallel as the foundation for v1+ features like:
- Multi-agent orchestration
- Work lineage tracking
- Governance and policy enforcement
- Artifact verification

Codex should complete the v0 spine first before integrating CWOM.