Sprint-0 is your “vertical slice”: a single task can be accepted, persisted, pulled by a worker, and logged end-to-end. “With Trace IDs” means: the same identifier threads through every layer so you can answer, later, “what happened to task X?” without spelunking.

Objective

Deliver a minimal DevOps Control Tower (JCT) that can:
	•	accept a task spec (enqueue)
	•	write canonical DB rows (Task/Job/Artifact stubs)
	•	have a worker claim and process one task
	•	expose /healthz
	•	emit and propagate a trace_id across API → DB → worker → downstream action calls → artifact references

Core concept: Trace ID

A trace_id is a stable string (UUID is fine) created at the edge (API) and carried everywhere as:
	•	a response field to the caller
	•	a column in DB tables
	•	a log field in every log line
	•	an HTTP header in downstream calls (common: traceparent or a simple X-Trace-Id)
	•	a field attached to artifacts (rows in artifacts table, filenames, object metadata, etc.)

This gives you “single-thread causality” across your system.

⸻

Layers (Sprint-0 shape)

1) API layer (FastAPI)

Endpoints
	•	POST /enqueue
	•	input: task spec (minimal JSON)
	•	behavior:
	1.	generate trace_id
	2.	insert tasks row (status=queued)
	3.	insert jobs row (optional in Sprint-0, but nice)
	4.	return {task_id, trace_id}
	•	GET /healthz
	•	returns {"ok": true} (optionally checks DB connectivity)

Trace rules
	•	If caller supplies a trace header (X-Trace-Id), you may accept it; otherwise generate.
	•	Include trace_id in:
	•	response JSON
	•	logs
	•	DB rows

2) Data layer (Postgres)

Minimum schema to support traceability:
	•	tasks
	•	id (uuid/int)
	•	trace_id (uuid/text, indexed)
	•	spec (jsonb)
	•	status (queued|running|done|failed)
	•	timestamps
	•	jobs (optional but aligns with your future)
	•	id
	•	task_id (fk)
	•	trace_id (duplicated for easy querying)
	•	status
	•	timestamps
	•	artifacts (stub)
	•	id
	•	task_id
	•	trace_id
	•	kind (log, diff, report, file, etc.)
	•	uri or ref (string)
	•	timestamps

Why duplicate trace_id across tables?
Because it makes forensic queries trivial (and fast) without multi-table joins when you’re debugging at 2am.

3) Worker layer (Celery or simple loop)

Sprint-0 worker behavior:
	1.	claim one queued task (DB transaction / “SELECT … FOR UPDATE SKIP LOCKED” style)
	2.	mark as running
	3.	call a stub “SandboxSpawner” / “ActionRunner”
	4.	emit logs containing trace_id
	5.	write at least one artifacts row referencing something (even a log blob ref)
	6.	mark task done (or failed with error field)

Trace propagation
	•	When worker calls downstream “actions”, it must pass the same trace_id as:
	•	header: X-Trace-Id: <trace_id>
	•	and/or in payload: {..., "trace_id": "<trace_id>"}

4) “Downstream action call and artifact references”

In Sprint-0, “downstream” can be a stub function that pretends to call another service. The important part is the contract:
	•	Every action invocation record includes:
	•	trace_id
	•	action_name
	•	inputs_hash (later)
	•	started_at, completed_at
	•	result_artifact_id (later)
	•	Every artifact reference includes:
	•	trace_id
	•	task_id
	•	uri/ref that can be resolved later

Even if Sprint-0 only stores “artifact: worker_log_line_#123”, you’ve proven the wiring.

⸻

Acceptance criteria (Sprint-0 is “done” when)
	•	POST /enqueue returns a trace_id.
	•	DB contains a tasks row with that trace_id.
	•	Worker processes the task and logs multiple lines that include the same trace_id.
	•	Worker creates at least one artifacts row with the same trace_id.
	•	/healthz responds 200.
	•	You can grep logs by trace_id and reconstruct the timeline.

⸻

Implementation choices (keep it boring)
	•	trace_id: UUIDv4 string.
	•	Logging: structured JSON logs (even if hand-rolled) with fields {trace_id, task_id, event, ...}.
	•	Propagation: simplest is X-Trace-Id header everywhere. (Later you can add W3C traceparent.)

⸻

Why this matters (strategic leverage)

Sprint-0 without trace IDs gives you “it works” demos that collapse the first time something flakes. Sprint-0 with trace IDs gives you the beginnings of an audit trail, which is the difference between a toy orchestrator and an operations-grade control tower.

Next natural step after this: add /tasks/{id} to fetch status + artifacts by task_id or trace_id, and you’ve got your first real “control tower console” API.x
