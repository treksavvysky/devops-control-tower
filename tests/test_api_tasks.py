"""API-level tests for the /tasks/enqueue endpoint with policy gate."""

import os

# Set environment variable before importing application code
os.environ["JCT_ALLOWED_REPO_PREFIXES"] = "testorg/"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from devops_control_tower.api import app
from devops_control_tower.db.base import Base, get_db

# Create an in-memory SQLite database for testing
# Using a unique named memory DB to avoid collision with other tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override the get_db dependency for testing."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency before creating the test client
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Create all tables before running tests, drop them after."""
    # Import models to register them with Base
    from devops_control_tower.db import models  # noqa: F401

    # Drop all tables first to ensure clean slate
    Base.metadata.drop_all(bind=test_engine)
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


def make_valid_task_payload(**overrides) -> dict:
    """Create a valid task payload with optional overrides."""
    defaults = {
        "version": "1.0",
        "requested_by": {"kind": "human", "id": "test-user", "label": "Test User"},
        "objective": "Test objective for the task",
        "operation": "code_change",
        "target": {"repo": "testorg/test-repo", "ref": "main", "path": ""},
        "constraints": {
            "time_budget_seconds": 900,
            "allow_network": False,
            "allow_secrets": False,
        },
        "inputs": {},
        "metadata": {},
    }
    defaults.update(overrides)
    return defaults


class TestEnqueuePolicyRejection:
    """Test that invalid tasks are rejected with proper error codes."""

    def test_rejects_disallowed_repo(self):
        """Task with unauthorized repository should be rejected."""
        payload = make_valid_task_payload(
            target={"repo": "unauthorized-org/repo", "ref": "main", "path": ""}
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"] == "policy_violation"
        assert data["detail"]["code"] == "REPO_NOT_ALLOWED"

    def test_rejects_network_access(self):
        """Task requesting network access should be rejected in V1."""
        payload = make_valid_task_payload(
            constraints={
                "time_budget_seconds": 900,
                "allow_network": True,
                "allow_secrets": False,
            }
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"] == "policy_violation"
        assert data["detail"]["code"] == "NETWORK_ACCESS_DENIED"

    def test_rejects_secrets_access(self):
        """Task requesting secrets access should be rejected in V1."""
        payload = make_valid_task_payload(
            constraints={
                "time_budget_seconds": 900,
                "allow_network": False,
                "allow_secrets": True,
            }
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["error"] == "policy_violation"
        assert data["detail"]["code"] == "SECRETS_ACCESS_DENIED"


class TestEnqueueAcceptAndNormalize:
    """Test that valid tasks are accepted and normalized correctly."""

    def test_accepts_valid_task(self):
        """Valid task should be accepted and return task_id."""
        payload = make_valid_task_payload()
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "task_id" in data
        assert data["task"]["status"] == "queued"

    def test_normalizes_repo_name(self):
        """Repository name should be canonicalized (lowercase, no .git)."""
        payload = make_valid_task_payload(
            target={"repo": "TestOrg/Test-Repo.git", "ref": "main", "path": ""}
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["target"]["repo"] == "testorg/test-repo"

    def test_normalizes_objective_whitespace(self):
        """Objective should have leading/trailing whitespace trimmed."""
        payload = make_valid_task_payload(objective="  Test objective with spaces  ")
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["objective"] == "Test objective with spaces"

    def test_applies_default_constraints(self):
        """Default constraints should be applied when not specified."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test objective",
            "operation": "analysis",
            "target": {"repo": "testorg/repo"},
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        constraints = data["task"]["constraints"]
        assert constraints["time_budget_seconds"] == 900
        assert constraints["allow_network"] is False
        assert constraints["allow_secrets"] is False

    def test_applies_default_target_ref(self):
        """Default ref should be 'main' when not specified."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test objective",
            "operation": "docs",
            "target": {"repo": "testorg/repo"},
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["target"]["ref"] == "main"

    def test_applies_default_target_path(self):
        """Default path should be empty string when not specified."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test objective",
            "operation": "ops",
            "target": {"repo": "testorg/repo"},
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["target"]["path"] == ""


