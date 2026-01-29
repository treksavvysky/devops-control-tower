"""
Sprint-0 Acceptance Criteria Tests.

These tests verify the end-to-end trace_id propagation:
1. POST /tasks/enqueue returns a trace_id
2. DB contains a tasks row with that trace_id
3. Worker processes task and logs with same trace_id
4. Worker creates artifact row with same trace_id
5. /healthz responds 200 with db: true
6. Can query by trace_id to reconstruct timeline
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from devops_control_tower.api import app
from devops_control_tower.db.base import Base, get_db
from devops_control_tower.db.models import ArtifactModel, JobModel, TaskModel
from devops_control_tower.db.services import ArtifactService, JobService, TaskService
from devops_control_tower.worker import Worker, StubActionRunner


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_sprint0.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Get a test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(test_db):
    """Get a test client."""
    return TestClient(app)


@pytest.fixture
def valid_task_spec():
    """Valid task specification for testing."""
    return {
        "version": "1.0",
        "requested_by": {
            "kind": "human",
            "id": "test-user",
            "label": "Test User",
        },
        "objective": "Test Sprint-0 trace_id propagation",
        "operation": "analysis",
        "target": {
            "repo": "test-org/test-repo",
            "ref": "main",
            "path": "",
        },
        "constraints": {
            "time_budget_seconds": 300,
            "allow_network": False,
            "allow_secrets": False,
        },
        "inputs": {"test_key": "test_value"},
        "metadata": {"sprint": "0"},
    }


class TestHealthEndpoint:
    """Test /healthz endpoint (Sprint-0 acceptance criteria #5)."""

    def test_healthz_returns_200(self, client):
        """Verify /healthz responds with 200."""
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_healthz_includes_db_status(self, client):
        """Verify /healthz includes database connectivity check."""
        response = client.get("/healthz")
        data = response.json()

        assert "ok" in data
        assert "db" in data
        # With test DB, both should be True
        assert data["db"] is True
        assert data["ok"] is True


class TestEnqueueWithTraceId:
    """Test POST /tasks/enqueue with trace_id (Sprint-0 acceptance criteria #1, #2)."""

    @patch("devops_control_tower.api.evaluate_policy")
    def test_enqueue_returns_trace_id(self, mock_policy, client, valid_task_spec, db_session):
        """Verify POST /tasks/enqueue returns a trace_id."""
        # Mock policy to return the task as-is (normalized)
        from devops_control_tower.schemas.task_v1 import TaskCreateLegacyV1
        mock_policy.return_value = TaskCreateLegacyV1(**valid_task_spec)

        response = client.post("/tasks/enqueue", json=valid_task_spec)
        assert response.status_code == 201

        data = response.json()
        assert "trace_id" in data
        assert data["trace_id"] is not None
        # trace_id should be a valid UUID format
        uuid.UUID(data["trace_id"])

    @patch("devops_control_tower.api.evaluate_policy")
    def test_enqueue_accepts_custom_trace_id(self, mock_policy, client, valid_task_spec, db_session):
        """Verify caller-supplied X-Trace-Id header is used."""
        from devops_control_tower.schemas.task_v1 import TaskCreateLegacyV1
        mock_policy.return_value = TaskCreateLegacyV1(**valid_task_spec)

        custom_trace_id = str(uuid.uuid4())
        response = client.post(
            "/tasks/enqueue",
            json=valid_task_spec,
            headers={"X-Trace-Id": custom_trace_id},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["trace_id"] == custom_trace_id

    @patch("devops_control_tower.api.evaluate_policy")
    def test_enqueue_stores_trace_id_in_db(self, mock_policy, client, valid_task_spec, db_session):
        """Verify trace_id is stored in the tasks table."""
        from devops_control_tower.schemas.task_v1 import TaskCreateLegacyV1
        mock_policy.return_value = TaskCreateLegacyV1(**valid_task_spec)

        response = client.post("/tasks/enqueue", json=valid_task_spec)
        assert response.status_code == 201

        data = response.json()
        trace_id = data["trace_id"]
        task_id = data["task_id"]

        # Query the task from DB
        task_service = TaskService(db_session)
        task = task_service.get_task(task_id)

        assert task is not None
        assert task.trace_id == trace_id

    @patch("devops_control_tower.api.evaluate_policy")
    def test_task_includes_trace_id_in_response(self, mock_policy, client, valid_task_spec, db_session):
        """Verify task dict in response includes trace_id."""
        from devops_control_tower.schemas.task_v1 import TaskCreateLegacyV1
        mock_policy.return_value = TaskCreateLegacyV1(**valid_task_spec)

        response = client.post("/tasks/enqueue", json=valid_task_spec)
        assert response.status_code == 201

        data = response.json()
        assert "task" in data
        assert "trace_id" in data["task"]
        assert data["task"]["trace_id"] == data["trace_id"]


class TestWorkerTraceId:
    """Test worker trace_id propagation (Sprint-0 acceptance criteria #3, #4)."""

    def test_worker_processes_task_with_trace_id(self, db_session):
        """Verify worker processes task and maintains trace_id."""
        # Create a task with trace_id
        trace_id = str(uuid.uuid4())
        task = TaskModel(
            version="1.0",
            requested_by_kind="human",
            requested_by_id="test-user",
            requested_by_label="Test User",
            objective="Test worker processing",
            operation="analysis",
            target_repo="test-org/test-repo",
            target_ref="main",
            target_path="",
            time_budget_seconds=300,
            allow_network=False,
            allow_secrets=False,
            inputs={"key": "value"},
            task_metadata={},
            status="queued",
            trace_id=trace_id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        # Process the task with worker
        worker = Worker(worker_id="test-worker")
        result = worker.process_task(db_session, task)

        # Verify trace_id is in result
        assert result["trace_id"] == trace_id
        assert result["task_id"] == str(task.id)
        assert "job_id" in result

    def test_worker_creates_artifact_with_trace_id(self, db_session):
        """Verify worker creates artifact row with trace_id."""
        # Create a task with trace_id
        trace_id = str(uuid.uuid4())
        task = TaskModel(
            version="1.0",
            requested_by_kind="human",
            requested_by_id="test-user",
            requested_by_label="Test User",
            objective="Test artifact creation",
            operation="analysis",
            target_repo="test-org/test-repo",
            target_ref="main",
            target_path="",
            time_budget_seconds=300,
            allow_network=False,
            allow_secrets=False,
            inputs={},
            task_metadata={},
            status="queued",
            trace_id=trace_id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        # Process the task
        worker = Worker(worker_id="test-worker")
        result = worker.process_task(db_session, task)

        # Verify artifacts were created
        assert "artifacts" in result
        assert len(result["artifacts"]) > 0

        # Verify artifact has trace_id
        artifact_service = ArtifactService(db_session)
        artifacts = artifact_service.get_artifacts_by_trace_id(trace_id)

        assert len(artifacts) > 0
        for artifact in artifacts:
            assert artifact.trace_id == trace_id
            assert artifact.task_id == str(task.id)

    def test_worker_creates_job_with_trace_id(self, db_session):
        """Verify worker creates job row with trace_id."""
        # Create a task with trace_id
        trace_id = str(uuid.uuid4())
        task = TaskModel(
            version="1.0",
            requested_by_kind="human",
            requested_by_id="test-user",
            requested_by_label="Test User",
            objective="Test job creation",
            operation="analysis",
            target_repo="test-org/test-repo",
            target_ref="main",
            target_path="",
            time_budget_seconds=300,
            allow_network=False,
            allow_secrets=False,
            inputs={},
            task_metadata={},
            status="queued",
            trace_id=trace_id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        # Process the task
        worker = Worker(worker_id="test-worker")
        result = worker.process_task(db_session, task)

        # Verify job was created with trace_id
        job_service = JobService(db_session)
        jobs = job_service.get_jobs_by_trace_id(trace_id)

        assert len(jobs) == 1
        assert jobs[0].trace_id == trace_id
        assert jobs[0].task_id == str(task.id)


class TestTraceIdQuery:
    """Test querying by trace_id (Sprint-0 acceptance criteria #6)."""

    def test_can_query_task_by_trace_id(self, db_session):
        """Verify tasks can be queried by trace_id."""
        trace_id = str(uuid.uuid4())

        # Create task with trace_id
        task = TaskModel(
            version="1.0",
            requested_by_kind="human",
            requested_by_id="test-user",
            requested_by_label="Test User",
            objective="Test trace query",
            operation="analysis",
            target_repo="test-org/test-repo",
            target_ref="main",
            target_path="",
            time_budget_seconds=300,
            allow_network=False,
            allow_secrets=False,
            inputs={},
            task_metadata={},
            status="queued",
            trace_id=trace_id,
        )
        db_session.add(task)
        db_session.commit()

        # Query by trace_id
        task_service = TaskService(db_session)
        found_task = task_service.get_task_by_trace_id(trace_id)

        assert found_task is not None
        assert found_task.trace_id == trace_id

    def test_can_query_jobs_by_trace_id(self, db_session):
        """Verify jobs can be queried by trace_id."""
        trace_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        # Create job with trace_id
        job_service = JobService(db_session)
        job = job_service.create_job(task_id=task_id, trace_id=trace_id)

        # Query by trace_id
        jobs = job_service.get_jobs_by_trace_id(trace_id)

        assert len(jobs) == 1
        assert jobs[0].trace_id == trace_id

    def test_can_query_artifacts_by_trace_id(self, db_session):
        """Verify artifacts can be queried by trace_id."""
        trace_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        # Create artifacts with trace_id
        artifact_service = ArtifactService(db_session)
        artifact1 = artifact_service.create_artifact(
            task_id=task_id,
            trace_id=trace_id,
            kind="log",
            content="Log entry 1",
        )
        artifact2 = artifact_service.create_artifact(
            task_id=task_id,
            trace_id=trace_id,
            kind="log",
            content="Log entry 2",
        )

        # Query by trace_id
        artifacts = artifact_service.get_artifacts_by_trace_id(trace_id)

        assert len(artifacts) == 2
        for artifact in artifacts:
            assert artifact.trace_id == trace_id

    def test_timeline_reconstruction(self, db_session):
        """Verify full timeline can be reconstructed by trace_id."""
        trace_id = str(uuid.uuid4())

        # Create a task
        task = TaskModel(
            version="1.0",
            requested_by_kind="human",
            requested_by_id="test-user",
            requested_by_label="Test User",
            objective="Test timeline reconstruction",
            operation="analysis",
            target_repo="test-org/test-repo",
            target_ref="main",
            target_path="",
            time_budget_seconds=300,
            allow_network=False,
            allow_secrets=False,
            inputs={},
            task_metadata={},
            status="queued",
            trace_id=trace_id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        # Process with worker
        worker = Worker(worker_id="test-worker")
        worker.process_task(db_session, task)

        # Reconstruct timeline
        task_service = TaskService(db_session)
        job_service = JobService(db_session)
        artifact_service = ArtifactService(db_session)

        tasks = task_service.get_tasks_by_trace_id(trace_id)
        jobs = job_service.get_jobs_by_trace_id(trace_id)
        artifacts = artifact_service.get_artifacts_by_trace_id(trace_id)

        # Verify all components have same trace_id
        assert len(tasks) == 1
        assert len(jobs) == 1
        assert len(artifacts) >= 1

        assert tasks[0].trace_id == trace_id
        assert jobs[0].trace_id == trace_id
        for artifact in artifacts:
            assert artifact.trace_id == trace_id


class TestActionRunner:
    """Test ActionRunner trace_id propagation."""

    def test_stub_action_runner_includes_trace_id(self):
        """Verify StubActionRunner includes trace_id in results."""
        trace_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        runner = StubActionRunner(
            trace_id=trace_id,
            task_id=task_id,
            job_id=job_id,
        )

        result = runner.execute(
            action_name="test_action",
            inputs={"key": "value"},
            constraints={"time_budget_seconds": 300},
        )

        assert result.trace_id == trace_id
        assert result.success is True
        assert len(result.artifacts) > 0

        # Verify trace_id in artifact content
        log_artifact = result.artifacts[0]
        assert trace_id in log_artifact["content"]

    def test_action_runner_get_headers(self):
        """Verify ActionRunner provides correct headers for downstream calls."""
        trace_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        runner = StubActionRunner(
            trace_id=trace_id,
            task_id=task_id,
            job_id=job_id,
        )

        headers = runner.get_headers()

        assert headers["X-Trace-Id"] == trace_id
        assert headers["X-Task-Id"] == task_id
        assert headers["X-Job-Id"] == job_id
