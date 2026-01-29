The right move is to run a tight verification protocol that answers, unambiguously: “Do we have the CWOM v0.1 schema, are relationships queryable, do migrations apply cleanly, do CRUD tests prove the contract?”

Below is the exact checklist + commands + what the schema must contain (including an AuditLog that pays for itself the first time something weird happens at 2am).

⸻

0) Definition of Done (DoD)

Pass means all of this is true:
	1.	SQLAlchemy models exist for:

	•	Repo, Issue, ContextPacket, Run, Artifact, ConstraintSnapshot, DoctrineRef
	•	(Optional but recommended) AuditLog

	2.	Alembic migrations:

	•	alembic upgrade head succeeds on a fresh DB
	•	alembic downgrade -1 works at least one step (sanity)
	•	alembic history shows a coherent chain (no forks unless intentional)

	3.	DB invariants:

	•	Primary keys, FKs, enums (or constrained strings), timestamps
	•	Relationship tables (join tables) exist where needed
	•	Immutables are enforced (at least by convention; better via DB constraints/triggers later)

	4.	CRUD tests pass:

	•	create/read/update where allowed
	•	ContextPacket + ConstraintSnapshot: update should be blocked or treated as new-row semantics
	•	Run emits Artifact and links correctly

⸻

1) The “Reality Check” Protocol (fast, brutal)

A. Locate the deliverables

Run:

# where are the models?
rg -n "class Repo|class Issue|class ContextPacket|class Run|class Artifact|class ConstraintSnapshot|class DoctrineRef" services -S

# where are the migrations?
ls -la services/jct/alembic/versions
rg -n "create_table\(|op\.create_table" services/jct/alembic/versions -S

# do we have tests?
ls -la services/jct/tests
rg -n "test_.*(crud|repo|issue|run|artifact|context|doctrine|constraint)" services/jct/tests -S

B. Fresh DB migration test (the only one that matters)

Use a clean database (local Postgres or docker):

# start infra (example)
docker compose up -d db

# wipe and recreate the schema (choose ONE method)
dropdb jct_test && createdb jct_test
# or if using a dedicated test container, recreate it cleanly

export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/jct_test"

alembic upgrade head

Fail conditions:
	•	missing revision, missing env.py config, import errors
	•	enum creation issues
	•	FK dependency order issues

C. Smoke downgrade (catches half-baked migrations)

alembic downgrade -1
alembic upgrade head

D. Run CRUD tests

pytest -q

If there are no tests, that’s a “not done” even if migrations apply.

⸻

2) What the Schema Must Look Like (minimum acceptable)

You don’t need perfection yet, but you need queryable relationships without JSON soup.

Tables (core)
	•	repos
	•	issues
	•	context_packets
	•	constraint_snapshots
	•	doctrine_refs
	•	runs
	•	artifacts

Join tables (recommended v0.1)

These are what prevent pain later:
	•	issue_context_packets (issue ↔ context_packet)
	•	issue_doctrine_refs (issue ↔ doctrine_ref)
	•	issue_constraint_snapshots (issue ↔ constraint_snapshot)
	•	run_context_packets (run ↔ context_packet)
	•	run_doctrine_refs (run ↔ doctrine_ref)

You can temporarily store refs as JSONB arrays, but you’ll regret it the moment you need analytics or “find all runs governed by doctrine X”.

Key constraints that matter immediately
	•	issues.repo_id FK → repos.id
	•	context_packets.for_issue_id FK → issues.id
	•	runs.for_issue_id FK → issues.id
	•	runs.repo_id FK → repos.id (redundant but indexing gold)
	•	artifacts.produced_by_run_id FK → runs.id
	•	artifacts.for_issue_id FK → issues.id

Column expectations (v0.1)
	•	id: ULID or UUID string (consistent across all tables)
	•	created_at, updated_at: timezone-aware
	•	status enums: keep canonical statuses (or constrained varchar)
	•	meta: JSONB
	•	tags: either JSONB array or separate table; JSONB is fine v0.1

⸻

3) AuditLog (strongly recommended)

This is the cheapest way to get “forensics” and later “event sourcing” without committing to a full event system.

Minimum AuditLog table
	•	id
	•	ts
	•	actor_kind, actor_id
	•	action (created/updated/status_changed/etc.)
	•	entity_kind, entity_id
	•	before JSONB (nullable)
	•	after JSONB (nullable)
	•	note text (nullable)
	•	indexes on (entity_kind, entity_id), ts

Even if Claude didn’t build this: you should.

⸻

4) CRUD Test Coverage (what “basic” should include)

At minimum, tests should prove:

Repo + Issue
	•	create repo
	•	create issue under repo
	•	query issue by repo_id

ContextPacket
	•	create context packet for issue
	•	verify immutability expectation:
	•	either updates are blocked (preferred), or update is allowed but flagged (acceptable temporarily)
	•	better: tests enforce “create new version instead of update”

ConstraintSnapshot
	•	create snapshot
	•	link to issue and/or run
	•	should be immutable (same notes as above)

DoctrineRef
	•	create doctrine
	•	link to issue
	•	query issues by doctrine (join table proves its worth)

Run + Artifact
	•	create run for issue with context/doctrine refs
	•	update run status ready → running → done
	•	create artifact produced_by run
	•	query artifacts by run_id and issue_id

If Claude wrote “CRUD tests” but they only test one table in isolation, that’s not sufficient. The whole point is linkage.

⸻

5) Common “Claude Code did something” failure modes

These are the usual traps. If you see these, it’s not done:
	•	Refs stored only as JSON (no join tables) while claiming “queryable”
	•	Missing foreign keys (“we’ll handle it in app logic”) → no, you won’t
	•	Enums baked incorrectly (Postgres enum creation order issues)
	•	Alembic autogenerate but no constraints (common when relationships aren’t declared)
	•	ContextPacket/ConstraintSnapshot mutable by default with no convention/test enforcing new versions
	•	No indexes on FKs (makes runs/artifacts queries painful quickly)

⸻

6) Fast way to report “extent complete” (scorecard)

When you inspect Claude’s output, classify each item:
	•	✅ Present and correct
	•	🟡 Present but weak (works but will hurt soon)
	•	❌ Missing

Scorecard lines:
	•	Models exist for all 7 objects
	•	Join tables exist (issue↔context, run↔context, doctrine links)
	•	Migrations apply cleanly on fresh DB
	•	Downgrade sanity works
	•	CRUD tests cover linkage end-to-end
	•	AuditLog exists (bonus)

⸻
