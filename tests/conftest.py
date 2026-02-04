"""Test configuration and shared fixtures.

This module provides shared database fixtures for all tests to avoid
conflicts from multiple modules overriding app.dependency_overrides.
"""

import asyncio
import os
from typing import Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables BEFORE importing application code
os.environ.setdefault("JCT_ALLOWED_REPO_PREFIXES", "testorg/")

from devops_control_tower.core.orchestrator import Orchestrator
from devops_control_tower.data.models.events import Event, EventPriority, EventTypes
from devops_control_tower.db import base as db_base
from devops_control_tower.db.base import Base, get_db


# =============================================================================
# Shared Test Database Setup
# =============================================================================

# Create a single shared in-memory SQLite database for all tests
# Using StaticPool to ensure the same connection is reused (required for in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    """Override the get_db dependency for testing."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Patch SessionLocal in db/base.py so the orchestrator uses the test database
# This is needed because the orchestrator creates its own session via SessionLocal()
# instead of using the dependency-injected session from get_db()
db_base.SessionLocal = TestSessionLocal

# Import app AFTER patching SessionLocal to ensure the orchestrator uses test DB
from devops_control_tower.api import app  # noqa: E402

# Override the dependency for routes that use Depends(get_db)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables once at the start of the test session.

    This runs automatically before any tests and tears down after all tests.
    """
    # Import all models to ensure they're registered with Base.metadata
    from devops_control_tower.db import models  # noqa: F401
    from devops_control_tower.db import cwom_models  # noqa: F401
    from devops_control_tower.db import audit_models  # noqa: F401

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    yield

    # Drop all tables after all tests complete
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(setup_test_database) -> Generator[Session, None, None]:
    """Provide a database session for a single test.

    Each test gets a fresh session. Changes are rolled back after each test
    to maintain isolation.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(setup_test_database) -> Generator[TestClient, None, None]:
    """Provide a test client for API tests.

    The client uses the shared test database via dependency override.
    """
    with TestClient(app) as c:
        yield c


# =============================================================================
# Orchestrator Fixtures
# =============================================================================

@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def orchestrator() -> Orchestrator:
    """Create a test orchestrator instance."""
    orch = Orchestrator()
    yield orch
    if orch.is_running:
        await orch.stop()


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    return Event(
        event_type=EventTypes.SYSTEM_STARTUP,
        source="test",
        data={"message": "test event"},
        priority=EventPriority.MEDIUM,
    )


@pytest.fixture
def valid_task_payload() -> dict:
    """Create a valid task payload for API tests."""
    return {
        "version": "1.0",
        "requested_by": {
            "kind": "human",
            "id": "test-user",
            "label": "Test User",
        },
        "objective": "Test objective",
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
