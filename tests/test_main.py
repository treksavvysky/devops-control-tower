from __future__ import annotations

from fastapi.testclient import TestClient

from devops_control_tower.main import app

client = TestClient(app)


def test_healthz():
    """Test the /healthz endpoint (Sprint-0: includes DB check)."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    # Sprint-0 format: {"ok": bool, "db": bool}
    assert "ok" in data
    assert "db" in data


def test_version():
    """Test the /version endpoint."""
    response = client.get("/version")
    assert response.status_code == 200
    # The version is read from pyproject.toml, so we can't know the exact value
    # but we can check that it's a string.
    assert "version" in response.json()
    assert isinstance(response.json()["version"], str)
