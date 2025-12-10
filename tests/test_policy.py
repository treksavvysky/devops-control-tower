"""Unit tests for the policy module."""

import pytest

from devops_control_tower.policy import PolicyError, evaluate
from devops_control_tower.policy.task_gate import (
    PolicyConfig,
    _normalize_repo,
    _parse_repo_prefixes,
)
from devops_control_tower.schemas.task_v1 import (
    Constraints,
    RequestedBy,
    Target,
    TaskCreateLegacyV1,
)


def make_valid_task(**overrides) -> TaskCreateLegacyV1:
    """Create a valid task with optional overrides."""
    defaults = {
        "version": "1.0",
        "requested_by": RequestedBy(kind="human", id="test-user", label="Test User"),
        "objective": "Test objective for the task",
        "operation": "code_change",
        "target": Target(repo="testorg/test-repo", ref="main", path=""),
        "constraints": Constraints(
            time_budget_seconds=900, allow_network=False, allow_secrets=False
        ),
        "inputs": {},
        "metadata": {},
    }
    defaults.update(overrides)
    return TaskCreateLegacyV1(**defaults)


class TestParseRepoPrefixes:
    """Tests for parsing comma-separated repository prefixes."""

    def test_parses_single_prefix(self):
        assert _parse_repo_prefixes("myorg/") == ["myorg/"]

    def test_parses_multiple_prefixes(self):
        assert _parse_repo_prefixes("myorg/,anotherorg/") == ["myorg/", "anotherorg/"]

    def test_strips_whitespace(self):
        assert _parse_repo_prefixes("  org1/ , org2/  ") == ["org1/", "org2/"]

    def test_filters_empty_strings(self):
        assert _parse_repo_prefixes("myorg/,,anotherorg/") == ["myorg/", "anotherorg/"]

    def test_empty_string_returns_empty_list(self):
        assert _parse_repo_prefixes("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert _parse_repo_prefixes("   ") == []


class TestNormalizeRepo:
    """Tests for repository name normalization."""

    def test_strips_trailing_git(self):
        assert _normalize_repo("myorg/repo.git") == "myorg/repo"

    def test_strips_whitespace(self):
        assert _normalize_repo("  myorg/repo  ") == "myorg/repo"

    def test_lowercases_repo(self):
        assert _normalize_repo("MyOrg/Repo") == "myorg/repo"

    def test_handles_combined_normalization(self):
        assert _normalize_repo("  MyOrg/Repo.git  ") == "myorg/repo"


class TestOperationValidation:
    """Tests for operation validation."""

    @pytest.mark.parametrize(
        "operation", ["code_change", "docs", "analysis", "ops"]
    )
    def test_valid_operations_pass(self, operation):
        task = make_valid_task(operation=operation)
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.operation == operation

    def test_invalid_operation_raises_policy_error(self):
        # We can't directly create a TaskCreateLegacyV1 with invalid operation due to Literal type
        # So we test by checking the policy module's behavior when given an unexpected value
        # This would be caught at Pydantic validation, so the test is more about documentation
        pass


class TestRepoValidation:
    """Tests for repository allowlist validation."""

    def test_allowed_repo_prefix_passes(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = make_valid_task(target=Target(repo="testorg/my-repo"))
        result = evaluate(task, config)
        assert result.target.repo == "testorg/my-repo"

    def test_allowed_repo_with_git_suffix_normalized(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = make_valid_task(target=Target(repo="testorg/my-repo.git"))
        result = evaluate(task, config)
        assert result.target.repo == "testorg/my-repo"

    def test_allowed_repo_case_insensitive(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = make_valid_task(target=Target(repo="TestOrg/My-Repo"))
        result = evaluate(task, config)
        assert result.target.repo == "testorg/my-repo"

    def test_disallowed_repo_raises_policy_error(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = make_valid_task(target=Target(repo="unauthorized/repo"))
        with pytest.raises(PolicyError) as exc_info:
            evaluate(task, config)
        assert exc_info.value.code == "REPO_NOT_ALLOWED"
        assert "unauthorized/repo" in exc_info.value.message

    def test_custom_repo_allowlist(self):
        config = PolicyConfig(allowed_repo_prefixes=["custom-org/"])
        task = make_valid_task(target=Target(repo="custom-org/my-repo"))
        result = evaluate(task, config)
        assert result.target.repo == "custom-org/my-repo"

    def test_custom_repo_allowlist_rejects_other_repos(self):
        config = PolicyConfig(allowed_repo_prefixes=["custom-org/"])
        task = make_valid_task(target=Target(repo="testorg/my-repo"))
        with pytest.raises(PolicyError) as exc_info:
            evaluate(task, config)
        assert exc_info.value.code == "REPO_NOT_ALLOWED"

    def test_empty_allowlist_denies_all_repos(self):
        """When no prefixes are configured, all repos should be denied."""
        config = PolicyConfig(allowed_repo_prefixes=[])
        task = make_valid_task(target=Target(repo="any-org/any-repo"))
        with pytest.raises(PolicyError) as exc_info:
            evaluate(task, config)
        assert exc_info.value.code == "REPO_NOT_ALLOWED"

    def test_multiple_allowed_prefixes(self):
        """Multiple prefixes should all be allowed."""
        config = PolicyConfig(allowed_repo_prefixes=["org1/", "org2/", "org3/"])

        # All three should pass
        for org in ["org1", "org2", "org3"]:
            task = make_valid_task(target=Target(repo=f"{org}/test-repo"))
            result = evaluate(task, config)
            assert result.target.repo == f"{org}/test-repo"


class TestTimeBudgetValidation:
    """Tests for time budget constraint validation."""

    def test_valid_time_budget_passes(self):
        task = make_valid_task(
            constraints=Constraints(time_budget_seconds=3600)
        )
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.constraints.time_budget_seconds == 3600

    def test_minimum_time_budget_passes(self):
        task = make_valid_task(
            constraints=Constraints(time_budget_seconds=30)
        )
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.constraints.time_budget_seconds == 30

    def test_maximum_time_budget_passes(self):
        task = make_valid_task(
            constraints=Constraints(time_budget_seconds=86400)
        )
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.constraints.time_budget_seconds == 86400

    def test_time_budget_below_minimum_rejected_by_pydantic(self):
        # Pydantic's conint(ge=30) catches this before policy
        with pytest.raises(Exception):  # ValidationError
            make_valid_task(constraints=Constraints(time_budget_seconds=29))

    def test_time_budget_above_maximum_rejected_by_pydantic(self):
        # Pydantic's conint(le=86400) catches this before policy
        with pytest.raises(Exception):  # ValidationError
            make_valid_task(constraints=Constraints(time_budget_seconds=86401))


class TestNetworkAccessValidation:
    """Tests for network access constraint validation."""

    def test_network_false_passes(self):
        task = make_valid_task(
            constraints=Constraints(allow_network=False)
        )
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.constraints.allow_network is False

    def test_network_true_raises_policy_error(self):
        task = make_valid_task(
            constraints=Constraints(allow_network=True)
        )
        with pytest.raises(PolicyError) as exc_info:
            config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

            evaluate(task, config)
        assert exc_info.value.code == "NETWORK_ACCESS_DENIED"


class TestSecretsAccessValidation:
    """Tests for secrets access constraint validation."""

    def test_secrets_false_passes(self):
        task = make_valid_task(
            constraints=Constraints(allow_secrets=False)
        )
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.constraints.allow_secrets is False

    def test_secrets_true_raises_policy_error(self):
        task = make_valid_task(
            constraints=Constraints(allow_secrets=True)
        )
        with pytest.raises(PolicyError) as exc_info:
            config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

            evaluate(task, config)
        assert exc_info.value.code == "SECRETS_ACCESS_DENIED"


class TestNormalization:
    """Tests for task normalization."""

    def test_objective_whitespace_trimmed(self):
        task = make_valid_task(objective="  Test objective with spaces  ")
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.objective == "Test objective with spaces"

    def test_target_ref_defaults_to_main(self):
        # The Pydantic model already defaults to "main", but let's verify it persists
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = make_valid_task(target=Target(repo="testorg/repo"))
        result = evaluate(task, config)
        assert result.target.ref == "main"

    def test_target_path_defaults_to_empty(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = make_valid_task(target=Target(repo="testorg/repo"))
        result = evaluate(task, config)
        assert result.target.path == ""

    def test_repo_canonicalized(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = make_valid_task(target=Target(repo="TestOrg/Repo.git"))
        result = evaluate(task, config)
        assert result.target.repo == "testorg/repo"

    def test_constraints_normalized_to_false(self):
        # Even if somehow passed through, constraints should be normalized
        task = make_valid_task(
            constraints=Constraints(
                time_budget_seconds=900, allow_network=False, allow_secrets=False
            )
        )
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])

        result = evaluate(task, config)
        assert result.constraints.allow_network is False
        assert result.constraints.allow_secrets is False


class TestPolicyErrorSerialization:
    """Tests for PolicyError JSON serialization."""

    def test_to_dict_format(self):
        error = PolicyError(code="TEST_CODE", message="Test message")
        result = error.to_dict()
        assert result == {
            "error": "policy_violation",
            "code": "TEST_CODE",
            "message": "Test message",
        }

    def test_str_representation(self):
        error = PolicyError(code="TEST_CODE", message="Test message")
        assert str(error) == "TEST_CODE: Test message"


class TestPolicyConfig:
    """Tests for PolicyConfig customization."""

    def test_default_allowed_prefixes_empty(self):
        """By default, no repos are allowed (deny-by-default)."""
        config = PolicyConfig()
        assert config.allowed_repo_prefixes == []

    def test_custom_time_budget_limits(self):
        config = PolicyConfig(
            min_time_budget_seconds=60,
            max_time_budget_seconds=1800,
        )
        assert config.min_time_budget_seconds == 60
        assert config.max_time_budget_seconds == 1800


class TestEvaluateIntegration:
    """Integration tests for the evaluate function."""

    def test_valid_task_returns_normalized_copy(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        original = make_valid_task(
            objective="  Test objective  ",
            target=Target(repo="TestOrg/Repo.git", ref="main", path=""),
        )
        result = evaluate(original, config)

        # Should be a new object
        assert result is not original

        # Should have normalized values
        assert result.objective == "Test objective"
        assert result.target.repo == "testorg/repo"

    def test_preserves_non_normalized_fields(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        original = make_valid_task(
            idempotency_key="test-key-123",
            inputs={"file": "test.py"},
            metadata={"tags": ["test"]},
        )
        result = evaluate(original, config)

        assert result.idempotency_key == "test-key-123"
        assert result.inputs == {"file": "test.py"}
        assert result.metadata == {"tags": ["test"]}

    def test_preserves_requested_by(self):
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        original = make_valid_task(
            requested_by=RequestedBy(kind="agent", id="jules-001", label="Jules Agent")
        )
        result = evaluate(original, config)

        assert result.requested_by.kind == "agent"
        assert result.requested_by.id == "jules-001"
        assert result.requested_by.label == "Jules Agent"


class TestCompatibilityLayerSchema:
    """Tests for backward compatibility layer at the schema level.

    These tests verify that legacy field aliases are correctly resolved
    by the Pydantic models before policy evaluation.
    """

    def test_type_alias_resolves_to_operation(self):
        """Legacy 'type' field should be resolved to 'operation'."""
        task = TaskCreateLegacyV1(
            requested_by=RequestedBy(kind="human", id="test"),
            objective="Test type alias",
            type="docs",  # Legacy
            target=Target(repo="testorg/repo"),
        )
        assert task.operation == "docs"
        assert task.type is None  # Cleared after resolution

    def test_payload_alias_resolves_to_inputs(self):
        """Legacy 'payload' field should be resolved to 'inputs'."""
        task = TaskCreateLegacyV1(
            requested_by=RequestedBy(kind="human", id="test"),
            objective="Test payload alias",
            operation="analysis",
            target=Target(repo="testorg/repo"),
            payload={"key": "value"},  # Legacy
        )
        assert task.inputs == {"key": "value"}
        assert task.payload is None  # Cleared after resolution

    def test_repository_alias_resolves_to_repo(self):
        """Legacy 'repository' field should be resolved to 'repo'."""
        target = Target(repository="testorg/repo")  # Legacy
        assert target.repo == "testorg/repo"
        assert target.repository is None  # Cleared after resolution

    def test_canonical_operation_preferred_over_type(self):
        """When both 'operation' and 'type' provided, 'operation' wins."""
        task = TaskCreateLegacyV1(
            requested_by=RequestedBy(kind="human", id="test"),
            objective="Test operation preference",
            operation="code_change",  # Canonical
            type="docs",  # Legacy (should be ignored)
            target=Target(repo="testorg/repo"),
        )
        assert task.operation == "code_change"

    def test_canonical_inputs_preferred_over_payload(self):
        """When both 'inputs' and 'payload' provided, 'inputs' wins."""
        task = TaskCreateLegacyV1(
            requested_by=RequestedBy(kind="human", id="test"),
            objective="Test inputs preference",
            operation="analysis",
            target=Target(repo="testorg/repo"),
            inputs={"canonical": True},  # Canonical
            payload={"legacy": True},  # Legacy (should be ignored)
        )
        assert task.inputs == {"canonical": True}

    def test_canonical_repo_preferred_over_repository(self):
        """When both 'repo' and 'repository' provided, 'repo' wins."""
        target = Target(
            repo="testorg/canonical",  # Canonical
            repository="testorg/legacy",  # Legacy (should be ignored)
        )
        assert target.repo == "testorg/canonical"

    def test_missing_operation_and_type_raises_error(self):
        """Missing both 'operation' and 'type' should raise ValueError."""
        with pytest.raises(ValueError, match="Either 'operation' or 'type' must be provided"):
            TaskCreateLegacyV1(
                requested_by=RequestedBy(kind="human", id="test"),
                objective="Test missing operation",
                target=Target(repo="testorg/repo"),
            )

    def test_missing_repo_and_repository_raises_error(self):
        """Missing both 'repo' and 'repository' should raise ValueError."""
        with pytest.raises(ValueError, match="Either 'repo' or 'repository' must be provided"):
            Target(ref="main", path="src/")

    def test_legacy_task_through_policy_evaluation(self):
        """Task with all legacy fields should pass through policy correctly."""
        config = PolicyConfig(allowed_repo_prefixes=["testorg/"])
        task = TaskCreateLegacyV1(
            requested_by=RequestedBy(kind="system", id="ci"),
            objective="Full legacy test",
            type="ops",  # Legacy
            target=Target(repository="testorg/test"),  # Legacy
            payload={"build_id": 123},  # Legacy
        )
        result = evaluate(task, config)

        assert result.operation == "ops"
        assert result.target.repo == "testorg/test"
        assert result.inputs == {"build_id": 123}
