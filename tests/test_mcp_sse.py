import pytest
from fastapi.testclient import TestClient
from devops_control_tower.api import app
from devops_control_tower.config import get_settings

def test_mcp_sse_auth_failures(client):
    """Test that unauthorized requests to /mcp/ endpoints return 401."""
    settings = get_settings()
    old_key = settings.jct_api_key
    settings.jct_api_key = "test-secret-token"
    try:
        # 1. GET /mcp/sse without credentials -> 401
        response = client.get("/mcp/sse")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid or missing API key"}

        # 2. GET /mcp/sse with invalid credentials -> 401
        response = client.get("/mcp/sse", headers={"Authorization": "Bearer wrong-token"})
        assert response.status_code == 401

        # 3. POST /mcp/messages without credentials -> 401
        response = client.post("/mcp/messages")
        assert response.status_code == 401
    finally:
        settings.jct_api_key = old_key

def test_mcp_sse_auth_success(client):
    """Test that authorized requests to /mcp/ endpoints are not blocked by auth."""
    settings = get_settings()
    old_key = settings.jct_api_key
    settings.jct_api_key = "test-secret-token"
    try:
        # POST with correct credentials should pass the auth middleware (returning 400 or 404 from MCP handler, but NOT 401)
        response = client.post("/mcp/messages", headers={"Authorization": "Bearer test-secret-token"})
        assert response.status_code != 401

        # POST with correct credentials in query param should also pass the auth middleware
        response = client.post("/mcp/messages?api_key=test-secret-token")
        assert response.status_code != 401
    finally:
        settings.jct_api_key = old_key
