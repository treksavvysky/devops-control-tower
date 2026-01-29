"""
Tests for the AuditLog model and service.

Verifies:
- AuditLogModel structure and to_dict()
- AuditService logging methods (create, update, status_change, delete, link, unlink)
- AuditService query methods (by entity, trace, actor, action)
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from devops_control_tower.db.base import Base
from devops_control_tower.db.audit_models import AuditLogModel
from devops_control_tower.db.audit_service import AuditService


@pytest.fixture
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestAuditLogModel:
    """Tests for AuditLogModel structure."""

    def test_model_has_required_columns(self, db_session):
        """Verify all required columns exist."""
        columns = {c.name for c in AuditLogModel.__table__.columns}
        required = {
            "id", "ts", "actor_kind", "actor_id", "action",
            "entity_kind", "entity_id", "before", "after",
            "note", "trace_id"
        }
        assert required.issubset(columns)

    def test_to_dict_output(self, db_session):
        """Verify to_dict() returns expected structure."""
        entry = AuditLogModel(
            id="test-id-123",
            ts=datetime(2026, 1, 26, 12, 0, 0, tzinfo=timezone.utc),
            actor_kind="human",
            actor_id="user-1",
            action="created",
            entity_kind="Issue",
            entity_id="issue-123",
            before=None,
            after={"title": "Test Issue"},
            note="Created via API",
            trace_id="trace-456",
        )

        result = entry.to_dict()

        assert result["id"] == "test-id-123"
        assert result["actor_kind"] == "human"
        assert result["actor_id"] == "user-1"
        assert result["action"] == "created"
        assert result["entity_kind"] == "Issue"
        assert result["entity_id"] == "issue-123"
        assert result["before"] is None
        assert result["after"] == {"title": "Test Issue"}
        assert result["note"] == "Created via API"
        assert result["trace_id"] == "trace-456"


class TestAuditServiceCreate:
    """Tests for AuditService.log_create()."""

    def test_log_create_basic(self, db_session):
        """Test basic create logging."""
        audit = AuditService(db_session)

        entry = audit.log_create(
            entity_kind="Repo",
            entity_id="repo-123",
            after={"name": "My Repo", "slug": "my/repo"},
            actor_kind="human",
            actor_id="user-1",
        )

        assert entry.id is not None
        assert entry.action == "created"
        assert entry.entity_kind == "Repo"
        assert entry.entity_id == "repo-123"
        assert entry.before is None
        assert entry.after == {"name": "My Repo", "slug": "my/repo"}

    def test_log_create_with_trace_id(self, db_session):
        """Test create logging with trace_id."""
        audit = AuditService(db_session)

        entry = audit.log_create(
            entity_kind="Issue",
            entity_id="issue-456",
            after={"title": "Fix bug"},
            trace_id="trace-789",
        )

        assert entry.trace_id == "trace-789"

    def test_log_create_persists_to_db(self, db_session):
        """Verify create entry is persisted."""
        audit = AuditService(db_session)

        entry = audit.log_create(
            entity_kind="Run",
            entity_id="run-123",
            after={"status": "planned"},
        )

        # Query back
        found = db_session.query(AuditLogModel).filter(
            AuditLogModel.id == entry.id
        ).first()

        assert found is not None
        assert found.entity_kind == "Run"
        assert found.action == "created"


class TestAuditServiceUpdate:
    """Tests for AuditService.log_update()."""

    def test_log_update_captures_before_after(self, db_session):
        """Test update logging captures both states."""
        audit = AuditService(db_session)

        entry = audit.log_update(
            entity_kind="Issue",
            entity_id="issue-123",
            before={"title": "Old Title", "priority": "P2"},
            after={"title": "New Title", "priority": "P1"},
            actor_kind="agent",
            actor_id="worker-1",
        )

        assert entry.action == "updated"
        assert entry.before == {"title": "Old Title", "priority": "P2"}
        assert entry.after == {"title": "New Title", "priority": "P1"}
        assert entry.actor_kind == "agent"


class TestAuditServiceStatusChange:
    """Tests for AuditService.log_status_change()."""

    def test_log_status_change(self, db_session):
        """Test status change logging."""
        audit = AuditService(db_session)

        entry = audit.log_status_change(
            entity_kind="Run",
            entity_id="run-123",
            old_status="planned",
            new_status="running",
            actor_kind="system",
            actor_id="worker-loop",
        )

        assert entry.action == "status_changed"
        assert entry.before == {"status": "planned"}
        assert entry.after == {"status": "running"}
        assert "planned -> running" in entry.note


class TestAuditServiceDelete:
    """Tests for AuditService.log_delete()."""

    def test_log_delete(self, db_session):
        """Test delete logging."""
        audit = AuditService(db_session)

        entry = audit.log_delete(
            entity_kind="Artifact",
            entity_id="artifact-123",
            before={"title": "Old Artifact", "type": "log"},
        )

        assert entry.action == "deleted"
        assert entry.before == {"title": "Old Artifact", "type": "log"}
        assert entry.after is None


class TestAuditServiceLink:
    """Tests for AuditService.log_link() and log_unlink()."""

    def test_log_link(self, db_session):
        """Test link logging."""
        audit = AuditService(db_session)

        entry = audit.log_link(
            entity_kind="Issue",
            entity_id="issue-123",
            linked_kind="ContextPacket",
            linked_id="cp-456",
        )

        assert entry.action == "linked"
        assert entry.after == {"linked_kind": "ContextPacket", "linked_id": "cp-456"}
        assert "ContextPacket:cp-456" in entry.note

    def test_log_unlink(self, db_session):
        """Test unlink logging."""
        audit = AuditService(db_session)

        entry = audit.log_unlink(
            entity_kind="Issue",
            entity_id="issue-123",
            unlinked_kind="DoctrineRef",
            unlinked_id="dr-789",
        )

        assert entry.action == "unlinked"
        assert entry.before == {"linked_kind": "DoctrineRef", "linked_id": "dr-789"}
        assert entry.after is None


class TestAuditServiceQueries:
    """Tests for AuditService query methods."""

    def test_query_by_entity(self, db_session):
        """Test querying by entity."""
        audit = AuditService(db_session)

        # Create multiple entries for different entities
        audit.log_create("Issue", "issue-1", {"title": "Issue 1"})
        audit.log_create("Issue", "issue-1", {"title": "Issue 1 v2"})  # Same entity
        audit.log_create("Issue", "issue-2", {"title": "Issue 2"})  # Different

        results = audit.query_by_entity("Issue", "issue-1")

        assert len(results) == 2
        for r in results:
            assert r.entity_id == "issue-1"

    def test_query_by_trace(self, db_session):
        """Test querying by trace ID."""
        audit = AuditService(db_session)

        trace_id = "trace-test-123"
        audit.log_create("Repo", "repo-1", {"name": "R1"}, trace_id=trace_id)
        audit.log_create("Issue", "issue-1", {"title": "I1"}, trace_id=trace_id)
        audit.log_create("Run", "run-1", {"status": "planned"}, trace_id=trace_id)
        audit.log_create("Repo", "repo-2", {"name": "R2"}, trace_id="other-trace")

        results = audit.query_by_trace(trace_id)

        assert len(results) == 3
        for r in results:
            assert r.trace_id == trace_id

    def test_query_by_actor(self, db_session):
        """Test querying by actor."""
        audit = AuditService(db_session)

        audit.log_create("Issue", "i1", {}, actor_kind="human", actor_id="user-1")
        audit.log_create("Issue", "i2", {}, actor_kind="human", actor_id="user-1")
        audit.log_create("Issue", "i3", {}, actor_kind="agent", actor_id="worker-1")

        results = audit.query_by_actor("human", "user-1")

        assert len(results) == 2
        for r in results:
            assert r.actor_kind == "human"
            assert r.actor_id == "user-1"

    def test_query_by_action(self, db_session):
        """Test querying by action type."""
        audit = AuditService(db_session)

        audit.log_create("Issue", "i1", {})
        audit.log_status_change("Issue", "i1", "planned", "running")
        audit.log_update("Issue", "i1", {}, {"title": "Updated"})
        audit.log_create("Run", "r1", {})

        # Query all created actions
        created = audit.query_by_action("created")
        assert len(created) == 2

        # Query created actions for Issues only
        created_issues = audit.query_by_action("created", entity_kind="Issue")
        assert len(created_issues) == 1

    def test_query_recent(self, db_session):
        """Test querying recent entries."""
        audit = AuditService(db_session)

        # Create 10 entries
        for i in range(10):
            audit.log_create("Issue", f"i{i}", {"num": i})

        # Get last 5
        results = audit.query_recent(limit=5)

        assert len(results) == 5


class TestAuditLogIndexes:
    """Tests verifying indexes exist on the model."""

    def test_indexes_defined(self):
        """Verify expected indexes are defined."""
        indexes = {idx.name for idx in AuditLogModel.__table__.indexes}

        # Check composite indexes from __table_args__
        assert "ix_audit_log_entity" in indexes
        assert "ix_audit_log_actor" in indexes
        assert "ix_audit_log_ts_action" in indexes
        assert "ix_audit_log_entity_ts" in indexes
