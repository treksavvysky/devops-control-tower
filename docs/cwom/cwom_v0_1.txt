Below is a v0.1 Canonical Work Object Model (CWOM): deliberately boring, rigid, and composable. It’s designed to be the “lowest common denominator” substrate that tools, agents, and human workflows can all agree on.

Core idea: everything is work flowing through time. Repos contain Issues. Issues ingest Context Packets. Runs execute against Issues (using Context + Doctrine + Constraints). Runs emit Artifacts. Constraint Snapshots capture operating conditions. Doctrine Refs anchor “why/how we decide.”

⸻

Design objectives
	•	Stable identifiers: every object is addressable, linkable, dedupable.
	•	Event-friendly: append-only history via events[] or external event log; the objects can be “current state.”
	•	Tool-agnostic: works for humans, LLM agents, CI/CD, schedulers.
	•	Composable: everything references everything else by ID; no deep nesting required.
	•	Auditable: “what ran, with what inputs, under what constraints, producing what outputs.”

⸻

Common primitives (used by all objects)

ID
	•	id: ULID preferred (sortable, unique). Format: ulid (string).

Reference

A universal link to another object.
	•	ref: { "kind": "<ObjectKind>", "id": "<ulid>", "role": "<optional semantic label>" }

Timestamp
	•	created_at, updated_at: ISO-8601 UTC strings.

Ownership & provenance
	•	created_by: { "actor_kind": "human|agent|system", "actor_id": "string", "display": "string" }
	•	source: { "system": "github|linear|local|...", "external_id": "string|null", "url": "string|null" }

Tags & metadata
	•	tags: string[]
	•	meta: freeform key/value map (namespaced keys recommended: github.*, jct.*, ace.*).

Status (canonical)

Use a small, boring enum; everything else maps into it.
	•	status: planned | ready | running | blocked | done | failed | canceled

Confidence (optional, but useful with LLMs)
	•	confidence: float 0–1 with confidence_note.

⸻

Object 1: Repo

A workspace boundary (codebase, knowledge base, or “project container”).

Schema
	•	kind: "Repo"
	•	id
	•	name: string (human-friendly)
	•	slug: string (stable)
	•	source (e.g., GitHub URL + repo id)
	•	default_branch: string
	•	visibility: public|private|internal
	•	owners: array of actor refs
	•	policy:
	•	allowed_tools: string[] (e.g., ["git", "docker", "python"])
	•	secrets_profile: string (pointer to secret vault policy)
	•	links: string[] (docs, dashboards)
	•	meta, tags, timestamps

Invariants
	•	slug is stable even if name changes.
	•	A Repo can be “code” or “non-code”; it’s still a work container.

⸻

Object 2: Issue

A unit of intent: problem, task, feature, bug, experiment. It’s the anchor for Runs.

Schema
	•	kind: "Issue"
	•	id
	•	repo: ref to Repo
	•	title: string
	•	description: string (markdown allowed)
	•	type: feature|bug|chore|research|ops|doc|incident
	•	priority: P0|P1|P2|P3|P4
	•	status
	•	assignees: actor refs
	•	watchers: actor refs
	•	doctrine_refs: ref[] (DoctrineRef)
	•	constraints: ref[] (ConstraintSnapshot) — usually “current”
	•	context_packets: ref[] (ContextPacket) — the “briefing bundle(s)”
	•	acceptance:
	•	criteria: string[]
	•	tests_expected: string[] (optional)
	•	relationships:
	•	parent: ref|null (Issue)
	•	blocks: ref[] (Issue)
	•	blocked_by: ref[] (Issue)
	•	duplicates: ref[] (Issue)
	•	runs: ref[] (Run) — historical linkage
	•	meta, tags, timestamps

Invariants
	•	Issues are not execution. They are intent.
	•	context_packets can be appended as new info arrives.

⸻

Object 3: Context Packet

A versioned input bundle: everything a Run should “know” at start. Think “briefing + attachments + assumptions.”

Schema
	•	kind: "ContextPacket"
	•	id
	•	for_issue: ref (Issue)
	•	version: string (e.g., "1.0", "2026-01-25a")
	•	summary: string (one paragraph)
	•	inputs:
	•	documents: array of { title, uri, digest, excerpt|null }
	•	data_blobs: array of { name, media_type, uri|inline, digest }
	•	links: string[]
	•	assumptions: string[]
	•	open_questions: string[]
	•	instructions: string (operator notes; “do this, avoid that”)
	•	doctrine_refs: ref[] (DoctrineRef)
	•	constraint_snapshot: ref|null (ConstraintSnapshot) — pinned at packet creation
	•	meta, tags, timestamps

Invariants
	•	ContextPacket is immutable once “sealed” (recommended). New info → new version.

⸻

Object 4: Run

A single execution attempt against an Issue: human session, agent session, CI job, codex run—doesn’t matter.

Schema
	•	kind: "Run"
	•	id
	•	for_issue: ref (Issue)
	•	repo: ref (Repo) (redundant but handy for indexing)
	•	status: planned|ready|running|done|failed|canceled
	•	mode: human|agent|hybrid|system
	•	executor: { actor_ref, runtime: "local|ci|container|vps|...", toolchain: string[] }
	•	inputs:
	•	context_packets: ref[] (ContextPacket) (usually 1 “primary”)
	•	doctrine_refs: ref[]
	•	constraint_snapshot: ref|null (pinned at run start)
	•	plan:
	•	steps: string[] (high level)
	•	risk_notes: string[]
	•	telemetry:
	•	started_at, ended_at
	•	duration_s
	•	cost: { "usd": number|null, "tokens": number|null, "compute_s": number|null }
	•	outputs:
	•	artifacts: ref[] (Artifact)
	•	result_summary: string
	•	decision_log: string[] (important choices)
	•	failure (optional):
	•	category: policy|build|test|runtime|dependency|unknown
	•	message: string
	•	meta, tags, timestamps

