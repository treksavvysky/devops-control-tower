Absolutely. Here’s an initial cwom_v0_1.md you can drop straight into your repo. It’s written as a spec: boring, strict, and implementation-friendly.

# Canonical Work Object Model (CWOM) — v0.1

**Status:** Draft (v0.1)  
**Purpose:** Define the minimal, stable schema for representing work as a system of interoperable objects.  
**Scope:** Repo, Issue, ContextPacket, Run, Artifact, ConstraintSnapshot, DoctrineRef.  
**Non-goals (v0.1):** UI, permissions/auth, event sourcing/log streams, scheduling, agent personas, secret storage.

---

## 0. Conceptual Spine

CWOM models work as explicit causality:

**Issue** + **ContextPacket** + **ConstraintSnapshot** + **DoctrineRef**  
→ (**Run**)  
→ produces (**Artifact**)

CWOM is intentionally small and rigid. Everything else plugs into it.

---

## 1. Guiding Principles

1. **Stable identity:** Every object has a globally unique, stable `id`.
2. **Explicit linkage:** Cross-object relationships are represented via `Ref`.
3. **Auditability:** A Run’s inputs and outputs must be explicit.
4. **Immutability where it matters:** ContextPacket and ConstraintSnapshot are immutable once created.
5. **Tool-agnostic:** Objects map cleanly to GitHub/CI/LLMs/humans.
6. **Boring enums:** Canonical statuses and types are intentionally small; adapters map richer states into them.

---

## 2. Common Primitives

### 2.1 ObjectKind
All objects include:
- `kind`: string constant identifying the object type (e.g., `"Issue"`).

Valid kinds (v0.1):
- `Repo`
- `Issue`
- `ContextPacket`
- `Run`
- `Artifact`
- `ConstraintSnapshot`
- `DoctrineRef`

### 2.2 ID
All objects include:
- `id`: string

**Recommended format:** ULID (lexicographically sortable, globally unique).  
**Constraint:** Must be unique across all CWOM objects within a deployment.

### 2.3 Timestamp
Objects SHOULD include:
- `created_at`: ISO-8601 UTC string
- `updated_at`: ISO-8601 UTC string

### 2.4 Actor
Represents who/what created or executed something.

