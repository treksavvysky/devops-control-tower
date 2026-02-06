# CWOM v0.1 Completion Roadmap

**Date**: 2026-01-26
**Updated**: 2026-02-06
**Status**: Phase 1-4 Complete

---

## 1. Current State Assessment (Scorecard)

Based on the CWOM-DELIVERABLE-CHECKLIST.md requirements:

| Requirement | Status | Notes |
|------------|--------|-------|
| **Models for all 7 objects** | ✅ Present | Repo, Issue, ContextPacket, Run, Artifact, ConstraintSnapshot, DoctrineRef all in `cwom_models.py` |
| **Join tables exist** | ✅ Present | 6 join tables: issue↔context, issue↔doctrine, issue↔constraint, run↔context, run↔doctrine, context↔doctrine |
| **Migrations apply cleanly** | ✅ Fixed | Chain: `a1b2c3d4e5f6 → b2f6a732d137 → c3e8f9a21b4d → d4a9b8c2e5f6 → e5f6a7b8c9d0` |
| **Downgrade sanity works** | 🟡 Needs testing | Downgrade functions exist with dialect checks, untested at runtime |
| **CRUD tests cover linkage** | ✅ Complete | Phase 3: 55 integration tests in `test_cwom_crud_integration.py` (DB round-trips, relationships, join tables, causality chain) |
| **AuditLog exists** | ✅ Complete | Phase 2 implemented |

---

## 2. Critical Issues Found (Phase 1 - RESOLVED)

### 2.1 Migration Chain Problem ✅ FIXED

~~There are **two separate migration directories**~~

**Resolution (2026-01-26):**
- Created new migration `a1b2c3d4e5f6_create_core_tables.py` for events, workflows, agents
- Updated `b2f6a732d137` to depend on `a1b2c3d4e5f6`
- Deleted orphaned `/migrations/` directory
- Updated `init_database()` to NOT call `create_all()` (now just verifies connection)
- Made all migrations SQLite-compatible with dialect checks

The migration chain is now:
```
a1b2c3d4e5f6 (core: events, workflows, agents) - down_revision = None
    ↓
b2f6a732d137 (tasks table) - down_revision = a1b2c3d4e5f6
    ↓
c3e8f9a21b4d (CWOM tables) - down_revision = b2f6a732d137
    ↓
d4a9b8c2e5f6 (cwom_issue_id to tasks) - down_revision = c3e8f9a21b4d
    ↓
e5f6a7b8c9d0 (trace_id, jobs, artifacts) - down_revision = d4a9b8c2e5f6
```

**On Fresh DB**: `alembic upgrade head` now creates ALL tables.

### 2.2 Missing CRUD Integration Tests (Phase 3)

The existing tests verify:
- Model structure (columns exist)
- `to_dict()` output
- API endpoints work

**Still Missing** (to be addressed in Phase 3):
- Database round-trip with actual relationships loaded
- Query by join table (e.g., "find all runs governed by doctrine X")
- Immutability enforcement at DB level (currently just convention/API level)

### 2.3 trace_id Column Not in Models ✅ FIXED

~~Migration `e5f6a7b8c9d0` adds `trace_id` columns to all CWOM tables, but the SQLAlchemy models in `cwom_models.py` do not define these columns.~~

**Resolution (2026-01-26):**
- Added `trace_id = Column(String(36), nullable=True, index=True)` to all 7 CWOM model classes
- Updated all `to_dict()` methods to include `trace_id`

---

## 3. Roadmap

### Phase 1: Fix Critical Issues (Priority: HIGH)

#### 1.1 Consolidate Migration Strategy
**Goal**: Single source of truth for all tables

**Option A (Recommended)**: Alembic manages everything
- Create migration to add events, workflows, agents tables if they don't exist
- Remove `init_database()` table creation (keep session init only)
- Ensure `alembic upgrade head` creates all tables

**Option B**: SQLAlchemy creates, Alembic evolves
- Keep `init_database()` for initial creation
- Use Alembic only for schema changes
- Document this hybrid approach

**Deliverable**: Fresh DB test passes with all 17+ tables created

#### 1.2 Add trace_id to CWOM Models
**Goal**: Model/migration alignment

Add to each CWOM model class:
```python
trace_id = Column(String(36), nullable=True, index=True)
```

**Files to update**:
- `devops_control_tower/db/cwom_models.py` (all 7 model classes)

