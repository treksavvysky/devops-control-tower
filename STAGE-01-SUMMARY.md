# STAGE-01-SUMMARY — JCT Stage 1 (Task Contract + Intake Gate)

This document is the authoritative progress tracker for Stage 1 of the Jules Control Tower (JCT) inside the `devops-control-tower` repo. It exists to prevent drift between documentation, API contracts, and implementation as multiple agents contribute.

Stage 1 goal: define a stable V1 Task Spec and implement a governed intake endpoint that persists tasks without executing them.

---

## Status at a glance

- Stage 1.0 — V1 Task Spec contract: ✅ Completed
- Stage 1.1 — DB model + migration for tasks: ✅ Completed
- Stage 1.2 — Policy gate (governance + normalization): ✅ Completed (corrected to match canonical contract)
- Stage 1.3 — POST intake endpoint (enqueue): ✅ Completed
- Stage 1.4 — Idempotency behavior: ✅ Completed
- Stage 1.5 — GET task status retrieval: ✅ Completed
- Stage 1.6 — Tests (contract + policy + endpoints): ✅ Completed
- Stage 1.7 — Minimal operator + agent docs: ✅ Completed
- Stage 1.8 — Contract drift prevention: ✅ Completed

Legend: ✅ done, 🟡 in progress/partial, ⏳ planned

---

## Stage 1 sub-stages (planned scope)

### Stage 1.0 — Define the V1 Task Spec (canonical contract)
Deliverables:
- `docs/specs/task-spec-v1.md` defining the V1 contract and field semantics
- Example payload included in the spec
- Standalone example JSON at `docs/examples/task-create-v1.json`

Contract summary (V1):
- `version: "1.0"`
- `requested_by: { kind: human|agent|system, id: string, label?: string }`
- `objective: string`
- `operation: code_change | docs | analysis | ops`
- `target: { repo: string, ref: "main" (default), path: "" (default) }`
- `constraints: { time_budget_seconds: 900 (default), allow_network: false (default), allow_secrets: false (default) }`
- `inputs: {}` free-form
- `metadata: {}` free-form
- `idempotency_key?: string` optional

Completion notes:
- Canonical spec document fully aligned with implementation
- Example JSON file added for reference

### Stage 1.1 — Create DB schema + migration for tasks
Deliverables:
- `tasks` table (and optional related tables) with lifecycle-ready fields:
  - `id` (UUID, server-generated)
  - `status` (at minimum: queued)
  - `requested_by`, `objective`, `operation`, `target`, `constraints`, `inputs`, `metadata`, `idempotency_key`
  - timestamps (`created_at`, `updated_at`)
- Alembic migration checked in and runnable

Completion notes:
- Store the normalized form of the task (after policy evaluation) where applicable.

### Stage 1.2 — Policy gate (governance + normalization)
Deliverables:
- Pure policy module (no DB, no FastAPI request objects), e.g. `devops_control_tower/policy/task_gate.py`
- `evaluate(task: TaskCreateLegacyV1) -> TaskCreateLegacyV1` returns normalized task OR raises `PolicyError(code, message)`
- Enforced V1 rules (minimal):
  - `operation` must be in allowed set
  - `target.repo` must be in allowlist / namespace allowlist
  - `constraints.time_budget_seconds` in safe range (e.g., 30..86400)
  - `allow_network` default false; deny if true (V1)
  - `allow_secrets` default false; deny if true (V1)
- Normalization:
  - default `target.ref="main"` and `target.path=""` if absent
  - trim objective whitespace
  - canonicalize `target.repo` (e.g., strip trailing `.git`, lowercase)

Completion notes:
- Endpoint rejects disallowed tasks with a consistent JSON error body.
- Only normalized tasks are persisted.
- Policy gate corrected to match canonical V1 contract.

### Stage 1.3 — Intake endpoint: POST /tasks/enqueue
Deliverables:
- FastAPI route `POST /tasks/enqueue`
- Accepts `TaskCreateLegacyV1`
- Runs schema validation then policy evaluation
- Persists task with `status="queued"`
- Returns at minimum `{ task_id, status }`
- Does NOT execute anything (no worker/sandbox/Jules calls)

Completion notes:
- Endpoint is a courthouse, not a factory.

### Stage 1.4 — Idempotency (optional but recommended)
Deliverables:
- Support `idempotency_key` to prevent duplicates on client retry
- Uniqueness rules defined and enforced
- Repeated submission returns original task_id

### Stage 1.5 — Task retrieval endpoint: GET /tasks/{id}
Deliverables:
- Returns task record with status and stored fields
- In Stage 1, trace/artifact pointers may be null/absent

### Stage 1.6 — Tests (contract + policy + endpoints)
Deliverables:
- Unit tests for policy behavior
- API tests for enqueue accept/reject
- DB persistence tests (record created, defaults applied)
- Compatibility layer tests for legacy field aliases

