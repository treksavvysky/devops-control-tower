# CWOM v0.1 Implementation Plan

**Status:** Phase 1 Complete
**Created:** 2025-01-25
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
- [ ] Create `devops_control_tower/db/cwom_models.py` with:
  - `RepoModel`
  - `IssueModel`
  - `ContextPacketModel`
  - `ConstraintSnapshotModel`
  - `DoctrineRefModel`
  - `RunModel`
  - `ArtifactModel`
- [ ] Create join tables for many-to-many relationships:
  - `issue_context_packets`
  - `issue_doctrine_refs`
  - `run_context_packets`
  - `run_artifacts`
- [ ] Generate Alembic migration
- [ ] Add indexes for common query patterns

### Storage Notes (from spec)
- Tables for each object kind
- Join tables for many-to-many refs
- `meta` stored as JSONB
- Do not store primary relationships solely as JSON arrays

---

## Phase 3: Services + API Endpoints

**Goal:** Create service layer and REST endpoints for CWOM CRUD operations.

### Deliverables
- [ ] Create `devops_control_tower/cwom/services.py`:
  - `RepoService`
  - `IssueService`
  - `ContextPacketService`
  - `ConstraintSnapshotService`
  - `DoctrineRefService`
  - `RunService`
  - `ArtifactService`
- [ ] Create API router `devops_control_tower/cwom/routes.py`:
  - `POST /cwom/repos` - Create repo
  - `GET /cwom/repos/{id}` - Get repo
  - `POST /cwom/issues` - Create issue
  - `GET /cwom/issues/{id}` - Get issue with related objects
  - `POST /cwom/context-packets` - Create context packet
  - `POST /cwom/constraint-snapshots` - Create constraint snapshot
  - `POST /cwom/doctrine-refs` - Create doctrine ref
  - `POST /cwom/runs` - Create run
  - `PATCH /cwom/runs/{id}` - Update run status/outputs
  - `POST /cwom/artifacts` - Create artifact
  - `GET /cwom/runs/{id}/artifacts` - List artifacts for run
- [ ] Add validation for immutability constraints
- [ ] Add tests for all endpoints

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
- [ ] Create adapter layer `devops_control_tower/cwom/task_adapter.py`:
  - `task_to_issue()` - Convert TaskCreateV1 to Issue + ContextPacket
  - `issue_to_task()` - Convert Issue back to Task format (for API compatibility)
- [ ] Modify `/tasks/enqueue` to optionally create CWOM objects
- [ ] Add `cwom_issue_id` foreign key to TaskModel
- [ ] Create migration for TaskModel update
- [ ] Ensure backward compatibility (existing Task API unchanged)

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

## Success Criteria (Phase 1)

- [ ] All 7 CWOM Pydantic schemas pass validation tests
- [ ] Schemas export valid JSON Schema
- [ ] Contract snapshot test exists and passes
- [ ] `docs/cwom/cwom-spec-v0.1.md` is the canonical spec location
- [ ] CLAUDE.md updated with CWOM section
