"""Test configuration and fixtures."""

import pytest
import pytest_asyncio
import asyncio
from typing import Generator

from devops_control_tower.core.orchestrator import Orchestrator
from devops_control_tower.data.models.events import Event, EventTypes, EventPriority


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


@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    return Event(
        event_type=EventTypes.SYSTEM_STARTUP,
        source="test",
        data={"message": "test event"},
        priority=EventPriority.MEDIUM
    )
