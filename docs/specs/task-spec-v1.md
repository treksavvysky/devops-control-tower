# JCT Task Spec — V1 (Canonical)

This document defines the canonical V1 task contract for Jules Control Tower (JCT). If any other document or code disagrees, **this contract wins** for Stage 1.

## Purpose

A Task is a durable, governed unit of work. The enqueue endpoint accepts a task, validates it, applies policy, persists it, and returns a `task_id`. Stage 1 does **not** execute tasks.

---

## TaskCreateLegacyV1 (Request Body)

### JSON Shape

```json
{
  "version": "1.0",
  "idempotency_key": "optional-client-generated-string",

  "requested_by": {
    "kind": "human | agent | system",
    "id": "string",
    "label": "optional string"
  },

  "objective": "string",
  "operation": "code_change | docs | analysis | ops",

  "target": {
    "repo": "owner/name",
    "ref": "main",
    "path": ""
  },

  "constraints": {
    "time_budget_seconds": 900,
    "allow_network": false,
    "allow_secrets": false
  },

  "inputs": {},
  "metadata": {}
}
```

---

## Field Definitions

### Top-Level Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `version` | `"1.0"` | Yes | `"1.0"` | Spec version, must be `"1.0"` |
| `idempotency_key` | `string` | No | `null` | Client-generated key for deduplication (max 256 chars) |
| `requested_by` | `object` | Yes | — | Audit trail: who/what initiated the task |
| `objective` | `string` | Yes | — | Clear statement of success criteria (5-4000 chars) |
| `operation` | `string` | Yes | — | One of: `code_change`, `docs`, `analysis`, `ops` |
| `target` | `object` | Yes | — | Repository and location for the task |
| `constraints` | `object` | No | (see below) | Resource and security constraints |
| `inputs` | `object` | No | `{}` | Free-form input data for the task |
| `metadata` | `object` | No | `{}` | Free-form metadata (tags, labels, etc.) |

### `requested_by` Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | `string` | Yes | One of: `human`, `agent`, `system` |
| `id` | `string` | Yes | Unique identifier (1-128 chars) |
| `label` | `string` | No | Human-readable label (1-256 chars) |

### `target` Object

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo` | `string` | Yes | — | Repository in `owner/name` format (1-256 chars) |
| `ref` | `string` | No | `"main"` | Git ref (branch, tag, commit) (1-256 chars) |
| `path` | `string` | No | `""` | Path within repository (max 512 chars) |

### `constraints` Object

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `time_budget_seconds` | `integer` | No | `900` | Max execution time (30-86400 seconds) |
| `allow_network` | `boolean` | No | `false` | Request network access (DENIED in V1) |
| `allow_secrets` | `boolean` | No | `false` | Request secrets access (DENIED in V1) |

---

## Operations

The `operation` field must be one of:

| Operation | Description |
|-----------|-------------|
| `code_change` | Modify source code (add feature, fix bug, refactor) |
| `docs` | Documentation updates (README, comments, specs) |
| `analysis` | Read-only analysis (code review, security scan, metrics) |
| `ops` | Operations tasks (CI/CD config, infrastructure as code) |

---

## V1 Policy Rules

The policy gate enforces these rules before persistence:

1. **Operation validation**: Must be one of the allowed operations
2. **Repository allowlist**: `target.repo` must match allowed prefixes configured via `JCT_ALLOWED_REPO_PREFIXES` environment variable (comma-separated list, e.g., `myorg/,partnerorg/`). Empty or unset = deny all repositories.
3. **Time budget range**: Must be 30-86400 seconds
4. **Network access**: `allow_network=true` is **DENIED** in V1
5. **Secrets access**: `allow_secrets=true` is **DENIED** in V1

### Normalization

Before persistence, tasks are normalized:
- `target.repo`: Lowercased, trailing `.git` stripped
- `target.ref`: Defaults to `"main"` if empty
- `target.path`: Defaults to `""` if empty
- `objective`: Leading/trailing whitespace trimmed

---

## Policy Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_OPERATION` | 422 | Operation not in allowed set |
| `REPO_NOT_ALLOWED` | 422 | Repository not in allowed namespace |
| `TIME_BUDGET_TOO_LOW` | 422 | Time budget below 30 seconds |
| `TIME_BUDGET_TOO_HIGH` | 422 | Time budget above 86400 seconds |
| `NETWORK_ACCESS_DENIED` | 422 | Network access requested in V1 |
| `SECRETS_ACCESS_DENIED` | 422 | Secrets access requested in V1 |

Error response format:
```json
{
  "detail": {
    "error": "policy_violation",
    "code": "REPO_NOT_ALLOWED",
    "message": "Repository 'unauthorized/repo' is not in the allowed namespace."
  }
}
```

---

## Compatibility Layer (Temporary)

To support clients migrating from older schemas, these aliases are accepted but deprecated:

| Legacy Field | Canonical Field | Notes |
|--------------|-----------------|-------|
| `type` | `operation` | Alias for operation |
| `payload` | `inputs` | Alias for inputs |
| `target.repository` | `target.repo` | Alias for repo |

Only canonical fields are persisted. Legacy aliases will be removed in V2.

---

## Example Request

```bash
curl -X POST http://localhost:8000/tasks/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0",
    "requested_by": {
      "kind": "human",
      "id": "alice",
      "label": "Alice Developer"
    },
    "objective": "Add a /healthz endpoint that returns {\"status\":\"ok\"} and a pytest that verifies 200 + body.",
    "operation": "code_change",
    "target": {
      "repo": "myorg/example-service",
      "ref": "main"
    }
  }'
```

## Example Response

```json
{
  "status": "success",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Task enqueued successfully",
  "task": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "version": "1.0",
    "status": "queued",
    "requested_by": {
      "kind": "human",
      "id": "alice",
      "label": "Alice Developer"
    },
    "objective": "Add a /healthz endpoint that returns {\"status\":\"ok\"} and a pytest that verifies 200 + body.",
    "operation": "code_change",
    "target": {
      "repo": "myorg/example-service",
      "ref": "main",
      "path": ""
    },
    "constraints": {
      "time_budget_seconds": 900,
      "allow_network": false,
      "allow_secrets": false
    },
    "inputs": {},
    "metadata": {},
    "created_at": "2025-12-08T12:00:00Z"
  }
}
```

---

## Task Lifecycle

```
POST /tasks/enqueue
        │
        ▼
  Schema Validation (Pydantic)
        │
        ▼
  Policy Evaluation (task_gate.py)
        │
        ├─ Violation → HTTP 422 + error body
        │
        ▼
  Normalize + Persist (status="queued")
        │
        ▼
  Return task_id + status

  [Stage 2+: Worker picks up → Execute → Trace folder]
```