**Deliverable**: Models match migration state

#### 1.3 Consolidate Migrations Directory
**Goal**: Single migration location

Options:
- Move `/migrations/versions/001_initial.py` content into main chain
- Or delete `/migrations/` if not needed

---

### Phase 2: Implement AuditLog (Priority: HIGH) ✅ COMPLETE

**Completed**: 2026-01-26

#### 2.1 Create AuditLog Model ✅

**File**: `devops_control_tower/db/audit_models.py`

Model created with:
- `id`, `ts`, `actor_kind`, `actor_id`, `action`
- `entity_kind`, `entity_id`, `before`, `after`
- `note`, `trace_id`
- Actions: `created`, `updated`, `status_changed`, `deleted`, `linked`, `unlinked`

#### 2.2 Create AuditLog Migration ✅

**File**: `devops_control_tower/db/migrations/versions/f7a8b9c0d1e2_create_audit_log.py`

Creates `audit_log` table with 10 indexes for efficient querying.

#### 2.3 Create AuditLog Service ✅

**File**: `devops_control_tower/db/audit_service.py`

Methods:
- `log_create()` - Log object creation
- `log_update()` - Log object updates
- `log_status_change()` - Log status transitions
- `log_delete()` - Log object deletion
- `log_link()` - Log relationship creation
- `log_unlink()` - Log relationship removal
- `query_by_entity()` - Get history for an entity
- `query_by_trace()` - Get events by trace_id
- `query_by_actor()` - Get events by actor
- `query_by_action()` - Get events by action type
- `query_recent()` - Get recent events

#### 2.4 Integrate AuditLog with CWOM Services ✅

All CWOM services updated with audit integration:
- `RepoService.create()` - logs creation
- `IssueService.create()`, `update_status()`, `link_*()` - logs all changes
- `ContextPacketService.create()` - logs creation (immutable)
- `ConstraintSnapshotService.create()` - logs creation (immutable)
- `DoctrineRefService.create()` - logs creation
- `RunService.create()`, `update()` - logs creation and updates
- `ArtifactService.create()` - logs creation

All methods accept optional `actor_kind`, `actor_id`, `trace_id` parameters.

#### 2.5 Tests ✅

**File**: `tests/test_audit_log.py`

Tests for:
- Model structure and `to_dict()`
- All logging methods
- All query methods
- Index existence verification

---

### Phase 3: Complete CRUD Tests (Priority: MEDIUM) ✅ COMPLETE

**Completed**: 2026-02-05

**File**: `tests/test_cwom_crud_integration.py` — 55 tests across 8 classes

#### 3.1 DB Round-Trip Tests ✅
- `TestRepoRoundTrip` (4 tests): create/get/list/to_dict via RepoService
- `TestIssueRoundTrip` (5 tests): create/get/list, repo relationship loading

#### 3.2 Relationship Loading Tests ✅
- `TestRelationshipLoading` (12 tests): All 6 join tables, FK relationships, backrefs, auto-linking via RunService and ContextPacketService

#### 3.3 Join Table Query Tests ✅
- `TestJoinTableQueries` (7 tests): Query through join tables (issues by doctrine, runs by context packet, etc.), service list/filter methods, latest context packet

#### 3.4 Full Causality Chain Tests ✅
- `TestFullCausalityChain` (5 tests): Complete 9-object chain (Repo→Issue→CP+CS+DR→Run→Artifact→EP→Review), forward/backward traversal, to_dict refs, multiple runs

#### 3.5 Immutability Tests ✅
- `TestImmutability` (4 tests): CP/CS have no update methods, versioning, data unchanged after reread

#### 3.6 Status Transition Tests ✅
- `TestStatusTransitions` (7 tests): Issue/Run status flow, telemetry updates, review-driven transitions (approved→done, rejected→failed)

#### 3.7 Audit Trail and Edge Cases ✅
- `TestAuditTrailAndEdgeCases` (11 tests): Audit logging for create/status_change/link, duplicate link handling, missing refs, unique constraints

---

### Phase 4: Fresh DB Verification (Priority: HIGH) ✅ COMPLETE

**Completed**: 2026-02-06

#### 4.1 Create Verification Script ✅

**File**: `scripts/verify_db_fresh.sh`

Script performs 5 checks:
1. `alembic upgrade head` on fresh SQLite DB
2. Verify all 22 application tables + alembic_version exist
3. `alembic downgrade -1` succeeds
4. Re-upgrade to head succeeds
5. Migration history is linear (no forks) — walks the chain programmatically