```json
{
  "actor_kind": "human|agent|system",
  "actor_id": "string",
  "display": "string"
}

2.5 Source

Represents linkage to external systems (GitHub, Linear, etc.).

{
  "system": "string",
  "external_id": "string|null",
  "url": "string|null"
}

2.6 Ref

Universal reference to another CWOM object.

{
  "kind": "Repo|Issue|ContextPacket|Run|Artifact|ConstraintSnapshot|DoctrineRef",
  "id": "string",
  "role": "string|null"
}

Rules:
	•	kind + id must resolve to exactly one object.
	•	role is optional semantic labeling (e.g., "primary_context", "governing_doctrine").

2.7 Tags and Meta

All objects MAY include:
	•	tags: string[]
	•	meta: object (freeform, namespaced keys recommended)

⸻

3. Canonical Enums

3.1 Status

Canonical status shared across objects where applicable:
	•	planned
	•	ready
	•	running
	•	blocked
	•	done
	•	failed
	•	canceled

Adapters MUST map tool-specific statuses into this set.

3.2 IssueType
	•	feature
	•	bug
	•	chore
	•	research
	•	ops
	•	doc
	•	incident

3.3 Priority
	•	P0
	•	P1
	•	P2
	•	P3
	•	P4

3.4 RunMode
	•	human
	•	agent
	•	hybrid
	•	system

3.5 ArtifactType
	•	code_patch
	•	commit
	•	pr
	•	build
	•	container_image
	•	doc
	•	report
	•	dataset
	•	log
	•	trace
	•	binary
	•	link

3.6 VerificationStatus
	•	unverified
	•	passed
	•	failed

3.7 DoctrineType
	•	principle
	•	policy
	•	procedure
	•	heuristic
	•	pattern

3.8 DoctrinePriority
	•	must
	•	should
	•	may

3.9 Visibility (Repo)
	•	public
	•	private
	•	internal

⸻

4. Object Schemas

Note: Schemas are defined structurally here. JSON Schema / Pydantic definitions may be derived from this document.

4.1 Repo

Represents a work container (codebase/project/docs boundary).

Fields:
	•	kind: "Repo"
	•	id: string
	•	name: string
	•	slug: string (stable identifier)
	•	source: Source
	•	default_branch: string
	•	visibility: public|private|internal
	•	owners: Ref[] (Refs to actors are stored as meta or separate system; v0.1 uses Actor[] if needed)
	•	policy:
	•	allowed_tools: string[]
	•	secrets_profile: string|null
	•	links: string[]
	•	tags: string[]
	•	meta: object
	•	created_at, updated_at

Invariants:
	•	slug MUST remain stable even if name changes.

⸻

4.2 Issue

Represents a unit of intent: a problem to solve or outcome to produce.

Fields:
	•	kind: "Issue"
	•	id: string
	•	repo: Ref (Repo)
	•	title: string
	•	description: string
	•	type: IssueType
	•	priority: Priority
	•	status: Status
	•	assignees: Actor[]
	•	watchers: Actor[]
	•	doctrine_refs: Ref[] (DoctrineRef)
	•	constraints: Ref[] (ConstraintSnapshot) — typically “current”
	•	context_packets: Ref[] (ContextPacket)
	•	acceptance:
	•	criteria: string[]
	•	tests_expected: string[]|null
	•	relationships:
	•	parent: Ref|null (Issue)
	•	blocks: Ref[] (Issue)
	•	blocked_by: Ref[] (Issue)
	•	duplicates: Ref[] (Issue)
	•	runs: Ref[] (Run)
	•	tags, meta, created_at, updated_at

Invariants:
	•	Issue is intent, not execution.
	•	Runs SHOULD link back to Issue; Issue MAY store Run refs for convenience.

⸻

4.3 ContextPacket

Represents a versioned briefing bundle for a Run.

Fields:
	•	kind: "ContextPacket"
	•	id: string
	•	for_issue: Ref (Issue)
	•	version: string
	•	summary: string
	•	inputs:
	•	documents: object[] where each document is:
	•	title: string
	•	uri: string
	•	digest: string|null (sha256 recommended)
	•	excerpt: string|null
	•	data_blobs: object[] where each blob is:
	•	name: string
	•	media_type: string
	•	uri: string|null
	•	inline: string|null (base64 or raw small text)
	•	digest: string|null
	•	links: string[]
	•	assumptions: string[]
	•	open_questions: string[]
	•	instructions: string
	•	doctrine_refs: Ref[] (DoctrineRef)
	•	constraint_snapshot: Ref|null (ConstraintSnapshot) pinned at packet creation
	•	tags, meta, created_at, updated_at

Invariants:
	•	ContextPacket is immutable once created. New info ⇒ new ContextPacket with a new version.
	•	Exactly one of uri or inline SHOULD be set for each data blob (both allowed only for convenience; keep small).

⸻

4.4 ConstraintSnapshot

Represents point-in-time operational constraints.

Fields:
	•	kind: "ConstraintSnapshot"
	•	id: string
	•	scope: personal|repo|org|system|run
	•	captured_at: ISO-8601 UTC string
	•	owner: Actor
	•	constraints:
	•	time: { "available_minutes": number|null, "deadline": string|null }
	•	energy: { "score_0_5": number|null, "notes": string|null }
	•	health: { "flags": string[], "notes": string|null }
	•	budget: { "usd_available": number|null, "burn_limit_usd": number|null }
	•	tools: { "allowed": string[], "blocked": string[] }
	•	environment: { "location": string|null, "connectivity": "offline|limited|ok", "device": string|null }
	•	risk: { "tolerance": "low|medium|high", "notes": string|null }
	•	tags, meta

Invariants:
	•	ConstraintSnapshot is immutable.

⸻

4.5 DoctrineRef

Represents governing doctrine: principles, policies, procedures, heuristics, patterns.

Fields:
	•	kind: "DoctrineRef"
	•	id: string
	•	namespace: string
	•	name: string
	•	version: string
	•	type: DoctrineType
	•	priority: must|should|may
	•	statement: string
	•	rationale: string|null
	•	links: string[]
	•	applicability:
	•	repo_refs: Ref[] (Repo)
	•	issue_types: string[]
	•	tags: string[]
	•	tags, meta, created_at, updated_at

Invariants:
	•	DoctrineRef SHOULD be versioned; consumers MUST reference a specific version when reproducibility matters.

⸻

4.6 Run

Represents one execution attempt against an Issue.

Fields:
	•	kind: "Run"
	•	id: string
	•	for_issue: Ref (Issue)
	•	repo: Ref (Repo)
	•	status: Status
	•	mode: RunMode
	•	executor:
	•	actor: Actor
	•	runtime: string (e.g., "local", "ci", "container", "vps")
	•	toolchain: string[]
	•	inputs:
	•	context_packets: Ref[] (ContextPacket)
	•	doctrine_refs: Ref[] (DoctrineRef)
	•	constraint_snapshot: Ref|null (ConstraintSnapshot) pinned at run start
	•	plan:
	•	steps: string[]
	•	risk_notes: string[]
	•	telemetry:
	•	started_at: string|null
	•	ended_at: string|null
	•	duration_s: number|null
	•	cost:
	•	usd: number|null
	•	tokens: number|null
	•	compute_s: number|null
	•	outputs:
	•	artifacts: Ref[] (Artifact)
	•	result_summary: string
	•	decision_log: string[]
	•	failure:
	•	category: policy|build|test|runtime|dependency|unknown
	•	message: string
	•	tags, meta, created_at, updated_at

Invariants:
	•	A Run MUST reference an Issue and Repo.
	•	A Run SHOULD reference at least one ContextPacket once it transitions to running.
	•	A Run SHOULD pin a ConstraintSnapshot at start for auditability.
	•	Run inputs/outputs SHOULD be treated as append-only; supersede by creating a new Run.

⸻

4.7 Artifact

Represents an output produced by a Run.

Fields:
	•	kind: "Artifact"
	•	id: string
	•	produced_by: Ref (Run)
	•	for_issue: Ref (Issue)
	•	type: ArtifactType
	•	title: string
	•	uri: string
	•	digest: string|null (sha256, git hash, etc.)
	•	media_type: string|null
	•	size_bytes: number|null
	•	preview: string|null
	•	verification:
	•	status: VerificationStatus
	•	checks: object[] where each check is:
	•	name: string
	•	status: passed|failed|unverified
	•	evidence_uri: string|null
	•	tags, meta, created_at, updated_at

Invariants:
	•	Artifact MUST reference the Run that produced it.
	•	Artifact SHOULD be retrievable by uri and/or verifiable by digest.

⸻

5. Relationship Rules (Canonical Wiring)
	•	Repo contains Issues.
	•	Issue collects ContextPackets, DoctrineRefs, ConstraintSnapshots.
	•	ContextPacket MAY pin a ConstraintSnapshot and DoctrineRefs.
	•	Run consumes ContextPackets, DoctrineRefs, and pins a ConstraintSnapshot.
	•	Run produces Artifacts.
	•	Artifact belongs to Run and Issue.

⸻

6. Storage Notes (Non-binding for v0.1)

Recommended relational storage:
	•	Tables for each object kind.
	•	Join tables for many-to-many refs (e.g., Issue↔ContextPacket, Run↔ContextPacket).
	•	meta stored as JSONB.

Do not store primary relationships solely as JSON arrays if you expect to query them.

⸻

7. Adapter Notes (Non-binding for v0.1)

Example mappings:
	•	GitHub repository → Repo
	•	GitHub issue → Issue
	•	GitHub PR/commit → Artifact
	•	CI job / agent execution → Run
	•	Briefing doc / conversation summary → ContextPacket
	•	Current body-state / operational limits → ConstraintSnapshot
	•	ACE/Org policies → DoctrineRef

⸻

8. Versioning Policy
	•	This document is the source of truth for v0.1.
	•	Backward-incompatible changes require v0.2+.
	•	Additive changes (new optional fields, new Artifact types) may be minor revisions within v0.1 if they do not break existing consumers.

⸻

9. Open Questions (v0.1)
	•	Should Actor be a first-class CWOM object kind in v0.2?
	•	Should event sourcing (timeline log) be introduced as Event in v0.2?
	•	Should we formalize “sealed” state for ContextPacket rather than immutability-by-convention?

⸻

10. Examples (Minimal)

Example: Run producing a PR artifact
	•	Issue: “Add /healthz”
	•	ContextPacket: “service constraints + desired behavior”
	•	ConstraintSnapshot: “time budget low, risk tolerance medium”
	•	Run: “agent executes changes”
	•	Artifact: “GitHub PR link”

This chain is the unit of audit and learning.

If you want this spec to be **even more enforceable**, the next move is: derive **Pydantic models as the canonical source**, and auto-export JSON Schema from them, so docs and validation can’t drift.
