"""API-level tests for the /tasks/enqueue endpoint with policy gate.

These tests verify the policy gate, normalization, and persistence behavior
for the task enqueue endpoint.

Database setup is handled by the shared fixtures in conftest.py.
"""

import pytest
from fastapi.testclient import TestClient

from devops_control_tower.api import app

# Use a module-level client - DB is configured in conftest.py
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

    def test_rejects_invalid_operation(self):
        """Tasks with invalid operation type should be rejected."""
        payload = make_valid_task_payload(operation="invalid_op")
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        # Pydantic validation error for invalid enum
        assert "detail" in data

    def test_rejects_disallowed_repo(self):
        """Tasks targeting disallowed repos should be rejected."""
        payload = make_valid_task_payload(
            target={"repo": "evil-org/hacker-repo", "ref": "main", "path": ""}
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["code"] == "REPO_NOT_ALLOWED"

    def test_rejects_time_budget_too_low(self):
        """Tasks with time budget below minimum should be rejected."""
        payload = make_valid_task_payload(
            constraints={
                "time_budget_seconds": 10,  # Below 30s minimum
                "allow_network": False,
                "allow_secrets": False,
            }
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        # Pydantic validation error for constraint violation
        assert "detail" in data

    def test_rejects_time_budget_too_high(self):
        """Tasks with time budget above maximum should be rejected."""
        payload = make_valid_task_payload(
            constraints={
                "time_budget_seconds": 100000,  # Above 86400s maximum
                "allow_network": False,
                "allow_secrets": False,
            }
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        # Pydantic validation error for constraint violation
        data = response.json()
        assert "detail" in data

    def test_rejects_network_access(self):
        """Tasks requesting network access should be rejected in V1."""
        payload = make_valid_task_payload(
            constraints={
                "time_budget_seconds": 300,
                "allow_network": True,  # Not allowed in V1
                "allow_secrets": False,
            }
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["code"] == "NETWORK_ACCESS_DENIED"

    def test_rejects_secrets_access(self):
        """Tasks requesting secrets access should be rejected in V1."""
        payload = make_valid_task_payload(
            constraints={
                "time_budget_seconds": 300,
                "allow_network": False,
                "allow_secrets": True,  # Not allowed in V1
            }
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["detail"]["code"] == "SECRETS_ACCESS_DENIED"


class TestEnqueueAcceptAndNormalize:
    """Test that valid tasks are accepted and normalized."""

    def test_accepts_valid_task(self):
        """A fully valid task should be accepted with 201."""
        payload = make_valid_task_payload(
            idempotency_key="test-valid-task-001",
            metadata={"test_case": "accepts_valid_task"},
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "task_id" in data

    def test_normalizes_repo_name(self):
        """Repo names should be normalized (lowercase, no .git suffix)."""
        payload = make_valid_task_payload(
            idempotency_key="test-normalize-repo-002",
            target={"repo": "TestOrg/MyRepo.git", "ref": "main", "path": ""},
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        # Check the normalized value
        assert data["task"]["target"]["repo"] == "testorg/myrepo"

    def test_normalizes_objective_whitespace(self):
        """Objective should have leading/trailing whitespace stripped."""
        payload = make_valid_task_payload(
            idempotency_key="test-normalize-objective-003",
            objective="  Whitespace around objective  ",
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["objective"] == "Whitespace around objective"

    def test_applies_default_constraints(self):
        """Missing constraints should get default values."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-default-constraints-004",
            "requested_by": {"kind": "agent", "id": "test-agent", "label": "Test"},
            "objective": "Test default constraints",
            "operation": "analysis",
            "target": {"repo": "testorg/test-repo", "ref": "main", "path": ""},
            # No constraints provided
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        task = data["task"]
        assert task["constraints"]["time_budget_seconds"] == 900  # default
        assert task["constraints"]["allow_network"] is False
        assert task["constraints"]["allow_secrets"] is False

    def test_applies_default_target_ref(self):
        """Missing target.ref should default to 'main'."""
        payload = make_valid_task_payload(
            idempotency_key="test-default-ref-005",
            target={"repo": "testorg/test-repo"},  # No ref
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["target"]["ref"] == "main"

    def test_applies_default_target_path(self):
        """Missing target.path should default to empty string."""
        payload = make_valid_task_payload(
            idempotency_key="test-default-path-006",
            target={"repo": "testorg/test-repo", "ref": "develop"},  # No path
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["target"]["path"] == ""


class TestEnqueueAllOperations:
    """Test that all valid operation types are accepted."""

    @pytest.mark.parametrize(
        "operation", ["code_change", "docs", "analysis", "ops"]
    )
    def test_accepts_all_valid_operations(self, operation):
        """All defined operation types should be accepted."""
        payload = make_valid_task_payload(
            idempotency_key=f"test-op-{operation}",
            operation=operation,
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == operation


class TestEnqueueAllRequesterKinds:
    """Test that all valid requester kinds are accepted."""

    @pytest.mark.parametrize("kind", ["human", "agent", "system"])
    def test_accepts_all_valid_requester_kinds(self, kind):
        """All defined requester kinds should be accepted."""
        payload = make_valid_task_payload(
            idempotency_key=f"test-requester-{kind}",
            requested_by={"kind": kind, "id": f"test-{kind}", "label": f"Test {kind}"},
        )
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["requested_by"]["kind"] == kind


class TestEnqueuePersistence:
    """Test that tasks are persisted to the database."""

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
        assert data["task_id"] == task_id
        assert data["status"] == "queued"
        assert data["operation"] == "code_change"

    def test_normalized_values_persisted(self):
        """Normalized values should be what's stored in DB."""
        payload = make_valid_task_payload(
            idempotency_key="test-persistence-normalized",
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
        """Legacy 'type' field should be accepted as 'operation'."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-compat-type",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Test legacy type field",
            "type": "analysis",  # Legacy field
            "target": {"repo": "testorg/test-repo", "ref": "main", "path": ""},
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == "analysis"

    def test_accepts_payload_as_inputs_alias(self):
        """Legacy 'payload' field should be accepted as 'inputs'."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-compat-payload",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Test legacy payload field",
            "operation": "code_change",
            "target": {"repo": "testorg/test-repo", "ref": "main", "path": ""},
            "payload": {"key": "value"},  # Legacy field
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["inputs"] == {"key": "value"}

    def test_accepts_repository_as_repo_alias(self):
        """Legacy 'target.repository' should be accepted as 'target.repo'."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-compat-repository",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Test legacy repository field",
            "operation": "code_change",
            "target": {
                "repository": "testorg/legacy-repo",  # Legacy field
                "ref": "main",
                "path": "",
            },
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["target"]["repo"] == "testorg/legacy-repo"

    def test_canonical_fields_preferred_over_legacy(self):
        """When both canonical and legacy fields present, canonical wins."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-compat-prefer-canonical",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Test canonical preferred",
            "operation": "analysis",  # Canonical
            "type": "docs",  # Legacy (should be ignored)
            "target": {"repo": "testorg/test-repo", "ref": "main", "path": ""},
            "inputs": {"canonical": True},  # Canonical
            "payload": {"legacy": True},  # Legacy (should be ignored)
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == "analysis"
        assert data["task"]["inputs"] == {"canonical": True}

    def test_mixed_legacy_and_canonical_fields(self):
        """A mix of legacy and canonical fields should work."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-compat-mixed",
            "requested_by": {"kind": "agent", "id": "bot", "label": "Bot"},
            "objective": "Test mixed fields",
            "type": "ops",  # Legacy operation
            "target": {
                "repository": "testorg/mixed-repo",  # Legacy repo
                "ref": "develop",
            },
            "inputs": {"new_style": True},  # Canonical inputs
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == "ops"
        assert data["task"]["target"]["repo"] == "testorg/mixed-repo"
        assert data["task"]["inputs"] == {"new_style": True}

    def test_legacy_repository_normalized(self):
        """Legacy repository field should also be normalized."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-compat-normalize-legacy",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Test legacy normalization",
            "operation": "code_change",
            "target": {
                "repository": "TestOrg/LegacyRepo.git",  # Should be normalized
            },
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["target"]["repo"] == "testorg/legacyrepo"

    def test_all_legacy_fields_together(self):
        """All legacy fields together should work."""
        payload = {
            "version": "1.0",
            "idempotency_key": "test-compat-all-legacy",
            "requested_by": {"kind": "system", "id": "ci", "label": "CI"},
            "objective": "All legacy fields test",
            "type": "docs",  # Legacy
            "target": {
                "repository": "testorg/all-legacy.git",  # Legacy
                "ref": "main",
            },
            "payload": {"all_legacy": True},  # Legacy
        }
        response = client.post("/tasks/enqueue", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["task"]["operation"] == "docs"
        assert data["task"]["target"]["repo"] == "testorg/all-legacy"
        assert data["task"]["inputs"] == {"all_legacy": True}


class TestIdempotency:
    """Test idempotency key behavior."""

    def test_idempotency_key_returns_same_task_on_duplicate(self):
        """Duplicate requests with same idempotency key return 409 with existing task."""
        payload = make_valid_task_payload(
            idempotency_key="test-idempotent-001",
            objective="Idempotency test",
        )

        # First request - creates the task
        response1 = client.post("/tasks/enqueue", json=payload)
        assert response1.status_code == 201
        task_id_1 = response1.json()["task_id"]

        # Second request with same idempotency key - returns 409 Conflict
        response2 = client.post("/tasks/enqueue", json=payload)
        assert response2.status_code == 409
        data = response2.json()
        assert data["status"] == "conflict"
        task_id_2 = data["task_id"]

        # Same task returned
        assert task_id_1 == task_id_2

    def test_idempotency_key_creates_only_one_db_row(self):
        """Multiple requests with same key should only create one DB row."""
        payload = make_valid_task_payload(
            idempotency_key="test-idempotent-single-row",
            objective="Single row test",
        )

        # First request creates the task
        response = client.post("/tasks/enqueue", json=payload)
        assert response.status_code == 201
        task_id = response.json()["task_id"]

        # Subsequent requests return 409 Conflict
        for _ in range(2):
            response = client.post("/tasks/enqueue", json=payload)
            assert response.status_code == 409
            assert response.json()["task_id"] == task_id

        # Task is retrievable
        get_response = client.get(f"/tasks/{task_id}")
        assert get_response.status_code == 200

    def test_idempotency_works_with_legacy_input_normalized(self):
        """Idempotency should work even with different input representations."""
        # First request with canonical fields
        payload1 = {
            "version": "1.0",
            "idempotency_key": "test-idempotent-normalize",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Test objective for idempotency",  # min 5 chars
            "operation": "analysis",
            "target": {"repo": "testorg/repo", "ref": "main", "path": ""},
        }
        response1 = client.post("/tasks/enqueue", json=payload1)
        assert response1.status_code == 201
        task_id_1 = response1.json()["task_id"]

        # Second request with same idempotency key but legacy fields
        # (the idempotency key match should take precedence - returns 409)
        payload2 = {
            "version": "1.0",
            "idempotency_key": "test-idempotent-normalize",  # Same key
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Different objective text",  # Different!
            "type": "docs",  # Legacy, different operation
            "target": {"repository": "testorg/other", "ref": "main", "path": ""},
        }
        response2 = client.post("/tasks/enqueue", json=payload2)
        assert response2.status_code == 409  # Conflict - idempotency hit
        task_id_2 = response2.json()["task_id"]

        # Same task returned due to idempotency key
        assert task_id_1 == task_id_2

    def test_different_idempotency_keys_create_different_tasks(self):
        """Different idempotency keys should create separate tasks."""
        base_payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "Same objective",
            "operation": "code_change",
            "target": {"repo": "testorg/test-repo", "ref": "main", "path": ""},
        }

        payload1 = {**base_payload, "idempotency_key": "key-different-1"}
        payload2 = {**base_payload, "idempotency_key": "key-different-2"}

        response1 = client.post("/tasks/enqueue", json=payload1)
        response2 = client.post("/tasks/enqueue", json=payload2)

        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["task_id"] != response2.json()["task_id"]

    def test_no_idempotency_key_creates_new_task_each_time(self):
        """Without idempotency key, each request creates a new task."""
        payload = {
            "version": "1.0",
            "requested_by": {"kind": "human", "id": "user", "label": "User"},
            "objective": "No idempotency key",
            "operation": "analysis",
            "target": {"repo": "testorg/test-repo", "ref": "main", "path": ""},
            # No idempotency_key
        }

        response1 = client.post("/tasks/enqueue", json=payload)
        response2 = client.post("/tasks/enqueue", json=payload)

        assert response1.status_code == 201
        assert response2.status_code == 201
        # Each request should create a new task
        assert response1.json()["task_id"] != response2.json()["task_id"]


class TestGetTaskById:
    """Test GET /tasks/{task_id} endpoint."""

    def test_get_existing_task_returns_200(self):
        """GET on existing task returns 200 with task data."""
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
        assert data["task_id"] == task_id
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
        assert "task_id" in data
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
        assert "kind" in data["requested_by"]
        assert "id" in data["requested_by"]
        assert "repo" in data["target"]
        assert "ref" in data["target"]
        assert "path" in data["target"]
        assert "time_budget_seconds" in data["constraints"]

    def test_get_nonexistent_task_returns_404(self):
        """GET on non-existent task returns 404."""
        response = client.get("/tasks/nonexistent-id-12345")
        assert response.status_code == 404

    def test_get_task_returns_timestamps(self):
        """GET returns timestamp fields in ISO format."""
        payload = make_valid_task_payload(
            idempotency_key="test-get-task-timestamps",
        )
        create_response = client.post("/tasks/enqueue", json=payload)
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        get_response = client.get(f"/tasks/{task_id}")
        data = get_response.json()

        # created_at should be present and look like ISO format
        assert data["created_at"] is not None
        assert "T" in data["created_at"]  # ISO format contains T separator

        # queued_at should also be present
        assert data["queued_at"] is not None