#### 4.2 Add to CI ✅

**File**: `.github/workflows/ci.yml`

Added two CI steps after tests:
- **SQLite**: Runs `scripts/verify_db_fresh.sh` (full 5-check verification)
- **PostgreSQL**: Creates fresh DB, runs upgrade/downgrade/upgrade cycle against Postgres service

---

## 4. Implementation Order

| Phase | Task | Effort | Blocks |
|-------|------|--------|--------|
| 1.1 | Consolidate migration strategy | 2h | - |
| 1.2 | Add trace_id to CWOM models | 30m | - |
| 1.3 | Clean up migration directories | 1h | 1.1 |
| 2.1 | Create AuditLog model | 1h | - |
| 2.2 | Create AuditLog migration | 30m | 2.1 |
| 2.3 | Create AuditLog service | 2h | 2.1, 2.2 |
| 2.4 | Integrate AuditLog with CWOM | 3h | 2.3 |
| 3.1 | DB round-trip tests | 2h | 1.*, 2.* |
| 3.2 | Join table query tests | 2h | 1.* |
| 4.1 | Fresh DB verification script | 1h | 1.*, 2.* |
| 4.2 | Add to CI | 30m | 4.1 |

**Total Estimated Effort**: ~15 hours

---

## 5. Definition of Done (Updated)

Pass means all of this is true:

1. **SQLAlchemy models exist for**:
   - ✅ Repo, Issue, ContextPacket, Run, Artifact, ConstraintSnapshot, DoctrineRef
   - ✅ AuditLog (Phase 2 complete)

2. **Alembic migrations**:
   - ✅ `alembic upgrade head` succeeds on a fresh DB (creates ALL tables)
   - ✅ `alembic downgrade -1` works at least one step
   - ✅ `alembic history` shows a coherent chain (no forks)

3. **DB invariants**:
   - ✅ Primary keys, FKs, enums, timestamps
   - ✅ Relationship tables (join tables) exist
   - 🟡 Immutables enforced (API level only, no DB constraints)

4. **CRUD tests pass**:
   - ✅ create/read/update where allowed (Phase 3: TestRepoRoundTrip, TestIssueRoundTrip, TestStatusTransitions)
   - ✅ ContextPacket + ConstraintSnapshot: update blocked (Phase 3: TestImmutability)
   - ✅ Run emits Artifact and links correctly (Phase 3: TestRelationshipLoading, TestFullCausalityChain)
   - ✅ Query via join tables works (Phase 3: TestJoinTableQueries)

5. **AuditLog**:
   - ✅ Model exists (`db/audit_models.py`)
   - ✅ Migration exists (`f7a8b9c0d1e2_create_audit_log.py`)
   - ✅ Service implemented (`db/audit_service.py`)
   - ✅ Integrated with CWOM operations (all services)

---

## 6. Files Created/Modified

### Phase 2 Files (Complete)
- ✅ `devops_control_tower/db/audit_models.py` - Created
- ✅ `devops_control_tower/db/audit_service.py` - Created
- ✅ `devops_control_tower/db/migrations/versions/f7a8b9c0d1e2_create_audit_log.py` - Created
- ✅ `devops_control_tower/db/__init__.py` - Updated to export AuditLog
- ✅ `devops_control_tower/cwom/services.py` - Updated with audit logging
- ✅ `tests/test_audit_log.py` - Created

### Phase 3 Files (Complete)
- ✅ `tests/test_cwom_crud_integration.py` - Created (55 tests, 8 classes)

### Phase 4 Files (Complete)
- ✅ `scripts/verify_db_fresh.sh` - Updated (5-check verification with table inventory and fork detection)
- ✅ `.github/workflows/ci.yml` - Updated (SQLite + PostgreSQL fresh DB verification steps)

---

## 7. Next Steps

1. ~~**Immediate**: Run `alembic upgrade head` on a fresh SQLite DB to verify current state~~ ✅
2. ~~**Phase 1**: Fix trace_id model mismatch~~ ✅ Complete
3. ~~**Phase 2**: Implement AuditLog~~ ✅ Complete (2026-01-26)
4. ~~**Phase 3**: Add integration tests with real DB~~ ✅ Complete (2026-02-05)
5. ~~**Phase 4**: CI verification~~ ✅ Complete (2026-02-06)
