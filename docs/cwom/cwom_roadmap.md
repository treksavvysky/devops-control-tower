Set it up as a shared kernel + a thin service. CWOM is a contract first; an API second; a UI last.

1) Repo decision: existing vs new

Best default: embed CWOM into jules-control-tower

CWOM is the “work substrate” JCT will orchestrate anyway (enqueue → run → artifacts → traces). Putting it inside JCT avoids the classic failure mode: a “schema repo” that never gets wired into the execution engine.

Why this is the right first move
	•	JCT already wants FastAPI + Postgres + Celery + Redis. CWOM objects map cleanly to DB tables and API resources.
	•	You get immediate leverage: every enqueue/run can start emitting CWOM objects on day one.
	•	One deployment, one auth story, one source of truth.

When to create a new repo

Create a separate repo only if you want CWOM to be used by multiple independent services (Scriptoria, vpsmanager, etc.) and you plan to publish it as a reusable library with strict semantic versioning.

If you do split later, do it as:
	•	cwom-spec (schemas + docs)
	•	cwom-core (Python package with Pydantic models + validation)
…and JCT depends on cwom-core.

But for v0.1: put it in JCT and avoid “spec drift.”

⸻

2) Do we need a web app or an API?

You need an API immediately

Because agents and tools can’t “click around”; they need CRUD + query + linkage.

Minimum endpoints (v0.1):
	•	POST /repos GET /repos/{id}
	•	POST /issues GET /issues/{id} PATCH /issues/{id}
	•	POST /context_packets GET /context_packets/{id}
	•	POST /constraint_snapshots GET /constraint_snapshots/{id}
	•	POST /doctrine_refs GET /doctrine_refs/{id}
	•	POST /runs PATCH /runs/{id} GET /runs/{id}
	•	POST /artifacts GET /artifacts/{id}

Add query endpoints early:
	•	GET /issues?repo_id=&status=&tag=
	•	GET /runs?issue_id=&status=
	•	GET /artifacts?run_id=&type=

You do not need a web UI yet

UI is a force multiplier later. Early on it’s a distraction that hardens bad assumptions.

A tiny compromise that’s worth it early:
	•	OpenAPI docs (FastAPI gives you this for free)
	•	An admin read-only “list & inspect” page can come later.

⸻

3) Tech stack (boring, stable, works)

Since your stack is already converging here, keep it consistent:

Service
	•	Python 3.12
	•	FastAPI (API layer)
	•	Pydantic v2 (object models + validation)
	•	SQLAlchemy 2.0 (ORM) or SQLModel if you want speed/ergonomics
	•	Alembic (migrations)

Data
	•	PostgreSQL (source of truth)
	•	Optional later: JSONB columns for meta + flexible fields

Async execution (already in your orbit)
	•	Celery + Redis
	•	Runs can be “state machines” updated by workers

Packaging
	•	Monorepo layout is fine (your JCT plan already mentions turborepo structure). CWOM can live at:
	•	services/jct/cwom/ (models, schemas, repos)
	•	services/jct/api/ (routers)
	•	services/jct/db/ (tables, migrations)

Testing / quality gates
	•	pytest
	•	ruff (lint/format)
	•	mypy (optional but nice once schema stabilizes)

⸻

4) Implementation plan: “steel first, polish later”

Phase A — Lock the spec (1–2 sessions)
	•	Create cwom/spec/:
	•	cwom_v0_1.md (human spec + invariants)
	•	jsonschema/ for each object (optional early; Pydantic can be the source)
	•	Define enums (Status, IssueType, ArtifactType) and the shared primitives (Ref, Actor, Source).

Output: a spec you can’t wiggle out of.

Phase B — Core models + DB (minimum viable substrate)
	•	Pydantic models for the 7 objects
	•	Postgres tables:
	•	repos, issues, context_packets, constraint_snapshots, doctrine_refs, runs, artifacts
	•	Use link tables instead of arrays-in-JSON for queries:
	•	issue_context_packets(issue_id, context_packet_id)
	•	issue_doctrines(issue_id, doctrine_id)
	•	run_context_packets(run_id, context_packet_id)
	•	etc.

Rule: meta can be JSONB; relationships should be relational.

Phase C — API CRUD + query
	•	Implement the endpoints above.
	•	Add server-side invariants:
	•	ContextPacket immutable once “sealed”
	•	ConstraintSnapshot immutable
	•	Run must reference issue + at least one context packet (or allow empty only for bootstrapping)

Phase D — Wire into the execution engine
	•	Update /enqueue (or /tasks/enqueue) to:
	1.	create Issue (or link to existing)
	2.	create ContextPacket
	3.	create Run in ready
	4.	Celery worker picks it up, transitions Run → running → done/failed
	5.	store Artifacts emitted by the worker

This is where CWOM becomes real instead of ceremonial.

⸻

5) What “setup” looks like in your world (practically)

If we use JCT as the host:
	•	Add a cwom module to the existing JCT service.
	•	Add migrations.
	•	Extend your current /enqueue to emit CWOM objects.
	•	Start capturing artifacts even if they’re just “logs” and “links” at first.

If you insist on a separate repo anyway:
	•	Make it a library, not a service:
	•	cwom-core (Pydantic models + validators + JSONSchema export)
	•	JCT imports it.
	•	The service still lives in JCT.

⸻

6) The real payoff: why this setup is correct

This approach makes CWOM:
	•	authoritative (stored in Postgres, not scattered across tools)
	•	queryable (relational links, not JSON soup)
	•	agent-usable (API-first)
	•	incrementally adoptable (you can start with Issues + Runs + Artifacts, then add the rest)

It also lines up with your trajectory: JCT is the orchestration spine; CWOM is the data spine. Put spines together unless you enjoy reconstructive surgery.

Next direction of travel: scaffold the DB tables + Pydantic models first, then wire /enqueue to create Issue → ContextPacket → Run. That gives you a living CWOM within a day of work, not a doc that slowly fossilizes.
