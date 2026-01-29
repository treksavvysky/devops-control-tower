# CWOM v0.1 Implementation Plan

**Status:** Phase 4 Complete
**Created:** 2025-01-25
**Updated:** 2025-01-26
**Spec:** `docs/cwom/cwom-spec-v0.1.md`

---

## Overview

This document outlines the phased implementation of the Canonical Work Object Model (CWOM) v0.1 into DevOps Control Tower. CWOM provides the "wiring standard" that makes features, agents, and automation composable.

### Core Causality Chain
```
Issue + ContextPacket + ConstraintSnapshot + DoctrineRef → Run → Artifact
```

### CWOM Object Types (v0.1)
| Object | Purpose |
|--------|---------|
| **Repo** | Work container (codebase, docs base, project boundary) |
| **Issue** | Unit of intent (what we want) |
| **ContextPacket** | Versioned briefing (what we know + assumptions + instructions) |
| **ConstraintSnapshot** | Operating envelope at a moment (time, money, health, policies) |
| **DoctrineRef** | Governing rules for "how we decide / how we work" |
| **Run** | Execution attempt (agent/human/CI doing work) |
| **Artifact** | Output of a Run (PR, commit, report, build) with verification |

---

## Phase 1: Foundation (Schemas + Structure)

**Goal:** Establish Pydantic schemas as the source of truth, create directory structure, move spec to proper location.

### Deliverables
- [x] Create `docs/cwom/` directory
- [x] Move spec from `cwom/cwom_v0_1.md` to `docs/cwom/cwom-spec-v0.1.md`
- [x] Create `devops_control_tower/cwom/` package
- [x] Create Pydantic schemas for all 7 CWOM object types:
  - `devops_control_tower/cwom/__init__.py`
  - `devops_control_tower/cwom/primitives.py` (Actor, Source, Ref, common enums)
  - `devops_control_tower/cwom/enums.py` (Status, IssueType, Priority, RunMode, etc.)
  - `devops_control_tower/cwom/repo.py`
  - `devops_control_tower/cwom/issue.py`
  - `devops_control_tower/cwom/context_packet.py`
  - `devops_control_tower/cwom/constraint_snapshot.py`
  - `devops_control_tower/cwom/doctrine_ref.py`
  - `devops_control_tower/cwom/run.py`
  - `devops_control_tower/cwom/artifact.py`
- [x] Add contract snapshot tests for CWOM schemas (45 tests in `tests/test_cwom_contract.py`)
- [x] Update CLAUDE.md with CWOM documentation

### Design Decisions
1. **ID Format:** ULID (lexicographically sortable, globally unique) - use `python-ulid` package
2. **Timestamps:** ISO-8601 UTC strings
3. **Immutability:** ContextPacket and ConstraintSnapshot are immutable (new version = new object)
4. **Validation:** Pydantic `model_validator` for cross-field rules

---

## Phase 2: Database Models + Migrations

**Goal:** Create SQLAlchemy models and Alembic migrations for CWOM objects.

### Deliverables
- [x] Create `devops_control_tower/db/cwom_models.py` with:
  - `CWOMRepoModel`
  - `CWOMIssueModel`
  - `CWOMContextPacketModel`
  - `CWOMConstraintSnapshotModel`
  - `CWOMDoctrineRefModel`
  - `CWOMRunModel`
  - `CWOMArtifactModel`
- [x] Create join tables for many-to-many relationships:
  - `cwom_issue_context_packets`
  - `cwom_issue_doctrine_refs`
  - `cwom_issue_constraint_snapshots`
  - `cwom_run_context_packets`
  - `cwom_run_doctrine_refs`
  - `cwom_context_packet_doctrine_refs`
- [x] Generate Alembic migration (`c3e8f9a21b4d_create_cwom_tables.py`)
- [x] Add indexes for common query patterns
- [x] Add database model tests (`tests/test_cwom_db_models.py`)

### Storage Notes (from spec)
- Tables for each object kind (prefixed with `cwom_`)
- Join tables for many-to-many refs (prefixed with `cwom_`)
- `meta` stored as JSON
- Primary relationships stored via foreign keys, not JSON arrays
- All models include `to_dict()` method for Pydantic schema compatibility

---

## Phase 3: Services + API Endpoints

**Goal:** Create service layer and REST endpoints for CWOM CRUD operations.

### Deliverables
- [x] Create `devops_control_tower/cwom/services.py`:
  - `RepoService`
  - `IssueService`
  - `ContextPacketService`
  - `ConstraintSnapshotService`
  - `DoctrineRefService`
  - `RunService`
  - `ArtifactService`