### Stage 1.7 — Minimal docs for operators + agents
Deliverables:
- README section with copy/paste curl examples for enqueue + get
- Short notes for agents: required fields, default constraints, policy failure codes

### Stage 1.8 — Contract drift prevention
Deliverables:
- Contract governance rules in `CLAUDE.md`
- Contract snapshot test (`tests/test_contract_snapshot.py`) that fails if canonical fields are removed
- Read-only convention for `docs/specs/task-spec-v1.md`

---

## Completed work (claimed as complete)

### ✅ Stage 1.0 — Task Spec contract
Files:
- `docs/specs/task-spec-v1.md` — Canonical V1 contract documentation
- `docs/examples/task-create-v1.json` — Standalone example payload

Verification:
- The example payload validates against the Pydantic model used by the API.
- Spec document includes full field definitions, policy rules, and error codes.

### ✅ Stage 1.1 — DB schema + migration
Files:
- `devops_control_tower/db/models.py` (TaskModel)
- `devops_control_tower/db/migrations/versions/b2f6a732d137_create_task_table.py`

Verification:
- `alembic upgrade head` succeeds.
- Task inserts include required fields and timestamps.

### ✅ Stage 1.2 — Policy gate
Files:
- `devops_control_tower/policy/__init__.py`
- `devops_control_tower/policy/task_gate.py`
- `devops_control_tower/schemas/task_v1.py`

Implementation:
- `PolicyError(code, message)` exception for policy violations
- `evaluate(task, config=None)` function returns normalized task or raises `PolicyError`
- Policy rules enforced:
  - Operation must be one of: `code_change`, `docs`, `analysis`, `ops`
  - Repository must match allowed prefixes (default: `treksavvysky/`, `owner/`)
  - Time budget must be in range 30-86400 seconds
  - `allow_network=true` is DENIED in V1
  - `allow_secrets=true` is DENIED in V1
- Normalization applied:
  - Repository: lowercase, strip `.git` suffix
  - Objective: trim whitespace
  - Target ref defaults to `"main"`
  - Target path defaults to `""`

Policy error codes:
- `INVALID_OPERATION` - Operation not in allowed set
- `REPO_NOT_ALLOWED` - Repository not in allowed namespace
- `TIME_BUDGET_TOO_LOW` - Time budget below 30 seconds
- `TIME_BUDGET_TOO_HIGH` - Time budget above 86400 seconds
- `NETWORK_ACCESS_DENIED` - Network access requested in V1
- `SECRETS_ACCESS_DENIED` - Secrets access requested in V1

**Compatibility Layer (temporary, will be removed in V2):**
- `type` accepted as alias for `operation`
- `payload` accepted as alias for `inputs`
- `target.repository` accepted as alias for `target.repo`
- Canonical fields take precedence when both are provided
- Only canonical fields are persisted

Verification:
- 46 unit tests in `tests/test_policy.py`
- Policy violations return HTTP 422 with `{"error": "policy_violation", "code": "...", "message": "..."}`

### ✅ Stage 1.3 — POST /tasks/enqueue
Implementation:
- Endpoint runs Pydantic schema validation first
- Then calls `evaluate_policy()` to validate and normalize
- Policy failures return 422 with structured error body
- Only normalized tasks are persisted

Verification:
- `curl` enqueue returns 201 and task row exists in DB.
- Invalid tasks return appropriate error codes.

### ✅ Stage 1.4 — Idempotency
Implementation:
- `TaskService.create_task()` checks for existing task with same `idempotency_key`
- If found, returns existing task instead of creating duplicate
- Unique constraint on `idempotency_key` column in `TaskModel`
- Idempotency enforced at DB level via `UniqueConstraint("idempotency_key")`

Verification:
- 5 tests in `tests/test_api_tasks.py::TestIdempotency`:
  - `test_idempotency_key_returns_same_task_on_duplicate`: Repeated submission with same `idempotency_key` returns same `task_id`
  - `test_idempotency_key_creates_only_one_db_row`: Multiple submissions create only one DB row
  - `test_idempotency_works_with_legacy_input_normalized`: Idempotency works after normalization (legacy + canonical inputs)
  - `test_different_idempotency_keys_create_different_tasks`: Different `idempotency_key` values create different tasks
  - `test_no_idempotency_key_creates_new_task_each_time`: Requests without `idempotency_key` always create new tasks

**Evidence:** Idempotency verified: repeated enqueue with same key returns same task_id (`test_idempotency_key_returns_same_task_on_duplicate`).

### ✅ Stage 1.5 — GET /tasks/{id}
Implementation:
- `GET /tasks/{task_id}` returns full task record with all canonical V1 fields
- Returns nested structures: `requested_by`, `target`, `constraints`
- Returns timestamps: `created_at`, `queued_at`, `started_at`, `completed_at`
- Returns 404 for unknown task IDs or invalid UUID formats
- `GET /tasks` supports filtering by status, operation, requester_kind, target_repo

