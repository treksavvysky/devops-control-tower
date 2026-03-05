"""Tests for ChatGPT Actions integration: auth and OpenAPI spec."""

from unittest.mock import patch


class TestApiKeyAuth:
    """Test optional API key authentication."""

    def test_no_auth_when_key_not_configured(self, client):
        """When JCT_API_KEY is not set, endpoints are accessible without auth."""
        response = client.get("/tasks")
        assert response.status_code == 200

    def test_auth_required_when_key_configured(self, client):
        """When JCT_API_KEY is set, requests without auth get 401."""
        with patch("devops_control_tower.auth.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_key = "test-secret-key"
            response = client.get("/tasks")
            assert response.status_code == 401

    def test_auth_succeeds_with_correct_key(self, client):
        """Correct bearer token passes authentication."""
        with patch("devops_control_tower.auth.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_key = "test-secret-key"
            response = client.get(
                "/tasks",
                headers={"Authorization": "Bearer test-secret-key"},
            )
            assert response.status_code == 200

    def test_auth_fails_with_wrong_key(self, client):
        """Wrong bearer token gets 401."""
        with patch("devops_control_tower.auth.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_key = "test-secret-key"
            response = client.get(
                "/tasks",
                headers={"Authorization": "Bearer wrong-key"},
            )
            assert response.status_code == 401

    def test_health_endpoint_never_requires_auth(self, client):
        """Health checks bypass auth regardless of config."""
        with patch("devops_control_tower.auth.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_key = "test-secret-key"
            response = client.get("/health")
            assert response.status_code == 200

    def test_enqueue_requires_auth_when_configured(self, client, valid_task_payload):
        """POST /tasks/enqueue returns 401 when key is set but not provided."""
        with patch("devops_control_tower.auth.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_key = "test-secret-key"
            response = client.post("/tasks/enqueue", json=valid_task_payload)
            assert response.status_code == 401

    def test_enqueue_succeeds_with_correct_key(self, client, valid_task_payload):
        """POST /tasks/enqueue works with correct bearer token."""
        with patch("devops_control_tower.auth.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_key = "test-secret-key"
            response = client.post(
                "/tasks/enqueue",
                json=valid_task_payload,
                headers={"Authorization": "Bearer test-secret-key"},
            )
            assert response.status_code == 201

    def test_get_task_requires_auth_when_configured(self, client):
        """GET /tasks/{id} returns 401 when key is set but not provided."""
        with patch("devops_control_tower.auth.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_key = "test-secret-key"
            response = client.get("/tasks/nonexistent-id")
            assert response.status_code == 401


class TestGptOpenApiSpec:
    """Test the /openapi-gpt.json endpoint."""

    def test_spec_is_accessible(self, client):
        """GPT spec endpoint returns valid JSON."""
        response = client.get("/openapi-gpt.json")
        assert response.status_code == 200
        spec = response.json()
        assert "openapi" in spec
        assert "paths" in spec

    def test_spec_contains_only_task_endpoints(self, client):
        """GPT spec only exposes the 3 task endpoints."""
        response = client.get("/openapi-gpt.json")
        spec = response.json()

        paths = spec["paths"]
        assert "/tasks/enqueue" in paths
        assert "/tasks/{task_id}" in paths
        assert "/tasks" in paths

        # Should NOT contain CWOM, events, agents, health, etc.
        for path in paths:
            assert path.startswith("/tasks"), f"Unexpected path in GPT spec: {path}"

    def test_spec_has_operation_ids(self, client):
        """All operations in GPT spec have operationId."""
        response = client.get("/openapi-gpt.json")
        spec = response.json()

        operation_ids = set()
        for path_item in spec["paths"].values():
            for operation in path_item.values():
                if isinstance(operation, dict):
                    assert "operationId" in operation
                    operation_ids.add(operation["operationId"])

        assert operation_ids == {"enqueueTask", "listTasks", "getTask"}

    def test_spec_has_server_url(self, client):
        """GPT spec includes the configured server URL."""
        response = client.get("/openapi-gpt.json")
        spec = response.json()
        assert "servers" in spec
        assert len(spec["servers"]) > 0
        assert "url" in spec["servers"][0]

    def test_spec_has_security_scheme(self, client):
        """GPT spec includes bearer auth security scheme."""
        response = client.get("/openapi-gpt.json")
        spec = response.json()
        assert "securitySchemes" in spec.get("components", {})
        assert "BearerAuth" in spec["components"]["securitySchemes"]

    def test_spec_has_top_level_security(self, client):
        """GPT spec has top-level security requiring BearerAuth."""
        response = client.get("/openapi-gpt.json")
        spec = response.json()
        assert "security" in spec
        assert {"BearerAuth": []} in spec["security"]

    def test_spec_descriptions_within_limits(self, client):
        """Endpoint descriptions stay within ChatGPT's 300 char limit."""
        response = client.get("/openapi-gpt.json")
        spec = response.json()

        for path, path_item in spec["paths"].items():
            for method, operation in path_item.items():
                if isinstance(operation, dict) and "description" in operation:
                    assert len(operation["description"]) <= 300, (
                        f"{method.upper()} {path} description exceeds 300 chars"
                    )

    def test_spec_param_descriptions_within_limits(self, client):
        """Parameter descriptions stay within ChatGPT's 700 char limit."""
        response = client.get("/openapi-gpt.json")
        spec = response.json()

        for path, path_item in spec["paths"].items():
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                for param in operation.get("parameters", []):
                    desc = param.get("description", "")
                    assert len(desc) <= 700, (
                        f"Param '{param.get('name')}' on {method.upper()} {path} "
                        f"description exceeds 700 chars"
                    )

    def test_spec_not_in_main_schema(self, client):
        """The /openapi-gpt.json endpoint should not appear in the main schema."""
        response = client.get("/openapi.json")
        spec = response.json()
        assert "/openapi-gpt.json" not in spec.get("paths", {})

    def test_spec_server_url_configurable(self, client):
        """Server URL in spec reflects JCT_API_BASE_URL setting."""
        with patch("devops_control_tower.gpt_openapi.get_settings") as mock_settings:
            mock_settings.return_value.jct_api_base_url = "https://api.example.com"
            # Need to also mock the version
            mock_settings.return_value.jct_api_key = None
            response = client.get("/openapi-gpt.json")
            spec = response.json()
            assert spec["servers"][0]["url"] == "https://api.example.com"
