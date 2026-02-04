"""
Tests for Task-CWOM integration (Phase 4).

Tests the bidirectional mapping between JCT V1 Tasks and CWOM objects.
"""

import pytest

from devops_control_tower.cwom.task_adapter import (
    task_to_cwom,
    issue_to_task,
    OPERATION_TO_ISSUE_TYPE,
    ISSUE_TYPE_TO_OPERATION,
)
from devops_control_tower.cwom.enums import IssueType, Status
from devops_control_tower.schemas.task_v1 import (
    TaskCreateV1,
    TaskCreateLegacyV1,
    RequestedBy,
    Target,
    TargetV1,
    Constraints,
)


# Note: client and db_session fixtures are provided by conftest.py


# Fixture for sample task spec
@pytest.fixture
def sample_task_v1():
    """Create a sample TaskCreateV1 for testing."""
    return TaskCreateV1(
        version="1.0",
        idempotency_key="test-task-cwom-001",
        requested_by=RequestedBy(
            kind="human",
            id="test-user",
            label="Test User",
        ),
        objective="Add /healthz endpoint and verify it returns 200 OK",
        operation="code_change",
        target=TargetV1(
            repo="testorg/test-repo",
            ref="main",
            path="src/api",
        ),
        constraints=Constraints(
            time_budget_seconds=600,
            allow_network=False,
            allow_secrets=False,
        ),
        inputs={"priority": "high"},
        metadata={"tags": ["test", "health-check"]},
    )


@pytest.fixture
def sample_legacy_task():
    """Create a sample TaskCreateLegacyV1 for testing."""
    return TaskCreateLegacyV1(
        version="1.0",
        idempotency_key="test-legacy-task-001",
        requested_by=RequestedBy(
            kind="agent",
            id="ci-bot",
            label="CI Bot",
        ),
        objective="Update documentation for API endpoints",
        type="docs",  # Legacy field
        target=Target(
            repo="testorg/docs-repo",
            ref="develop",
            path="docs/api",
        ),
        payload={"format": "markdown"},  # Legacy field
        metadata={"source": "legacy-system"},
    )


class TestOperationMapping:
    """Tests for operation to IssueType mapping."""

    def test_operation_to_issue_type_code_change(self):
        """code_change maps to FEATURE."""
        assert OPERATION_TO_ISSUE_TYPE["code_change"] == IssueType.FEATURE

    def test_operation_to_issue_type_docs(self):
        """docs maps to DOC."""
        assert OPERATION_TO_ISSUE_TYPE["docs"] == IssueType.DOC

    def test_operation_to_issue_type_analysis(self):
        """analysis maps to RESEARCH."""
        assert OPERATION_TO_ISSUE_TYPE["analysis"] == IssueType.RESEARCH

    def test_operation_to_issue_type_ops(self):
        """ops maps to OPS."""
        assert OPERATION_TO_ISSUE_TYPE["ops"] == IssueType.OPS

    def test_issue_type_to_operation_feature(self):
        """FEATURE maps back to code_change."""
        assert ISSUE_TYPE_TO_OPERATION[IssueType.FEATURE] == "code_change"

    def test_issue_type_to_operation_bug(self):
        """BUG also maps to code_change."""
        assert ISSUE_TYPE_TO_OPERATION[IssueType.BUG] == "code_change"

    def test_issue_type_to_operation_doc(self):
        """DOC maps back to docs."""
        assert ISSUE_TYPE_TO_OPERATION[IssueType.DOC] == "docs"


class TestTaskToCWOM:
    """Tests for task_to_cwom conversion."""

    def test_task_to_cwom_creates_repo(self, db_session, sample_task_v1):
        """task_to_cwom creates a Repo for the target."""
        result = task_to_cwom(sample_task_v1, db_session)

        assert result.repo is not None
        assert result.repo.slug == "testorg/test-repo"
        assert result.repo.name == "test-repo"

    def test_task_to_cwom_creates_issue(self, db_session, sample_task_v1):
        """task_to_cwom creates an Issue linked to the Repo."""
        result = task_to_cwom(sample_task_v1, db_session)

        assert result.issue is not None
        assert result.issue.title == sample_task_v1.objective.split("\n")[0][:200]
        assert result.issue.description == sample_task_v1.objective
        assert result.issue.type == IssueType.FEATURE.value
        assert result.issue.status == Status.PLANNED.value

    def test_task_to_cwom_creates_context_packet(self, db_session, sample_task_v1):
        """task_to_cwom creates a ContextPacket with task data in meta."""
        result = task_to_cwom(sample_task_v1, db_session)

        assert result.context_packet is not None
        assert result.context_packet.meta is not None
        # Task inputs are stored in meta (ContextInputs only accepts documents/blobs/links)
        meta = result.context_packet.meta
        assert meta.get("task_ref") == "main"
        assert meta.get("task_path") == "src/api"
        assert meta.get("task_inputs", {}).get("priority") == "high"

    def test_task_to_cwom_creates_constraint_snapshot(self, db_session, sample_task_v1):
        """task_to_cwom creates a ConstraintSnapshot from constraints."""
        result = task_to_cwom(sample_task_v1, db_session)

        assert result.constraint_snapshot is not None
        # Original task constraints are stored in meta for round-trip fidelity
        meta = result.constraint_snapshot.meta
        assert meta is not None
        assert meta.get("time_budget_seconds") == 600
        assert meta.get("allow_network") is False
        assert meta.get("allow_secrets") is False

    def test_task_to_cwom_legacy_task(self, db_session, sample_legacy_task):
        """task_to_cwom handles legacy tasks with type/payload aliases."""
        result = task_to_cwom(sample_legacy_task, db_session)

        # Should create all objects
        assert result.repo is not None
        assert result.issue is not None
        assert result.context_packet is not None
        assert result.constraint_snapshot is not None

        # Issue type should be DOC (from 'docs' operation)
        assert result.issue.type == IssueType.DOC.value