- [x] Create API router `devops_control_tower/cwom/routes.py`:
  - `POST /cwom/repos` - Create repo
  - `GET /cwom/repos/{id}` - Get repo
  - `GET /cwom/repos` - List repos
  - `POST /cwom/issues` - Create issue
  - `GET /cwom/issues/{id}` - Get issue with related objects
  - `GET /cwom/issues` - List issues
  - `PATCH /cwom/issues/{id}/status` - Update issue status
  - `POST /cwom/context-packets` - Create context packet
  - `GET /cwom/context-packets/{id}` - Get context packet
  - `GET /cwom/issues/{id}/context-packets` - List context packets for issue
  - `POST /cwom/constraint-snapshots` - Create constraint snapshot
  - `GET /cwom/constraint-snapshots/{id}` - Get constraint snapshot
  - `GET /cwom/constraint-snapshots` - List constraint snapshots
  - `POST /cwom/doctrine-refs` - Create doctrine ref
  - `GET /cwom/doctrine-refs/{id}` - Get doctrine ref
  - `GET /cwom/doctrine-refs` - List doctrine refs
  - `POST /cwom/runs` - Create run
  - `GET /cwom/runs/{id}` - Get run
  - `GET /cwom/runs` - List runs
  - `PATCH /cwom/runs/{id}` - Update run status/outputs
  - `POST /cwom/artifacts` - Create artifact
  - `GET /cwom/artifacts/{id}` - Get artifact
  - `GET /cwom/runs/{id}/artifacts` - List artifacts for run
  - `GET /cwom/issues/{id}/artifacts` - List artifacts for issue
- [x] Add validation for immutability constraints (405 Method Not Allowed for PUT/PATCH on ContextPacket and ConstraintSnapshot)
- [x] Add tests for all endpoints (`tests/test_cwom_api.py` - 21 tests)
- [x] Integrated CWOM router into main FastAPI app (`api.py`)

---

## Phase 4: Integration with Existing Task System

**Goal:** Bridge the existing JCT V1 Task system with CWOM.

### Mapping Strategy
| JCT V1 Task | CWOM Equivalent |
|-------------|-----------------|
| `Task.objective` | `Issue.description` + `Issue.acceptance.criteria` |
| `Task.operation` | `Issue.type` (mapped: code_change→feature, docs→doc, analysis→research, ops→ops) |
| `Task.target` | `Repo` + `Issue.repo` ref |
| `Task.constraints` | `ConstraintSnapshot` |
| `Task.inputs` | `ContextPacket.inputs` |
| `Task.requested_by` | `Actor` on Issue/Run |
| Task execution | `Run` |
| Task result/output | `Artifact` |

### Deliverables
- [x] Create adapter layer `devops_control_tower/cwom/task_adapter.py`:
  - `task_to_cwom()` - Convert TaskCreateV1 to Repo + Issue + ContextPacket + ConstraintSnapshot
  - `issue_to_task()` - Convert Issue back to Task format (for API compatibility)
- [x] Modify `/tasks/enqueue` to optionally create CWOM objects via `?create_cwom=true` query parameter
- [x] Add `cwom_issue_id` column to TaskModel
- [x] Create migration for TaskModel update (`d4a9b8c2e5f6_add_cwom_issue_id_to_tasks.py`)
- [x] Ensure backward compatibility (existing Task API unchanged - CWOM creation is opt-in)
- [x] Add integration tests (`tests/test_task_cwom_integration.py`)

---

## Phase 5: Worker Integration (Future)

**Goal:** Connect CWOM Run/Artifact to worker execution (Stage 2 of main project).

### Deliverables (Future)
- [ ] Worker creates Run when picking up Issue
- [ ] Worker pins ContextPacket and ConstraintSnapshot at Run start
- [ ] Worker creates Artifacts for outputs
- [ ] Trace folder maps to Artifact with type=`trace`

---

## Dependencies

### New Package Dependencies
```toml
# Add to pyproject.toml
python-ulid = "^2.0"  # For ULID generation
```

### Existing Infrastructure Used
- SQLAlchemy 2.0 (models)
- Alembic (migrations)
- Pydantic 2.x (schemas)
- FastAPI (API routes)

---

## Testing Strategy

1. **Unit Tests:** Pydantic schema validation, enum mappings
2. **Integration Tests:** Database CRUD operations, service layer
3. **Contract Tests:** JSON schema snapshots to detect breaking changes
4. **API Tests:** Endpoint behavior, error responses

---

## Success Criteria

### Phase 1 ✅
- [x] All 7 CWOM Pydantic schemas pass validation tests
- [x] Schemas export valid JSON Schema
- [x] Contract snapshot test exists and passes
- [x] `docs/cwom/cwom-spec-v0.1.md` is the canonical spec location
- [x] CLAUDE.md updated with CWOM section

### Phase 2 ✅
- [x] SQLAlchemy models created for all 7 object types
- [x] Join tables created for many-to-many relationships
- [x] Alembic migration successfully creates all tables
- [x] Database model tests pass

### Phase 3 ✅
- [x] Service layer provides CRUD for all object types
- [x] API endpoints accessible under `/cwom` prefix
- [x] Immutability enforced for ContextPacket and ConstraintSnapshot
- [x] API tests pass

### Phase 4 ✅
- [x] Task adapter provides bidirectional conversion
- [x] `/tasks/enqueue?create_cwom=true` creates CWOM objects
- [x] Task records linked to CWOM Issues via `cwom_issue_id`
- [x] Backward compatibility maintained (opt-in CWOM creation)
- [x] Integration tests pass
