"""
Contract snapshot test for JCT V1 Task Specification.

This test asserts that the TaskCreateLegacyV1 Pydantic model contains all canonical fields.
If this test fails, a breaking change to the API contract has been introduced.

The Pydantic model is the source of truth for the API contract, not the markdown docs.
Any change to the model shape that causes this test to fail is a breaking change.
"""

import pytest

from devops_control_tower.schemas.task_v1 import TaskCreateLegacyV1


class TestContractSnapshot:
    """Freeze the V1 contract schema to prevent accidental breaking changes."""

    def test_task_create_v1_has_canonical_top_level_fields(self):
        """TaskCreateLegacyV1 must have all canonical top-level fields."""
        schema = TaskCreateLegacyV1.model_json_schema()
        properties = schema.get("properties", {})

        # Canonical top-level fields that MUST exist
        required_fields = [
            "version",
            "idempotency_key",
            "requested_by",
            "objective",
            "operation",
            "target",
            "constraints",
            "inputs",
            "metadata",
        ]

        for field in required_fields:
            assert field in properties, (
                f"BREAKING CHANGE: Canonical field '{field}' missing from TaskCreateLegacyV1. "
                f"The Pydantic model is the API contract source of truth."
            )

    def test_requested_by_has_canonical_fields(self):
        """RequestedBy must have kind, id, and optional label."""
        schema = TaskCreateLegacyV1.model_json_schema()
        defs = schema.get("$defs", {})

        assert "RequestedBy" in defs, "RequestedBy schema definition missing"
        requested_by_props = defs["RequestedBy"].get("properties", {})

        required_fields = ["kind", "id", "label"]
        for field in required_fields:
            assert field in requested_by_props, (
                f"BREAKING CHANGE: Field '{field}' missing from RequestedBy. "
                f"The Pydantic model is the API contract source of truth."
            )

    def test_target_has_canonical_fields(self):
        """Target must have repo, ref, and path."""
        schema = TaskCreateLegacyV1.model_json_schema()
        defs = schema.get("$defs", {})

        assert "Target" in defs, "Target schema definition missing"
        target_props = defs["Target"].get("properties", {})

        required_fields = ["repo", "ref", "path"]
        for field in required_fields:
            assert field in target_props, (
                f"BREAKING CHANGE: Field '{field}' missing from Target. "
                f"The Pydantic model is the API contract source of truth."
            )

    def test_constraints_has_canonical_fields(self):
        """Constraints must have time_budget_seconds, allow_network, allow_secrets."""
        schema = TaskCreateLegacyV1.model_json_schema()
        defs = schema.get("$defs", {})

        assert "Constraints" in defs, "Constraints schema definition missing"
        constraints_props = defs["Constraints"].get("properties", {})

        required_fields = ["time_budget_seconds", "allow_network", "allow_secrets"]
        for field in required_fields:
            assert field in constraints_props, (
                f"BREAKING CHANGE: Field '{field}' missing from Constraints. "
                f"The Pydantic model is the API contract source of truth."
            )

    def test_operation_literal_values(self):
        """Operation must accept exactly the V1 allowed values."""
        schema = TaskCreateLegacyV1.model_json_schema()
        defs = schema.get("$defs", {})

        # Find the operation enum values
        # In Pydantic v2, Literal types may be in $defs or inline
        operation_prop = schema.get("properties", {}).get("operation", {})

        # Check for anyOf pattern (common with Optional[Literal[...]])
        any_of = operation_prop.get("anyOf", [])
        enum_values = None

        for item in any_of:
            if "enum" in item:
                enum_values = set(item["enum"])
                break

        # If not in anyOf, check direct enum
        if enum_values is None and "enum" in operation_prop:
            enum_values = set(operation_prop["enum"])

        expected_operations = {"code_change", "docs", "analysis", "ops"}

        assert enum_values is not None, (
            "BREAKING CHANGE: operation field does not define allowed values. "
            "Expected Literal type with enum constraint."
        )

        assert expected_operations.issubset(enum_values), (
            f"BREAKING CHANGE: operation field missing required values. "
            f"Expected: {expected_operations}, Found: {enum_values}"
        )

    def test_requester_kind_literal_values(self):
        """RequestedBy.kind must accept human, agent, system."""
        schema = TaskCreateLegacyV1.model_json_schema()
        defs = schema.get("$defs", {})

        requested_by_def = defs.get("RequestedBy", {})
        kind_prop = requested_by_def.get("properties", {}).get("kind", {})

        enum_values = set(kind_prop.get("enum", []))
        expected_kinds = {"human", "agent", "system"}

        assert expected_kinds == enum_values, (
            f"BREAKING CHANGE: RequestedBy.kind values changed. "
            f"Expected: {expected_kinds}, Found: {enum_values}"
        )

    def test_version_is_1_0(self):
        """Version field must default to '1.0' for V1 spec."""
        schema = TaskCreateLegacyV1.model_json_schema()
        version_prop = schema.get("properties", {}).get("version", {})

        # Check for Literal["1.0"] which shows as enum or const
        if "const" in version_prop:
            assert version_prop["const"] == "1.0", "Version const must be '1.0'"
        elif "enum" in version_prop:
            assert "1.0" in version_prop["enum"], "Version enum must include '1.0'"
        elif "default" in version_prop:
            assert version_prop["default"] == "1.0", "Version default must be '1.0'"
        else:
            # Check anyOf for Optional[Literal["1.0"]]
            any_of = version_prop.get("anyOf", [])
            found_1_0 = False
            for item in any_of:
                if item.get("const") == "1.0" or "1.0" in item.get("enum", []):
                    found_1_0 = True
                    break
            assert found_1_0, "BREAKING CHANGE: Version must be Literal['1.0']"

    def test_constraints_defaults(self):
        """Constraints must have conservative V1 defaults."""
        from devops_control_tower.schemas.task_v1 import Constraints

        defaults = Constraints()

        assert defaults.time_budget_seconds == 900, (
            "BREAKING CHANGE: Default time_budget_seconds changed from 900"
        )
        assert defaults.allow_network is False, (
            "BREAKING CHANGE: Default allow_network changed from False"
        )
        assert defaults.allow_secrets is False, (
            "BREAKING CHANGE: Default allow_secrets changed from False"
        )

    def test_target_defaults(self):
        """Target must have sensible V1 defaults."""
        from devops_control_tower.schemas.task_v1 import Target

        # repo is required, so we must provide it
        target = Target(repo="test/repo")

        assert target.ref == "main", (
            "BREAKING CHANGE: Default target.ref changed from 'main'"
        )
        assert target.path == "", (
            "BREAKING CHANGE: Default target.path changed from ''"
        )
