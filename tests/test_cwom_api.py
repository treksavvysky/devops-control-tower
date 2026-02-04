"""
Tests for CWOM v0.1 API endpoints.

Tests verify:
1. CRUD operations for all 7 CWOM object types
2. Referential integrity validation
3. Immutability constraints for ContextPacket and ConstraintSnapshot
4. Query filtering and pagination

Database setup is handled by the shared fixtures in conftest.py.
"""

import pytest
from fastapi.testclient import TestClient

from devops_control_tower.api import app

# Use a module-level client - DB is configured in conftest.py
client = TestClient(app)


class TestRepoEndpoints:
    """Tests for /cwom/repos endpoints."""

    def test_create_repo(self):
        """Test creating a new Repo."""
        response = client.post(
            "/cwom/repos",
            json={
                "name": "Test Repo",
                "slug": "test-repo",
                "source": {
                    "system": "github",
                    "external_id": "myorg/test-repo",
                    "url": "https://github.com/myorg/test-repo",
                },
                "default_branch": "main",
                "visibility": "private",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["repo"]["name"] == "Test Repo"
        assert data["repo"]["slug"] == "test-repo"
        assert data["repo"]["kind"] == "Repo"
        assert "id" in data["repo"]

    def test_create_repo_duplicate_slug(self):
        """Test that duplicate slug is rejected."""
        repo_data = {
            "name": "Test Repo",
            "slug": "duplicate-slug",
            "source": {"system": "github", "external_id": "myorg/test"},
        }

        # Create first repo
        response = client.post("/cwom/repos", json=repo_data)
        assert response.status_code == 201

        # Try to create with same slug
        response = client.post("/cwom/repos", json=repo_data)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_get_repo(self):
        """Test getting a Repo by ID."""
        # Create repo first
        create_response = client.post(
            "/cwom/repos",
            json={
                "name": "Get Test",
                "slug": "get-test",
                "source": {"system": "github", "external_id": "org/get-test"},
            },
        )
        repo_id = create_response.json()["repo"]["id"]

        # Get the repo
        response = client.get(f"/cwom/repos/{repo_id}")
        assert response.status_code == 200
        assert response.json()["id"] == repo_id

    def test_get_repo_not_found(self):
        """Test 404 for non-existent Repo."""
        response = client.get("/cwom/repos/nonexistent-id")
        assert response.status_code == 404

    def test_list_repos(self):
        """Test listing Repos."""
        # Create some repos
        for i in range(3):
            client.post(
                "/cwom/repos",
                json={
                    "name": f"List Test {i}",
                    "slug": f"list-test-{i}",
                    "source": {"system": "github", "external_id": f"org/list-{i}"},
                },
            )

        response = client.get("/cwom/repos")
        assert response.status_code == 200
        assert len(response.json()) >= 3


class TestIssueEndpoints:
    """Tests for /cwom/issues endpoints."""

    @pytest.fixture
    def repo_id(self):
        """Create a repo for issue tests."""
        response = client.post(
            "/cwom/repos",
            json={
                "name": "Issue Test Repo",
                "slug": f"issue-test-repo-{id(self)}",
                "source": {"system": "github", "external_id": "org/issue-test"},
            },
        )
        return response.json()["repo"]["id"]

    def test_create_issue(self, repo_id):
        """Test creating a new Issue."""
        response = client.post(
            "/cwom/issues",
            json={
                "repo": {"kind": "Repo", "id": repo_id},
                "title": "Add /healthz endpoint",
                "description": "We need a health check endpoint",
                "type": "feature",
                "priority": "P2",
                "status": "planned",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["issue"]["title"] == "Add /healthz endpoint"
        assert data["issue"]["kind"] == "Issue"

    def test_create_issue_invalid_repo(self):
        """Test that issue with invalid repo is rejected."""
        response = client.post(
            "/cwom/issues",
            json={
                "repo": {"kind": "Repo", "id": "nonexistent-repo"},
                "title": "Test Issue",
                "type": "feature",
            },
        )
        assert response.status_code == 422
        assert "does not exist" in response.json()["detail"]

    def test_get_issue(self, repo_id):
        """Test getting an Issue by ID."""
        # Create issue
        create_response = client.post(
            "/cwom/issues",
            json={
                "repo": {"kind": "Repo", "id": repo_id},
                "title": "Get Test Issue",
                "type": "bug",
            },
        )
        issue_id = create_response.json()["issue"]["id"]

        # Get the issue
        response = client.get(f"/cwom/issues/{issue_id}")
        assert response.status_code == 200
        assert response.json()["id"] == issue_id

    def test_update_issue_status(self, repo_id):
        """Test updating Issue status."""
        # Create issue
        create_response = client.post(
            "/cwom/issues",
            json={
                "repo": {"kind": "Repo", "id": repo_id},
                "title": "Status Test Issue",
                "type": "chore",
                "status": "planned",
            },
        )
        issue_id = create_response.json()["issue"]["id"]

        # Update status
        response = client.patch(
            f"/cwom/issues/{issue_id}/status",
            params={"status": "running"},
        )
        assert response.status_code == 200
        assert response.json()["issue"]["status"] == "running"


class TestContextPacketEndpoints:
    """Tests for /cwom/context-packets endpoints."""

    @pytest.fixture
    def issue_id(self):
        """Create a repo and issue for context packet tests."""
        # Create repo
        repo_response = client.post(
            "/cwom/repos",
            json={
                "name": "CP Test Repo",
                "slug": f"cp-test-repo-{id(self)}",
                "source": {"system": "github", "external_id": "org/cp-test"},
            },
        )
        repo_id = repo_response.json()["repo"]["id"]

        # Create issue
        issue_response = client.post(
            "/cwom/issues",
            json={
                "repo": {"kind": "Repo", "id": repo_id},
                "title": "CP Test Issue",
                "type": "feature",
            },
        )
        return issue_response.json()["issue"]["id"]

    def test_create_context_packet(self, issue_id):
        """Test creating a ContextPacket."""
        response = client.post(
            "/cwom/context-packets",
            json={
                "for_issue": {"kind": "Issue", "id": issue_id},
                "version": "1.0",
                "summary": "Initial context for implementation",
                "assumptions": ["API is REST-based", "Uses existing auth"],
                "instructions": "Follow existing patterns in the codebase",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["context_packet"]["version"] == "1.0"
        assert data["context_packet"]["kind"] == "ContextPacket"

    def test_context_packet_immutability_patch(self, issue_id):
        """Test that ContextPackets cannot be modified via PATCH."""
        # Create context packet
        create_response = client.post(
            "/cwom/context-packets",
            json={
                "for_issue": {"kind": "Issue", "id": issue_id},
                "version": "1.0",
                "summary": "Immutable test",
            },
        )
        packet_id = create_response.json()["context_packet"]["id"]

        # Try to update - should be blocked
        response = client.patch(f"/cwom/context-packets/{packet_id}")
        assert response.status_code == 405
        assert response.json()["detail"]["error"] == "IMMUTABILITY_VIOLATION"

    def test_context_packet_immutability_put(self, issue_id):
        """Test that ContextPackets cannot be modified via PUT."""
        # Create context packet
        create_response = client.post(
            "/cwom/context-packets",
            json={
                "for_issue": {"kind": "Issue", "id": issue_id},
                "version": "1.1",
                "summary": "Immutable test put",
            },
        )
        packet_id = create_response.json()["context_packet"]["id"]

        response = client.put(f"/cwom/context-packets/{packet_id}")
        assert response.status_code == 405

    def test_list_context_packets_for_issue(self, issue_id):
        """Test listing ContextPackets for an Issue."""
        # Create multiple versions
        for version in ["2.0", "2.1", "2.2"]:
            client.post(
                "/cwom/context-packets",
                json={
                    "for_issue": {"kind": "Issue", "id": issue_id},
                    "version": version,
                    "summary": f"Version {version}",
                },
            )

        response = client.get(f"/cwom/issues/{issue_id}/context-packets")
        assert response.status_code == 200
        assert len(response.json()) >= 3


class TestConstraintSnapshotEndpoints:
    """Tests for /cwom/constraint-snapshots endpoints."""

    def test_create_constraint_snapshot(self):
        """Test creating a ConstraintSnapshot."""
        response = client.post(
            "/cwom/constraint-snapshots",
            json={
                "scope": "personal",
                "owner": {
                    "actor_kind": "human",
                    "actor_id": "user-123",
                    "display": "Test User",
                },
                "constraints": {
                    "time": {"available_minutes": 60},
                    "energy": {"score_0_5": 4},
                    "risk": {"tolerance": "medium"},
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["constraint_snapshot"]["scope"] == "personal"
        assert data["constraint_snapshot"]["kind"] == "ConstraintSnapshot"

    def test_constraint_snapshot_immutability(self):
        """Test that ConstraintSnapshots cannot be modified."""
        # Create snapshot
        create_response = client.post(
            "/cwom/constraint-snapshots",
            json={
                "scope": "run",
                "owner": {"actor_kind": "agent", "actor_id": "claude"},
            },
        )
        snapshot_id = create_response.json()["constraint_snapshot"]["id"]

        # Try to update - should be blocked
        response = client.patch(f"/cwom/constraint-snapshots/{snapshot_id}")
        assert response.status_code == 405
        assert response.json()["detail"]["error"] == "IMMUTABILITY_VIOLATION"


class TestDoctrineRefEndpoints:
    """Tests for /cwom/doctrine-refs endpoints."""

    def test_create_doctrine_ref(self):
        """Test creating a DoctrineRef."""
        response = client.post(
            "/cwom/doctrine-refs",
            json={
                "namespace": "org/security",
                "name": "no-secrets-in-logs",
                "version": "1.0",
                "type": "policy",
                "priority": "must",
                "statement": "Never log secrets or credentials",
                "rationale": "Prevent credential leakage in log files",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["doctrine_ref"]["namespace"] == "org/security"
        assert data["doctrine_ref"]["kind"] == "DoctrineRef"

    def test_create_duplicate_doctrine_ref(self):
        """Test that duplicate namespace/name/version is rejected."""
        doctrine_data = {
            "namespace": "org/testing",
            "name": "duplicate-test",
            "version": "1.0",
            "type": "principle",
            "priority": "should",
            "statement": "Test statement",
        }

        # Create first
        response = client.post("/cwom/doctrine-refs", json=doctrine_data)
        assert response.status_code == 201

        # Try duplicate
        response = client.post("/cwom/doctrine-refs", json=doctrine_data)
        assert response.status_code == 409


class TestRunEndpoints:
    """Tests for /cwom/runs endpoints."""

    @pytest.fixture
    def issue_and_repo(self):
        """Create repo and issue for run tests."""
        # Create repo
        repo_response = client.post(
            "/cwom/repos",
            json={
                "name": "Run Test Repo",
                "slug": f"run-test-repo-{id(self)}",
                "source": {"system": "github", "external_id": "org/run-test"},
            },
        )
        repo_id = repo_response.json()["repo"]["id"]

        # Create issue
        issue_response = client.post(
            "/cwom/issues",
            json={
                "repo": {"kind": "Repo", "id": repo_id},
                "title": "Run Test Issue",
                "type": "feature",
            },
        )
        issue_id = issue_response.json()["issue"]["id"]

        return {"repo_id": repo_id, "issue_id": issue_id}

    def test_create_run(self, issue_and_repo):
        """Test creating a Run."""
        response = client.post(
            "/cwom/runs",
            json={
                "for_issue": {"kind": "Issue", "id": issue_and_repo["issue_id"]},
                "repo": {"kind": "Repo", "id": issue_and_repo["repo_id"]},
                "mode": "agent",
                "executor": {
                    "actor": {"actor_kind": "agent", "actor_id": "claude"},
                    "runtime": "container",
                    "toolchain": ["python", "git"],
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["run"]["mode"] == "agent"
        assert data["run"]["kind"] == "Run"

    def test_update_run(self, issue_and_repo):
        """Test updating a Run."""
        # Create run (starts as "planned" by default)
        create_response = client.post(
            "/cwom/runs",
            json={
                "for_issue": {"kind": "Issue", "id": issue_and_repo["issue_id"]},
                "repo": {"kind": "Repo", "id": issue_and_repo["repo_id"]},
                "mode": "agent",
                "executor": {
                    "actor": {"actor_kind": "agent", "actor_id": "claude"},
                    "runtime": "local",
                },
            },
        )
        run_id = create_response.json()["run"]["id"]

        # Update run
        response = client.patch(
            f"/cwom/runs/{run_id}",
            json={
                "status": "running",
                "telemetry": {"started_at": "2025-01-26T10:00:00Z"},
            },
        )
        assert response.status_code == 200
        assert response.json()["run"]["status"] == "running"


class TestArtifactEndpoints:
    """Tests for /cwom/artifacts endpoints."""

    @pytest.fixture
    def run_id(self):
        """Create repo, issue, and run for artifact tests."""
        # Create repo
        repo_response = client.post(
            "/cwom/repos",
            json={
                "name": "Artifact Test Repo",
                "slug": f"artifact-test-repo-{id(self)}",
                "source": {"system": "github", "external_id": "org/artifact-test"},
            },
        )
        repo_id = repo_response.json()["repo"]["id"]

        # Create issue
        issue_response = client.post(
            "/cwom/issues",
            json={
                "repo": {"kind": "Repo", "id": repo_id},
                "title": "Artifact Test Issue",
                "type": "feature",
            },
        )
        issue_id = issue_response.json()["issue"]["id"]

        # Create run
        run_response = client.post(
            "/cwom/runs",
            json={
                "for_issue": {"kind": "Issue", "id": issue_id},
                "repo": {"kind": "Repo", "id": repo_id},
                "mode": "agent",
                "executor": {
                    "actor": {"actor_kind": "agent", "actor_id": "claude"},
                    "runtime": "local",
                },
            },
        )
        return {
            "run_id": run_response.json()["run"]["id"],
            "issue_id": issue_id,
        }

    def test_create_artifact(self, run_id):
        """Test creating an Artifact."""
        response = client.post(
            "/cwom/artifacts",
            json={
                "produced_by": {"kind": "Run", "id": run_id["run_id"]},
                "for_issue": {"kind": "Issue", "id": run_id["issue_id"]},
                "type": "pr",
                "title": "Add /healthz endpoint",
                "uri": "https://github.com/org/repo/pull/123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["artifact"]["type"] == "pr"
        assert data["artifact"]["kind"] == "Artifact"

    def test_list_artifacts_for_run(self, run_id):
        """Test listing Artifacts for a Run."""
        # Create multiple artifacts
        for i in range(3):
            client.post(
                "/cwom/artifacts",
                json={
                    "produced_by": {"kind": "Run", "id": run_id["run_id"]},
                    "for_issue": {"kind": "Issue", "id": run_id["issue_id"]},
                    "type": "commit",
                    "title": f"Commit {i}",
                    "uri": f"https://github.com/org/repo/commit/{i}",
                },
            )

        response = client.get(f"/cwom/runs/{run_id['run_id']}/artifacts")
        assert response.status_code == 200
        assert len(response.json()) >= 3