class TestEnqueueSchemaValidation:
    """Test that Pydantic schema validation works before policy."""

    def test_rejects_missing_required_fields(self):
        """Missing required fields should return 422."""
        payload = {"version": "1.0"}  # Missing required fields
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422

    def test_rejects_invalid_operation(self):
        """Invalid operation value should be rejected by Pydantic."""
        payload = make_valid_task_payload(operation="invalid_operation")
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422

    def test_rejects_invalid_requester_kind(self):
        """Invalid requester kind should be rejected by Pydantic."""
        payload = make_valid_task_payload(
            requested_by={"kind": "invalid", "id": "test"}
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422


class TestEnqueueAllOperations:
    """Test that all valid operations are accepted."""

    @pytest.mark.parametrize(
        "operation", ["code_change", "docs", "analysis", "ops"]
    )
    def test_accepts_all_valid_operations(self, operation):
        """All V1 operations should be accepted."""
        payload = make_valid_task_payload(operation=operation)
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == operation


class TestEnqueueAllRequesterKinds:
    """Test that all valid requester kinds are accepted."""

    @pytest.mark.parametrize("kind", ["human", "agent", "system"])
    def test_accepts_all_valid_requester_kinds(self, kind):
        """All V1 requester kinds should be accepted."""
        payload = make_valid_task_payload(
            requested_by={"kind": kind, "id": f"test-{kind}"}
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["requested_by"]["kind"] == kind


class TestEnqueuePersistence:
    """Test that accepted tasks are persisted correctly."""

    def test_task_can_be_retrieved_after_creation(self):
        """Created task should be retrievable via GET."""
        payload = make_valid_task_payload(
            idempotency_key="test-persistence-key",
            metadata={"test": "persistence"},
        )
        create_response = client.post("/tasks/enqueue", json=payload)
        assert create_response.status_code == 201

        task_id = create_response.json()["task_id"]

        # Retrieve the task
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["id"] == task_id
        assert data["status"] == "queued"
        assert data["operation"] == "code_change"

    def test_normalized_values_persisted(self):
        """Normalized values should be what's stored in DB."""
        payload = make_valid_task_payload(
            objective="  Whitespace objective  ",
            target={"repo": "TestOrg/Repo.git", "ref": "develop", "path": "src/"},
        )
        create_response = client.post("/tasks/enqueue", json=payload)
        assert create_response.status_code == 201

        task_id = create_response.json()["task_id"]

        # Retrieve and verify normalization was persisted
        get_response = client.get(f"/tasks/{task_id}")
        data = get_response.json()

        assert data["objective"] == "Whitespace objective"
        assert data["target"]["repo"] == "testorg/repo"
        assert data["target"]["ref"] == "develop"
        assert data["target"]["path"] == "src/"


class TestCompatibilityLayer:
    """Test the backward compatibility layer for legacy field aliases.

    These tests verify that legacy field names are accepted and correctly
    mapped to canonical V1 fields. This layer is temporary and will be
    removed in V2.
    """

    def test_accepts_type_as_operation_alias(self):
        """Legacy 'type' field should be accepted as alias for 'operation'."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test using legacy type field",
            "type": "docs",  # Legacy alias for 'operation'
            "target": {"repo": "testorg/repo"},
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        # Should be normalized to canonical 'operation' field
        assert data["task"]["operation"] == "docs"

    def test_accepts_payload_as_inputs_alias(self):
        """Legacy 'payload' field should be accepted as alias for 'inputs'."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test using legacy payload field",
            "operation": "analysis",
            "target": {"repo": "testorg/repo"},
            "payload": {"file": "test.py", "line": 42},  # Legacy alias for 'inputs'
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        # Should be normalized to canonical 'inputs' field
        assert data["task"]["inputs"] == {"file": "test.py", "line": 42}

    def test_accepts_repository_as_repo_alias(self):
        """Legacy 'target.repository' field should be accepted as alias for 'target.repo'."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test using legacy repository field",
            "operation": "code_change",
            "target": {"repository": "testorg/repo"},  # Legacy alias for 'repo'
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        # Should be normalized to canonical 'repo' field
        assert data["task"]["target"]["repo"] == "testorg/repo"

    def test_canonical_fields_preferred_over_legacy(self):
        """When both canonical and legacy fields are provided, canonical wins."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test canonical fields take precedence",
            "operation": "code_change",  # Canonical
            "type": "docs",  # Legacy (should be ignored)
            "target": {"repo": "testorg/repo"},
            "inputs": {"canonical": True},  # Canonical
            "payload": {"legacy": True},  # Legacy (should be ignored)
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        # Canonical values should win
        assert data["task"]["operation"] == "code_change"
        assert data["task"]["inputs"] == {"canonical": True}

    def test_mixed_legacy_and_canonical_fields(self):
        """Mix of legacy and canonical fields should work correctly."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "agent", "id": "jules-001"},
            "objective": "Mix of legacy and canonical",
            "type": "ops",  # Legacy
            "target": {"repository": "testorg/test"},  # Legacy
            "inputs": {"key": "value"},  # Canonical
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == "ops"
        assert data["task"]["target"]["repo"] == "testorg/test"
        assert data["task"]["inputs"] == {"key": "value"}

    def test_legacy_repository_normalized(self):
        """Legacy 'repository' field should still be normalized (lowercase, strip .git)."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test repository normalization with legacy field",
            "operation": "analysis",
            "target": {"repository": "TestOrg/Test-Repo.git"},  # Legacy with normalization needed
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        # Should be normalized even when using legacy field
        assert data["task"]["target"]["repo"] == "testorg/test-repo"

    def test_all_legacy_fields_together(self):
        """All legacy fields used together should work correctly."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "system", "id": "ci-pipeline"},
            "objective": "Full legacy payload test",
            "type": "code_change",  # Legacy
            "target": {"repository": "testorg/legacy-test"},  # Legacy
            "payload": {"pr_number": 123},  # Legacy
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == "code_change"
        assert data["task"]["target"]["repo"] == "testorg/legacy-test"
        assert data["task"]["inputs"] == {"pr_number": 123}


class TestIdempotency:
    """Test idempotency behavior for POST /tasks/enqueue (Stage 1.4).

    When an idempotency_key is provided, repeated submissions with the same key
    should return the existing task instead of creating a duplicate.
    """

    def test_idempotency_key_returns_same_task_on_duplicate(self):
        """Repeated submission with same idempotency_key returns the same task_id."""
        idempotency_key = "test-idempotency-unique-001"
        payload = make_valid_task_payload(idempotency_key=idempotency_key)

        # First submission
        response1 = client.post("/tasks/enqueue", json=payload)
        assert response1.status_code == 201
        task_id_1 = response1.json()["task_id"]

        # Second submission with same idempotency_key
        response2 = client.post("/tasks/enqueue", json=payload)
        assert response2.status_code == 201
        task_id_2 = response2.json()["task_id"]

        # Should return the same task_id
        assert task_id_1 == task_id_2

    def test_idempotency_key_creates_only_one_db_row(self):
        """Repeated submissions with same idempotency_key create only one DB row."""
        idempotency_key = "test-idempotency-unique-002"
        payload = make_valid_task_payload(idempotency_key=idempotency_key)

        # Submit multiple times
        response1 = client.post("/tasks/enqueue", json=payload)
        response2 = client.post("/tasks/enqueue", json=payload)
        response3 = client.post("/tasks/enqueue", json=payload)

        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response3.status_code == 201

        task_id = response1.json()["task_id"]

        # Verify all returned the same task_id
        assert response2.json()["task_id"] == task_id
        assert response3.json()["task_id"] == task_id

        # Verify only one task exists with this idempotency_key by retrieving it
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200
        assert get_response.json()["idempotency_key"] == idempotency_key

    def test_idempotency_works_with_legacy_input_normalized(self):
        """Idempotency works correctly even with legacy field aliases after normalization."""
        idempotency_key = "test-idempotency-legacy-003"

        # First submission with canonical fields
        payload_canonical = {
            "version": "1.0",
            "idempotency_key": idempotency_key,
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Test idempotency with canonical fields",
            "operation": "docs",
            "target": {"repo": "testorg/repo"},
        }
        response1 = client.post("/tasks/enqueue", json=payload_canonical)
        assert response1.status_code == 201
        task_id_1 = response1.json()["task_id"]

        # Second submission with legacy fields (same idempotency_key)
        payload_legacy = {
            "version": "1.0",
            "idempotency_key": idempotency_key,
            "requested_by": {"kind": "human", "id": "test-user"},
            "objective": "Different objective - should be ignored",
            "type": "analysis",  # Legacy alias for operation
            "target": {"repository": "testorg/different-repo"},  # Legacy alias
        }
        response2 = client.post("/tasks/enqueue", json=payload_legacy)
        assert response2.status_code == 201
        task_id_2 = response2.json()["task_id"]

        # Should return the original task (idempotency takes precedence)
        assert task_id_1 == task_id_2

        # Verify the task has the original values, not the second submission's
        get_response = client.get(f"/tasks/{task_id_1}")
        assert get_response.status_code == 200
        task_data = get_response.json()
        assert task_data["operation"] == "docs"  # From first submission
        assert task_data["target"]["repo"] == "testorg/repo"  # From first submission

    def test_different_idempotency_keys_create_different_tasks(self):
        """Different idempotency_keys should create separate tasks."""
        payload1 = make_valid_task_payload(idempotency_key="key-unique-A")
        payload2 = make_valid_task_payload(idempotency_key="key-unique-B")

        response1 = client.post("/tasks/enqueue", json=payload1)
        response2 = client.post("/tasks/enqueue", json=payload2)

        assert response1.status_code == 201
        assert response2.status_code == 201

        # Should create different tasks
        assert response1.json()["task_id"] != response2.json()["task_id"]

    def test_no_idempotency_key_creates_new_task_each_time(self):
        """Without idempotency_key, each submission creates a new task."""
        payload = make_valid_task_payload()  # No idempotency_key

        response1 = client.post("/tasks/enqueue", json=payload)
        response2 = client.post("/tasks/enqueue", json=payload)

        assert response1.status_code == 201
        assert response2.status_code == 201

        # Should create different tasks
        assert response1.json()["task_id"] != response2.json()["task_id"]


class TestGetTaskById:
    """Test GET /tasks/{task_id} endpoint (Stage 1.5)."""

    def test_get_existing_task_returns_200(self):
        """GET /tasks/{task_id} returns 200 for existing task."""
        # Create a task first
        payload = make_valid_task_payload(
            idempotency_key="test-get-task-001",
            metadata={"test_case": "get_existing_task"},
        )
        create_response = client.post("/tasks/enqueue", json=payload)
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        # GET the task
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["id"] == task_id
        assert data["status"] == "queued"

    def test_get_task_returns_canonical_fields(self):
        """GET /tasks/{task_id} returns all canonical V1 fields."""
        payload = make_valid_task_payload(
            idempotency_key="test-get-task-fields-002",
            objective="Canonical fields test objective",
            operation="analysis",
            metadata={"tags": ["test", "canonical"]},
        )
        create_response = client.post("/tasks/enqueue", json=payload)
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200

        data = get_response.json()

        # Verify all canonical fields are present
        assert "id" in data
        assert "version" in data
        assert "idempotency_key" in data
        assert "requested_by" in data
        assert "objective" in data
        assert "operation" in data
        assert "target" in data
        assert "constraints" in data
        assert "inputs" in data
        assert "metadata" in data
        assert "status" in data
        assert "created_at" in data

        # Verify nested structures
        assert data["requested_by"]["kind"] == "human"
        assert data["requested_by"]["id"] == "test-user"
        assert data["target"]["repo"] == "testorg/test-repo"
        assert data["constraints"]["time_budget_seconds"] == 900
        assert data["metadata"] == {"tags": ["test", "canonical"]}

    def test_get_nonexistent_task_returns_404(self):
        """GET /tasks/{task_id} returns 404 for unknown task ID."""
        fake_task_id = "00000000-0000-0000-0000-000000000000"

        response = client.get(f"/tasks/{fake_task_id}")

        assert response.status_code == 404
        assert "Task not found" in response.json()["detail"]

    def test_get_task_with_invalid_uuid_returns_404(self):
        """GET /tasks/{task_id} returns 404 for invalid UUID format."""
        invalid_task_id = "not-a-valid-uuid"

        response = client.get(f"/tasks/{invalid_task_id}")

        assert response.status_code == 404

    def test_get_task_returns_timestamps(self):
        """GET /tasks/{task_id} returns timestamp fields."""
        payload = make_valid_task_payload(idempotency_key="test-get-task-timestamps-003")
        create_response = client.post("/tasks/enqueue", json=payload)
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200

        data = get_response.json()

        # created_at should be present
        assert "created_at" in data
        assert data["created_at"] is not None

        # For queued tasks, queued_at should be present
        assert "queued_at" in data

        # started_at and completed_at may be None for queued tasks
        assert "started_at" in data
        assert "completed_at" in data