class TestIssueToTask:
    """Tests for issue_to_task conversion."""

    def test_issue_to_task_basic(self, db_session, sample_task_v1):
        """issue_to_task converts CWOM objects back to Task format."""
        # First create CWOM objects
        cwom = task_to_cwom(sample_task_v1, db_session)

        # Now convert back to task format
        task_dict = issue_to_task(
            cwom.issue,
            context_packet=cwom.context_packet,
            constraint_snapshot=cwom.constraint_snapshot,
            repo=cwom.repo,
        )

        assert task_dict["version"] == "1.0"
        assert task_dict["operation"] == "code_change"
        assert task_dict["objective"] == sample_task_v1.objective
        assert task_dict["target"]["repo"] == "testorg/test-repo"

    def test_issue_to_task_preserves_constraints(self, db_session, sample_task_v1):
        """issue_to_task preserves constraints from ConstraintSnapshot."""
        cwom = task_to_cwom(sample_task_v1, db_session)

        task_dict = issue_to_task(
            cwom.issue,
            constraint_snapshot=cwom.constraint_snapshot,
            repo=cwom.repo,
        )

        assert task_dict["constraints"]["time_budget_seconds"] == 600
        assert task_dict["constraints"]["allow_network"] is False
        assert task_dict["constraints"]["allow_secrets"] is False


class TestEnqueueWithCWOM:
    """Tests for /tasks/enqueue with create_cwom flag."""

    def test_enqueue_without_cwom(self, client):
        """Enqueue task without CWOM objects (default behavior)."""
        task_data = {
            "version": "1.0",
            "idempotency_key": "test-no-cwom-001",
            "requested_by": {
                "kind": "human",
                "id": "tester",
                "label": "Tester",
            },
            "objective": "Test task without CWOM creation",
            "operation": "code_change",
            "target": {
                "repo": "testorg/test-repo",
                "ref": "main",
                "path": "",
            },
            "constraints": {
                "time_budget_seconds": 300,
                "allow_network": False,
                "allow_secrets": False,
            },
            "inputs": {},
            "metadata": {},
        }

        response = client.post("/tasks/enqueue?create_cwom=false", json=task_data)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "task_id" in data
        # Should NOT have CWOM objects when create_cwom=false
        assert "cwom" not in data

    def test_enqueue_with_cwom(self, client):
        """Enqueue task with CWOM object creation."""
        task_data = {
            "version": "1.0",
            "idempotency_key": "test-with-cwom-001",
            "requested_by": {
                "kind": "human",
                "id": "tester",
                "label": "Tester",
            },
            "objective": "Test task with CWOM creation",
            "operation": "code_change",
            "target": {
                "repo": "testorg/cwom-test-repo",
                "ref": "main",
                "path": "",
            },
            "constraints": {
                "time_budget_seconds": 300,
                "allow_network": False,
                "allow_secrets": False,
            },
            "inputs": {},
            "metadata": {},
        }

        response = client.post("/tasks/enqueue?create_cwom=true", json=task_data)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "task_id" in data
        # Should have CWOM objects (create_cwom=true)
        assert "cwom" in data
        assert "repo_id" in data["cwom"]
        assert "issue_id" in data["cwom"]
        assert "context_packet_id" in data["cwom"]
        assert "constraint_snapshot_id" in data["cwom"]

    def test_enqueue_with_cwom_links_task(self, client):
        """Enqueue with CWOM links the task to the issue."""
        task_data = {
            "version": "1.0",
            "idempotency_key": "test-cwom-link-001",
            "requested_by": {
                "kind": "human",
                "id": "tester",
            },
            "objective": "Test task-CWOM linking",
            "operation": "analysis",
            "target": {
                "repo": "testorg/link-test",
                "ref": "main",
                "path": "",
            },
        }

        response = client.post("/tasks/enqueue?create_cwom=true", json=task_data)

        assert response.status_code == 201
        data = response.json()

        # Task should have cwom_issue_id set
        task = data["task"]
        assert task.get("cwom_issue_id") == data["cwom"]["issue_id"]
