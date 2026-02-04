from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, constr, conint, model_validator, ConfigDict

# Reuse your existing RequestedBy and Constraints classes as-is.

class RequestedBy(BaseModel):
    """Structured audit information about who/what initiated the task."""

    kind: Literal["human", "agent", "system"]
    id: constr(min_length=1, max_length=128)
    label: Optional[constr(min_length=1, max_length=256)] = None


class Target(BaseModel):
    """Specifies the repository and location for the task.

    Compatibility: accepts 'repository' as alias for 'repo' (deprecated).
    """

    repo: Optional[constr(min_length=1, max_length=256)] = None
    ref: constr(min_length=1, max_length=256) = "main"
    path: constr(max_length=512) = ""

    # Legacy alias (deprecated, will be removed in V2)
    repository: Optional[constr(min_length=1, max_length=256)] = None

    @model_validator(mode="after")
    def resolve_repo_alias(self) -> "Target":
        """Resolve 'repository' alias to 'repo' for backwards compatibility."""
        if self.repo is None and self.repository is not None:
            # Use repository as repo (compatibility layer)
            object.__setattr__(self, "repo", self.repository)
        elif self.repo is None and self.repository is None:
            raise ValueError("Either 'repo' or 'repository' must be provided")
        # Clear the legacy field after resolution
        object.__setattr__(self, "repository", None)
        return self


class Constraints(BaseModel):
    """Resource and security constraints for task execution."""

    time_budget_seconds: conint(ge=30, le=86400) = 900
    allow_network: bool = False
    allow_secrets: bool = False


class TaskCreateLegacyV1(BaseModel):
    """
    JCT V1 Task Specification.

    This is the legacy compatibility intake model for creating tasks in Jules Control Tower.
    See docs/specs/task-spec-v1.md for full documentation.

    Compatibility Layer (temporary, will be removed in V2):
    - 'type' is accepted as alias for 'operation'
    - 'payload' is accepted as alias for 'inputs'
    - 'target.repository' is accepted as alias for 'target.repo'
    """

    version: Literal["1.0"] = "1.0"
    idempotency_key: Optional[constr(min_length=1, max_length=256)] = None

    requested_by: RequestedBy
    objective: constr(min_length=5, max_length=4000)

    # Canonical field
    operation: Optional[Literal["code_change", "docs", "analysis", "ops"]] = None
    # Legacy alias (deprecated, will be removed in V2)
    type: Optional[Literal["code_change", "docs", "analysis", "ops"]] = None

    target: Target
    constraints: Constraints = Field(default_factory=Constraints)

    # Canonical field
    inputs: Dict[str, Any] = Field(default_factory=dict)
    # Legacy alias (deprecated, will be removed in V2)
    payload: Optional[Dict[str, Any]] = None

    # Acceptance and evidence (V1.1 additions)
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="Structured criteria that define task completion"
    )
    evidence_requirements: List[str] = Field(
        default_factory=list,
        description="Required artifacts/evidence to prove completion"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def resolve_legacy_aliases(self) -> "TaskCreateLegacyV1":
        """Resolve legacy field aliases to canonical fields for backwards compatibility."""
        # Resolve 'type' -> 'operation'
        if self.operation is None and self.type is not None:
            object.__setattr__(self, "operation", self.type)
        elif self.operation is None and self.type is None:
            raise ValueError("Either 'operation' or 'type' must be provided")
        # Clear legacy field after resolution
        object.__setattr__(self, "type", None)

        # Resolve 'payload' -> 'inputs'
        if not self.inputs and self.payload is not None:
            object.__setattr__(self, "inputs", self.payload)
        # Clear legacy field after resolution
        object.__setattr__(self, "payload", None)

        return self

    class Config:
        json_schema_extra = {
            "example": {
                "version": "1.0",
                "idempotency_key": "2025-12-08T14:05:00Z-devops-ctl-001",
                "requested_by": {
                    "kind": "human",
                    "id": "alice",
                    "label": "Alice Developer",
                },
                "objective": 'Add a /healthz endpoint that returns {"status":"ok"} and a pytest that verifies 200 + body.',
                "operation": "code_change",
                "target": {
                    "repo": "myorg/example-service",
                    "ref": "main",
                    "path": "",
                },
                "constraints": {
                    "time_budget_seconds": 900,
                    "allow_network": False,
                    "allow_secrets": False,
                },
                "inputs": {},
                "acceptance_criteria": [
                    "Endpoint returns 200 with JSON body",
                    "pytest passes with >80% coverage"
                ],
                "evidence_requirements": [
                    "test_healthz.py output",
                    "coverage report"
                ],
                "metadata": {"tags": ["stage-1", "api"]},
            }
        }

class TargetV1(BaseModel):
    repo: constr(min_length=1, max_length=256)
    ref: constr(min_length=1, max_length=256) = "main"
    path: constr(max_length=512) = ""

    class Config:
        extra = "forbid"

class TaskCreateV1(BaseModel):
    """
    JCT V1 Task Specification (Canonical).
    This is the schema new clients should submit.
    """
    
    version: Literal["1.0"] = "1.0"
    idempotency_key: Optional[constr(min_length=1, max_length=256)] = None

    requested_by: RequestedBy
    objective: constr(min_length=5, max_length=4000)
    operation: Literal["code_change", "docs", "analysis", "ops"]

    target: TargetV1
    constraints: Constraints = Field(default_factory=Constraints)

    inputs: Dict[str, Any] = Field(default_factory=dict)

    # Acceptance and evidence (V1.1 additions)
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="Structured criteria that define task completion"
    )
    evidence_requirements: List[str] = Field(
        default_factory=list,
        description="Required artifacts/evidence to prove completion"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "version": "1.0",
                "idempotency_key": "demo-001",
                "requested_by": {"kind": "human", "id": "operator", "label": "Operator"},
                "objective": "Add a /healthz endpoint and a pytest that verifies 200 + body.",
                "operation": "code_change",
                "target": {"repo": "myorg/example-service", "ref": "main", "path": ""},
                "constraints": {
                    "time_budget_seconds": 900,
                    "allow_network": False,
                    "allow_secrets": False,
                },
                "inputs": {},
                "acceptance_criteria": [
                    "Endpoint returns 200 with JSON body",
                    "pytest passes with >80% coverage"
                ],
                "evidence_requirements": [
                    "test_healthz.py output",
                    "coverage report"
                ],
                "metadata": {"tags": ["stage-1", "api"]},
            }
        }