Invariants
	•	A Run must be reproducible in principle: inputs are explicit.
	•	Runs are append-only in spirit: don’t rewrite history; supersede with a new Run.

⸻

Object 5: Artifact

A produced output: file, patch, build, model, report, dataset, screenshot, deployment URL.

Schema
	•	kind: "Artifact"
	•	id
	•	produced_by: ref (Run)
	•	for_issue: ref (Issue)
	•	type:
code_patch|commit|pr|build|container_image|doc|report|dataset|log|trace|binary|link
	•	title: string
	•	uri: string (file path, S3, GitHub PR, etc.)
	•	digest: string (sha256 or git hash; optional but recommended)
	•	media_type: string (MIME)
	•	size_bytes: number|null
	•	preview: string|null (short excerpt/abstract)
	•	verification:
	•	status: unverified|passed|failed
	•	checks: array of { name, status, evidence_uri|null }
	•	meta, tags, timestamps

Invariants
	•	Artifact should be independently retrievable by uri and/or digest.

⸻

Object 6: Constraint Snapshot

A point-in-time operating envelope: what was true about limits, health, time, money, policies when decisions were made.

Schema
	•	kind: "ConstraintSnapshot"
	•	id
	•	scope: personal|repo|org|system|run
	•	captured_at: ISO timestamp
	•	owner: actor ref (who these constraints apply to)
	•	constraints:
	•	time: { available_minutes: number|null, deadline: string|null }
	•	energy: { score_0_5: number|null, notes: string|null }
	•	health: { flags: string[], notes: string|null }
	•	budget: { usd_available: number|null, burn_limit_usd: number|null }
	•	tools: { allowed: string[], blocked: string[] }
	•	environment: { location: string|null, connectivity: "offline|limited|ok", device: string|null }
	•	risk: { tolerance: "low|medium|high", notes: string|null }
	•	meta, tags

Invariants
	•	Snapshots are immutable. New reality → new snapshot.
	•	Runs should pin one at start for auditability.

⸻

Object 7: Doctrine Ref

A governing principle / policy / method reference: “how we decide,” “how we work,” “what’s forbidden.”

Schema
	•	kind: "DoctrineRef"
	•	id
	•	namespace: string (e.g., "ace", "jct", "security", "personal")
	•	name: string
	•	version: string
	•	type: principle|policy|procedure|heuristic|pattern
	•	statement: string (the actual doctrine text, concise)
	•	rationale: string|null
	•	links: string[] (long-form docs)
	•	priority: must|should|may
	•	applicability: { repo_refs: ref[], issue_types: string[], tags: string[] }
	•	meta, tags, timestamps

Invariants
	•	Doctrine is referenced, not copy-pasted, so it can evolve versioned.

⸻

Canonical relationships (the “wiring diagram”)
	•	Repo contains Issues.
	•	Issue collects ContextPackets + DoctrineRefs + ConstraintSnapshots; Issue spawns Runs.
	•	ContextPacket pins (optional) a ConstraintSnapshot and DoctrineRefs.
	•	Run consumes ContextPackets + DoctrineRefs + a ConstraintSnapshot; Run produces Artifacts.
	•	Artifact belongs to Run and Issue.
	•	DoctrineRef governs Issue/Run/Context by reference.
	•	ConstraintSnapshot frames Context and Run decisions.

⸻

Minimal JSON skeletons (v0.1)

No code generation theatrics, just the shape.

{
  "kind": "Issue",
  "id": "01HZY…",
  "repo": { "kind": "Repo", "id": "01HZX…" },
  "title": "Add /healthz endpoint",
  "description": "Expose uptime check for badge + deploy monitoring.",
  "type": "feature",
  "priority": "P2",
  "status": "ready",
  "doctrine_refs": [{ "kind": "DoctrineRef", "id": "01HZD…" }],
  "context_packets": [{ "kind": "ContextPacket", "id": "01HZC…" }],
  "constraints": [{ "kind": "ConstraintSnapshot", "id": "01HZK…" }],
  "runs": [],
  "meta": {},
  "tags": ["jct", "ops"],
  "created_at": "2026-01-25T20:00:00Z",
  "updated_at": "2026-01-25T20:00:00Z"
}


⸻

v0.1 “Lock points” (what we do NOT allow yet)
	•	No polymorphic status taxonomies per tool. Everything maps into the canonical status.
	•	No deep nesting of objects (keeps diffs small; enables event sourcing).
	•	No implicit inputs. If a Run used it, it’s referenced.
	•	No mutable ContextPackets or ConstraintSnapshots after sealing.

⸻

What plugs in later (but not in v0.1)
	•	Event log / timeline objects (audit stream)
	•	Agent persona / model config objects
	•	Secrets / credential objects (must be externalized)
	•	Schedules / triggers
	•	Metrics dashboards

⸻

If you adopt this as the substrate, you can now build “everything else” as adapters:
	•	GitHub Issue ⇄ CWOM Issue
	•	PR/Commit ⇄ Artifact
	•	CI job ⇄ Run
	•	“General’s Tent briefing” ⇄ ContextPacket
	•	“Current body-state” ⇄ ConstraintSnapshot
	•	ACE doctrine registry ⇄ DoctrineRef

Next natural step is a canonical JSON Schema for each object plus a reference resolver (by kind+id) so any agent can hydrate a working set deterministically.
