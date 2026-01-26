"""
Tests for CWOM v0.1 database models.

These tests verify that:
1. Models can be instantiated and have correct table names
2. Models have the expected columns
3. to_dict() methods return proper structures
4. Relationships are correctly defined
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import inspect


class TestCWOMRepoModel:
    """Tests for CWOMRepoModel."""

    def test_table_name(self):
        """Verify table name is correct."""
        from devops_control_tower.db.cwom_models import CWOMRepoModel
        assert CWOMRepoModel.__tablename__ == "cwom_repos"

    def test_has_required_columns(self):
        """Verify all required columns exist."""
        from devops_control_tower.db.cwom_models import CWOMRepoModel

        mapper = inspect(CWOMRepoModel)
        column_names = {col.key for col in mapper.columns}

        required = {
            "id", "kind", "name", "slug", "default_branch", "visibility",
            "source", "owners", "policy", "links", "tags", "meta",
            "created_at", "updated_at"
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    def test_to_dict_structure(self):
        """Verify to_dict returns expected structure."""
        from devops_control_tower.db.cwom_models import CWOMRepoModel

        model = CWOMRepoModel(
            id="test-id",
            name="test-repo",
            slug="test-repo",
            source={"system": "github", "url": "https://github.com/test/test"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        result = model.to_dict()
        assert result["kind"] == "Repo"
        assert result["id"] == "test-id"
        assert result["name"] == "test-repo"
        assert result["slug"] == "test-repo"
        assert "source" in result


class TestCWOMIssueModel:
    """Tests for CWOMIssueModel."""

    def test_table_name(self):
        """Verify table name is correct."""
        from devops_control_tower.db.cwom_models import CWOMIssueModel
        assert CWOMIssueModel.__tablename__ == "cwom_issues"

    def test_has_required_columns(self):
        """Verify all required columns exist."""
        from devops_control_tower.db.cwom_models import CWOMIssueModel

        mapper = inspect(CWOMIssueModel)
        column_names = {col.key for col in mapper.columns}

        required = {
            "id", "kind", "repo_id", "repo_kind", "title", "description",
            "type", "priority", "status", "assignees", "watchers",
            "acceptance", "relationships", "runs", "tags", "meta",
            "created_at", "updated_at"
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    def test_to_dict_includes_repo_ref(self):
        """Verify to_dict includes repo as a Ref object."""
        from devops_control_tower.db.cwom_models import CWOMIssueModel

        model = CWOMIssueModel(
            id="issue-id",
            repo_id="repo-id",
            repo_kind="Repo",
            title="Test Issue",
            type="feature",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        result = model.to_dict()
        assert result["kind"] == "Issue"
        assert result["repo"]["kind"] == "Repo"
        assert result["repo"]["id"] == "repo-id"


class TestCWOMContextPacketModel:
    """Tests for CWOMContextPacketModel."""

    def test_table_name(self):
        """Verify table name is correct."""
        from devops_control_tower.db.cwom_models import CWOMContextPacketModel
        assert CWOMContextPacketModel.__tablename__ == "cwom_context_packets"

    def test_has_required_columns(self):
        """Verify all required columns exist."""
        from devops_control_tower.db.cwom_models import CWOMContextPacketModel

        mapper = inspect(CWOMContextPacketModel)
        column_names = {col.key for col in mapper.columns}

        required = {
            "id", "kind", "for_issue_id", "for_issue_kind", "version",
            "summary", "inputs", "assumptions", "open_questions",
            "instructions", "constraint_snapshot_id", "tags", "meta",
            "created_at", "updated_at"
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    def test_to_dict_includes_issue_ref(self):
        """Verify to_dict includes for_issue as a Ref object."""
        from devops_control_tower.db.cwom_models import CWOMContextPacketModel

        model = CWOMContextPacketModel(
            id="cp-id",
            for_issue_id="issue-id",
            for_issue_kind="Issue",
            version="1.0",
            summary="Test context",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        result = model.to_dict()
        assert result["kind"] == "ContextPacket"
        assert result["for_issue"]["kind"] == "Issue"
        assert result["for_issue"]["id"] == "issue-id"


class TestCWOMConstraintSnapshotModel:
    """Tests for CWOMConstraintSnapshotModel."""

    def test_table_name(self):
        """Verify table name is correct."""
        from devops_control_tower.db.cwom_models import CWOMConstraintSnapshotModel
        assert CWOMConstraintSnapshotModel.__tablename__ == "cwom_constraint_snapshots"

    def test_has_required_columns(self):
        """Verify all required columns exist."""
        from devops_control_tower.db.cwom_models import CWOMConstraintSnapshotModel

        mapper = inspect(CWOMConstraintSnapshotModel)
        column_names = {col.key for col in mapper.columns}

        required = {
            "id", "kind", "scope", "captured_at",
            "owner_kind", "owner_id", "owner_display",
            "constraints", "tags", "meta"
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    def test_to_dict_includes_owner(self):
        """Verify to_dict includes owner as Actor object."""
        from devops_control_tower.db.cwom_models import CWOMConstraintSnapshotModel

        model = CWOMConstraintSnapshotModel(
            id="cs-id",
            scope="personal",
            owner_kind="human",
            owner_id="user-123",
            owner_display="Test User",
            captured_at=datetime.now(timezone.utc),
        )

        result = model.to_dict()
        assert result["kind"] == "ConstraintSnapshot"
        assert result["owner"]["actor_kind"] == "human"
        assert result["owner"]["actor_id"] == "user-123"
        assert result["owner"]["display"] == "Test User"


class TestCWOMDoctrineRefModel:
    """Tests for CWOMDoctrineRefModel."""

    def test_table_name(self):
        """Verify table name is correct."""
        from devops_control_tower.db.cwom_models import CWOMDoctrineRefModel
        assert CWOMDoctrineRefModel.__tablename__ == "cwom_doctrine_refs"

    def test_has_required_columns(self):
        """Verify all required columns exist."""
        from devops_control_tower.db.cwom_models import CWOMDoctrineRefModel

        mapper = inspect(CWOMDoctrineRefModel)
        column_names = {col.key for col in mapper.columns}

        required = {
            "id", "kind", "namespace", "name", "version", "type", "priority",
            "statement", "rationale", "links", "applicability",
            "tags", "meta", "created_at", "updated_at"
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    def test_to_dict_structure(self):
        """Verify to_dict returns expected structure."""
        from devops_control_tower.db.cwom_models import CWOMDoctrineRefModel

        model = CWOMDoctrineRefModel(
            id="dr-id",
            namespace="org/security",
            name="no-secrets-in-logs",
            version="1.0",
            type="policy",
            priority="must",
            statement="Never log secrets",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        result = model.to_dict()
        assert result["kind"] == "DoctrineRef"
        assert result["namespace"] == "org/security"
        assert result["name"] == "no-secrets-in-logs"
        assert result["type"] == "policy"
        assert result["priority"] == "must"


class TestCWOMRunModel:
    """Tests for CWOMRunModel."""

    def test_table_name(self):
        """Verify table name is correct."""
        from devops_control_tower.db.cwom_models import CWOMRunModel
        assert CWOMRunModel.__tablename__ == "cwom_runs"

    def test_has_required_columns(self):
        """Verify all required columns exist."""
        from devops_control_tower.db.cwom_models import CWOMRunModel

        mapper = inspect(CWOMRunModel)
        column_names = {col.key for col in mapper.columns}

        required = {
            "id", "kind", "for_issue_id", "for_issue_kind", "repo_id", "repo_kind",
            "status", "mode", "executor", "inputs", "constraint_snapshot_id",
            "plan", "telemetry", "cost", "outputs", "failure",
            "tags", "meta", "created_at", "updated_at"
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    def test_to_dict_includes_refs(self):
        """Verify to_dict includes issue and repo refs."""
        from devops_control_tower.db.cwom_models import CWOMRunModel

        model = CWOMRunModel(
            id="run-id",
            for_issue_id="issue-id",
            for_issue_kind="Issue",
            repo_id="repo-id",
            repo_kind="Repo",
            mode="agent",
            executor={"actor": {"actor_kind": "agent", "actor_id": "claude"}, "runtime": "local", "toolchain": []},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        result = model.to_dict()
        assert result["kind"] == "Run"
        assert result["for_issue"]["kind"] == "Issue"
        assert result["for_issue"]["id"] == "issue-id"
        assert result["repo"]["kind"] == "Repo"
        assert result["repo"]["id"] == "repo-id"
        assert result["mode"] == "agent"


class TestCWOMArtifactModel:
    """Tests for CWOMArtifactModel."""

    def test_table_name(self):
        """Verify table name is correct."""
        from devops_control_tower.db.cwom_models import CWOMArtifactModel
        assert CWOMArtifactModel.__tablename__ == "cwom_artifacts"

    def test_has_required_columns(self):
        """Verify all required columns exist."""
        from devops_control_tower.db.cwom_models import CWOMArtifactModel

        mapper = inspect(CWOMArtifactModel)
        column_names = {col.key for col in mapper.columns}

        required = {
            "id", "kind", "produced_by_id", "produced_by_kind",
            "for_issue_id", "for_issue_kind", "type", "title", "uri",
            "digest", "media_type", "size_bytes", "preview",
            "verification", "tags", "meta", "created_at", "updated_at"
        }
        assert required.issubset(column_names), f"Missing columns: {required - column_names}"

    def test_to_dict_includes_refs(self):
        """Verify to_dict includes produced_by and for_issue refs."""
        from devops_control_tower.db.cwom_models import CWOMArtifactModel

        model = CWOMArtifactModel(
            id="artifact-id",
            produced_by_id="run-id",
            produced_by_kind="Run",
            for_issue_id="issue-id",
            for_issue_kind="Issue",
            type="pr",
            title="Fix bug #123",
            uri="https://github.com/test/test/pull/456",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        result = model.to_dict()
        assert result["kind"] == "Artifact"
        assert result["produced_by"]["kind"] == "Run"
        assert result["produced_by"]["id"] == "run-id"
        assert result["for_issue"]["kind"] == "Issue"
        assert result["for_issue"]["id"] == "issue-id"
        assert result["type"] == "pr"


class TestJoinTables:
    """Tests for join table definitions."""

    def test_join_tables_exist(self):
        """Verify all join tables are defined."""
        from devops_control_tower.db import cwom_models

        # Check join tables exist as Table objects
        assert hasattr(cwom_models, "issue_context_packets")
        assert hasattr(cwom_models, "issue_doctrine_refs")
        assert hasattr(cwom_models, "issue_constraint_snapshots")
        assert hasattr(cwom_models, "run_context_packets")
        assert hasattr(cwom_models, "run_doctrine_refs")
        assert hasattr(cwom_models, "context_packet_doctrine_refs")

    def test_join_table_names(self):
        """Verify join table names follow convention."""
        from devops_control_tower.db.cwom_models import (
            issue_context_packets,
            issue_doctrine_refs,
            issue_constraint_snapshots,
            run_context_packets,
            run_doctrine_refs,
            context_packet_doctrine_refs,
        )

        assert issue_context_packets.name == "cwom_issue_context_packets"
        assert issue_doctrine_refs.name == "cwom_issue_doctrine_refs"
        assert issue_constraint_snapshots.name == "cwom_issue_constraint_snapshots"
        assert run_context_packets.name == "cwom_run_context_packets"
        assert run_doctrine_refs.name == "cwom_run_doctrine_refs"
        assert context_packet_doctrine_refs.name == "cwom_context_packet_doctrine_refs"


class TestModelExports:
    """Tests for model exports from package."""

    def test_cwom_models_exported_from_db_package(self):
        """Verify CWOM models are exported from db package."""
        from devops_control_tower.db import (
            CWOMRepoModel,
            CWOMIssueModel,
            CWOMContextPacketModel,
            CWOMConstraintSnapshotModel,
            CWOMDoctrineRefModel,
            CWOMRunModel,
            CWOMArtifactModel,
        )

        # Just verify they can be imported - no assertions needed
        assert CWOMRepoModel is not None
        assert CWOMIssueModel is not None
        assert CWOMContextPacketModel is not None
        assert CWOMConstraintSnapshotModel is not None
        assert CWOMDoctrineRefModel is not None
        assert CWOMRunModel is not None
        assert CWOMArtifactModel is not None