Verification:
- 5 tests in `tests/test_api_tasks.py::TestGetTaskById`:
  - `test_get_existing_task_returns_200`: Existing task returns 200 with correct data
  - `test_get_task_returns_canonical_fields`: Response includes all canonical V1 fields
  - `test_get_nonexistent_task_returns_404`: Unknown task ID returns 404 with "Task not found" message
  - `test_get_task_with_invalid_uuid_returns_404`: Invalid UUID format returns 404
  - `test_get_task_returns_timestamps`: Response includes timestamp fields

**Evidence:** GET verified: `/tasks/{id}` returns stored record (`test_get_existing_task_returns_200`); unknown id returns "Task not found" (`test_get_nonexistent_task_returns_404`).

### ✅ Stage 1.6 — Tests
Files:
- `tests/test_policy.py` - 53 unit tests for policy module + compatibility layer
- `tests/test_api_tasks.py` - 38 API-level integration tests (includes idempotency + retrieval tests)
- `tests/test_contract_snapshot.py` - 9 contract snapshot tests

Test coverage (100 tests total):
- Policy rule enforcement (operation, repo, time budget, network, secrets)
- Normalization (repo canonicalization, whitespace trimming)
- API rejection codes for policy violations
- Task creation and retrieval
- Default value application
- Compatibility layer (type→operation, payload→inputs, repository→repo)
- Idempotency behavior (5 tests in `TestIdempotency`)
- Task retrieval with 404 handling (5 tests in `TestGetTaskById`)
- Contract schema freeze (9 tests in `test_contract_snapshot.py`)

### ✅ Stage 1.7 — Documentation
Files:
- `docs/specs/task-spec-v1.md` - Complete V1 specification with examples
- `docs/examples/task-create-v1.json` - Standalone example payload
- `CLAUDE.md` - Agent guidance including V1 spec summary

### ✅ Stage 1.8 — Contract drift prevention
Files:
- `CLAUDE.md` - Contract governance section added
- `tests/test_contract_snapshot.py` - 9 tests that freeze the V1 contract schema

Implementation:
- **Source of Truth:** The Pydantic model `TaskCreateLegacyV1` in `schemas/task_v1.py` is the API contract. The code is the source of truth, not the markdown documentation. Changing the model shape is a breaking change.
- **Read-Only Spec Document:** `docs/specs/task-spec-v1.md` is read-only by convention. Do NOT modify unless explicitly asked.
- **Contract Snapshot Test:** `tests/test_contract_snapshot.py` asserts all canonical fields exist in the JSON schema. If CI turns red on this test, a breaking change was introduced.
- **Compatibility Layer:** Legacy field aliases (`type`, `payload`, `target.repository`) are accepted once and normalized to canonical fields. No further changes to the compatibility layer.

Verification:
- 9 contract snapshot tests in `tests/test_contract_snapshot.py`
- Tests assert: top-level fields, RequestedBy fields, Target fields, Constraints fields, operation enum values, requester kind enum values, version literal, default values

---

## Decisions (record here to prevent drift)

- Allowed V1 operations: `code_change | docs | analysis | ops`
- Default `target.ref`: `main`
- Default constraints: `time_budget_seconds=900`, `allow_network=false`, `allow_secrets=false`
- V1 stance on `allow_network=true`: **DENY** (returns `NETWORK_ACCESS_DENIED`)
- V1 stance on `allow_secrets=true`: **DENY** (returns `SECRETS_ACCESS_DENIED`)
- Default allowed repo prefixes: `treksavvysky/`, `owner/` (configurable via `PolicyConfig`)
- Repository normalization: lowercase + strip `.git` suffix

**Compatibility Layer Decisions:**
- Legacy field aliases are temporary and will be removed in V2
- Canonical fields always take precedence when both canonical and legacy are provided
- Only canonical fields are persisted to DB

**Contract Drift Prevention Decisions:**
- The Pydantic model `TaskCreateLegacyV1` is the source of truth, not the markdown documentation
- `docs/specs/task-spec-v1.md` is read-only by convention
- Contract snapshot tests in CI prevent accidental breaking changes
- Compatibility layer is frozen — no further field aliases will be added

---

## Notes for agents (Claude/Codex/Jules)

- Do not invent new Task Spec fields without updating the spec doc.
- Keep policy logic out of the endpoint handler; endpoints call the policy module.
- Stage 1 does not execute tasks. If you find worker/sandbox calls in enqueue, remove them.
- Policy configuration can be customized by passing a `PolicyConfig` object to `evaluate()`.
- All policy errors return HTTP 422 with a structured body containing `error`, `code`, and `message` fields.
- The compatibility layer accepts legacy field names but always normalizes to canonical V1 fields before persistence.
- **Do NOT modify `docs/specs/task-spec-v1.md` unless explicitly asked by the user.**
- **The Pydantic model is the contract. If `tests/test_contract_snapshot.py` fails, a breaking change was introduced.**
