# CWOM v0.1 Completion Roadmap

**Date**: 2026-01-26
**Status**: Assessment Complete, Roadmap Created

---

## 1. Current State Assessment (Scorecard)

Based on the CWOM-DELIVERABLE-CHECKLIST.md requirements:

| Requirement | Status | Notes |
|------------|--------|-------|
| **Models for all 7 objects** | ✅ Present | Repo, Issue, ContextPacket, Run, Artifact, ConstraintSnapshot, DoctrineRef all in `cwom_models.py` |
| **Join tables exist** | ✅ Present | 6 join tables: issue↔context, issue↔doctrine, issue↔constraint, run↔context, run↔doctrine, context↔doctrine |
| **Migrations apply cleanly** | 🟡 Needs testing | Chain looks correct: `b2f6a732d137 → c3e8f9a21b4d → d4a9b8c2e5f6 → e5f6a7b8c9d0` |
| **Downgrade sanity works** | 🟡 Needs testing | Downgrade functions exist but untested |
| **CRUD tests cover linkage** | 🟡 Partial | Tests verify structure but not actual DB round-trip with relationships |
| **AuditLog exists** | ❌ Missing | Not implemented |

---

## 2. Critical Issues Found

### 2.1 Migration Chain Problem

There are **two separate migration directories**:
- `/migrations/versions/` - Contains `001_initial.py` (creates events, workflows, agents tables)
- `/devops_control_tower/db/migrations/versions/` - Contains the task and CWOM migrations

The migration chain in `devops_control_tower/db/migrations/versions/`:
```
b2f6a732d137 (tasks table) - down_revision = None
    ↓
c3e8f9a21b4d (CWOM tables) - down_revision = b2f6a732d137
    ↓
d4a9b8c2e5f6 (cwom_issue_id to tasks) - down_revision = c3e8f9a21b4d
    ↓
e5f6a7b8c9d0 (trace_id, jobs, artifacts) - down_revision = d4a9b8c2e5f6
```

**Problem**: The core models (Event, Workflow, Agent) have their tables created via `init_database()` using SQLAlchemy `create_all()`, but there's a separate `001_initial.py` migration in `/migrations/` that also creates them. This creates confusion about which migration path is authoritative.

**On Fresh DB**:
- `alembic upgrade head` will create: tasks, all CWOM tables, jobs, artifacts
- It will NOT create: events, workflows, agents (they rely on `init_database()`)

### 2.2 Missing CRUD Integration Tests

The existing tests verify:
- Model structure (columns exist)
- `to_dict()` output
- API endpoints work

**Missing**:
- Database round-trip with actual relationships loaded
- Query by join table (e.g., "find all runs governed by doctrine X")
- Immutability enforcement at DB level (currently just convention/API level)

### 2.3 trace_id Column Not in Models

Migration `e5f6a7b8c9d0` adds `trace_id` columns to all CWOM tables, but the SQLAlchemy models in `cwom_models.py` do not define these columns. This causes a mismatch between migration state and model definitions.

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

### Phase 2: Implement AuditLog (Priority: HIGH)

#### 2.1 Create AuditLog Model

**File**: `devops_control_tower/db/audit_models.py`

```python
class AuditLogModel(Base):
    """Audit log for forensics and event sourcing."""

    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True)
    ts = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)

    # Who did it
    actor_kind = Column(Enum("human", "agent", "system", name="audit_actor_kind"), nullable=False)
    actor_id = Column(String(128), nullable=False, index=True)

    # What action
    action = Column(String(50), nullable=False, index=True)  # created, updated, status_changed, deleted

    # What entity was affected
    entity_kind = Column(String(50), nullable=False, index=True)  # Repo, Issue, Run, Task, etc.
    entity_id = Column(String(128), nullable=False, index=True)

    # State before/after
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)

    # Context
    note = Column(Text, nullable=True)
    trace_id = Column(String(36), nullable=True, index=True)

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_kind", "entity_id"),
        Index("ix_audit_log_actor", "actor_kind", "actor_id"),
        Index("ix_audit_log_ts_action", "ts", "action"),
    )
```

#### 2.2 Create AuditLog Migration

**File**: `devops_control_tower/db/migrations/versions/f7a8b9c0d1e2_create_audit_log.py`

#### 2.3 Create AuditLog Service

**File**: `devops_control_tower/db/audit_service.py`

```python
class AuditService:
    @staticmethod
    def log_create(db: Session, entity_kind: str, entity_id: str, after: dict, actor: Actor, trace_id: str = None):
        ...

    @staticmethod
    def log_update(db: Session, entity_kind: str, entity_id: str, before: dict, after: dict, actor: Actor, trace_id: str = None):
        ...

    @staticmethod
    def log_status_change(db: Session, entity_kind: str, entity_id: str, old_status: str, new_status: str, actor: Actor):
        ...

    @staticmethod
    def query_by_entity(db: Session, entity_kind: str, entity_id: str) -> List[AuditLog]:
        ...

    @staticmethod
    def query_by_trace(db: Session, trace_id: str) -> List[AuditLog]:
        ...
```

#### 2.4 Integrate AuditLog with CWOM Services

Add audit logging to:
- Repo create
- Issue create/update/status_change
- Run create/update/status_change
- Artifact create
- ContextPacket create
- ConstraintSnapshot create
- DoctrineRef create

---

### Phase 3: Complete CRUD Tests (Priority: MEDIUM)

#### 3.1 Add DB Round-Trip Tests

**File**: `tests/test_cwom_crud_integration.py`

Test scenarios:
1. Create Repo → Create Issue under Repo → Query Issue by repo_id
2. Create Issue → Create ContextPacket for Issue → Verify immutability (update blocked)
3. Create Issue → Create ConstraintSnapshot → Link via join table → Query issues by constraint
4. Create DoctrineRef → Link to Issue → Query issues by doctrine
5. Create Run for Issue → Update status ready→running→done → Create Artifact → Query artifacts by run_id and issue_id

#### 3.2 Add Join Table Query Tests

Test that relationships are properly queryable:
```python
def test_find_runs_by_doctrine(db_session):
    """Find all runs governed by a specific doctrine."""
    doctrine = create_doctrine(...)
    run1 = create_run(...)
    run1.doctrine_refs_rel.append(doctrine)
    db_session.commit()

    # Query via join table
    runs = db_session.query(CWOMRunModel)\
        .join(run_doctrine_refs)\
        .filter(run_doctrine_refs.c.doctrine_ref_id == doctrine.id)\
        .all()

    assert len(runs) == 1
```

---

### Phase 4: Fresh DB Verification (Priority: HIGH)

#### 4.1 Create Verification Script

**File**: `scripts/verify_db_fresh.sh`

```bash
#!/bin/bash
# Verify migrations apply cleanly on fresh DB

set -e

# Create temp DB
export DATABASE_URL="sqlite:///./test_fresh_migration.db"
rm -f test_fresh_migration.db

# Run migrations
alembic upgrade head

# Verify tables exist
python -c "
from devops_control_tower.db.base import get_engine
from sqlalchemy import inspect

engine = get_engine()
tables = inspect(engine).get_table_names()

required = [
    'tasks', 'jobs', 'artifacts',
    'cwom_repos', 'cwom_issues', 'cwom_context_packets',
    'cwom_constraint_snapshots', 'cwom_doctrine_refs',
    'cwom_runs', 'cwom_artifacts',
    'cwom_issue_context_packets', 'cwom_issue_doctrine_refs',
    'cwom_issue_constraint_snapshots', 'cwom_run_context_packets',
    'cwom_run_doctrine_refs', 'cwom_context_packet_doctrine_refs',
    'audit_log',  # After Phase 2
]

missing = [t for t in required if t not in tables]
if missing:
    print(f'FAIL: Missing tables: {missing}')
    exit(1)

print(f'PASS: All {len(required)} required tables present')
"

# Test downgrade
alembic downgrade -1
alembic upgrade head

echo "SUCCESS: Fresh DB verification passed"
rm test_fresh_migration.db
```

#### 4.2 Add to CI

Add fresh DB verification to GitHub Actions workflow.

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
   - ⬜ AuditLog (after Phase 2)

2. **Alembic migrations**:
   - ⬜ `alembic upgrade head` succeeds on a fresh DB (creates ALL tables)
   - ⬜ `alembic downgrade -1` works at least one step
   - ⬜ `alembic history` shows a coherent chain (no forks)

3. **DB invariants**:
   - ✅ Primary keys, FKs, enums, timestamps
   - ✅ Relationship tables (join tables) exist
   - 🟡 Immutables enforced (API level only, no DB constraints)

4. **CRUD tests pass**:
   - 🟡 create/read/update where allowed
   - 🟡 ContextPacket + ConstraintSnapshot: update blocked
   - ⬜ Run emits Artifact and links correctly (needs integration test)
   - ⬜ Query via join tables works

5. **AuditLog**:
   - ⬜ Model exists
   - ⬜ Migration exists
   - ⬜ Service implemented
   - ⬜ Integrated with CWOM operations

---

## 6. Files to Create/Modify

### New Files
- `devops_control_tower/db/audit_models.py`
- `devops_control_tower/db/audit_service.py`
- `devops_control_tower/db/migrations/versions/f7a8b9c0d1e2_create_audit_log.py`
- `tests/test_cwom_crud_integration.py`
- `scripts/verify_db_fresh.sh`

### Modified Files
- `devops_control_tower/db/cwom_models.py` - Add trace_id columns
- `devops_control_tower/db/__init__.py` - Export AuditLog
- `devops_control_tower/cwom/services.py` - Add audit logging calls
- `.github/workflows/*.yml` - Add fresh DB verification step

---

## 7. Next Steps

1. **Immediate**: Run `alembic upgrade head` on a fresh SQLite DB to verify current state
2. **Phase 1**: Fix trace_id model mismatch (30min task)
3. **Phase 2**: Implement AuditLog (highest value add per checklist)
4. **Phase 3**: Add integration tests with real DB
5. **Phase 4**: CI verification
