"""
Policy gate for JCT V1 Task Specification.

This module implements a pure, testable policy gate that evaluates and normalizes
incoming tasks. It enforces governance rules and returns either a normalized task
or raises a PolicyError with a stable error code.

Policy Rules (V1):
- operation must be one of: code_change, docs, analysis, ops
- target.repo must match an allowlist/prefix (configured via JCT_ALLOWED_REPO_PREFIXES env var)
- constraints.time_budget_seconds must be in range [30, 86400]
- constraints.allow_network must be false (V1 denies network access)
- constraints.allow_secrets must be false (V1 denies secrets access)

Configuration:
- JCT_ALLOWED_REPO_PREFIXES: Comma-separated list of allowed repository prefixes
  (e.g., "myorg/,anotherorg/"). Empty or unset = deny all repositories.

Normalization:
- target.ref defaults to "main"
- target.path defaults to ""
- objective is trimmed of leading/trailing whitespace
- target.repo is canonicalized (lowercase, trailing .git stripped)
"""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel

from devops_control_tower.schemas.task_v1 import (
    Constraints,
    RequestedBy,
    Target,
    TaskCreateLegacyV1,
)


def _parse_repo_prefixes(raw: str) -> List[str]:
    """
    Parse comma-separated repository prefixes from environment variable.

    - Strips whitespace from each prefix
    - Filters out empty strings
    - Returns empty list if input is empty/whitespace

    Examples:
        "myorg/,anotherorg/" -> ["myorg/", "anotherorg/"]
        "  org1/ , org2/  " -> ["org1/", "org2/"]
        "" -> []
        "   " -> []
    """
    if not raw or not raw.strip():
        return []

    prefixes = [prefix.strip() for prefix in raw.split(",")]
    return [p for p in prefixes if p]


def _get_default_policy_config() -> "PolicyConfig":
    """
    Get default policy config from environment settings.

    This lazy-loads the settings to avoid circular imports and
    reads JCT_ALLOWED_REPO_PREFIXES from environment.
    """
    from devops_control_tower.config import settings

    allowed_prefixes = _parse_repo_prefixes(settings.jct_allowed_repo_prefixes)

    return PolicyConfig(allowed_repo_prefixes=allowed_prefixes)


# Time budget limits
MIN_TIME_BUDGET_SECONDS = 30
MAX_TIME_BUDGET_SECONDS = 86400
DEFAULT_TIME_BUDGET_SECONDS = 900

# Allowed operations (V1)
ALLOWED_OPERATIONS = {"code_change", "docs", "analysis", "ops"}


class PolicyConfig(BaseModel):
    """Configuration for policy evaluation."""

    allowed_repo_prefixes: List[str] = []
    min_time_budget_seconds: int = MIN_TIME_BUDGET_SECONDS
    max_time_budget_seconds: int = MAX_TIME_BUDGET_SECONDS
    default_time_budget_seconds: int = DEFAULT_TIME_BUDGET_SECONDS


class PolicyError(Exception):
    """
    Raised when a task fails policy evaluation.

    Attributes:
        code: Stable error code for programmatic handling
        message: Human-readable error description
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "error": "policy_violation",
            "code": self.code,
            "message": self.message,
        }


def _normalize_repo(repo: str) -> str:
    """
    Canonicalize repository name.

    - Strip trailing .git
    - Strip leading/trailing whitespace
    - Lowercase for consistency
    """
    repo = repo.strip()
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo.lower()


def _validate_operation(operation: str) -> None:
    """Validate operation is in allowed set."""
    if operation not in ALLOWED_OPERATIONS:
        raise PolicyError(
            code="INVALID_OPERATION",
            message=f"Operation '{operation}' is not allowed. "
            f"Allowed operations: {', '.join(sorted(ALLOWED_OPERATIONS))}",
        )


def _validate_repo(repo: str, config: PolicyConfig) -> None:
    """Validate repository is in allowlist."""
    normalized = _normalize_repo(repo)
    for prefix in config.allowed_repo_prefixes:
        if normalized.startswith(prefix.lower()):
            return
    raise PolicyError(
        code="REPO_NOT_ALLOWED",
        message=f"Repository '{repo}' is not in the allowed namespace. "
        f"Allowed prefixes: {', '.join(config.allowed_repo_prefixes)}",
    )


def _validate_time_budget(time_budget: int, config: PolicyConfig) -> None:
    """Validate time budget is within safe range."""
    if time_budget < config.min_time_budget_seconds:
        raise PolicyError(
            code="TIME_BUDGET_TOO_LOW",
            message=f"Time budget {time_budget}s is below minimum "
            f"({config.min_time_budget_seconds}s)",
        )
    if time_budget > config.max_time_budget_seconds:
        raise PolicyError(
            code="TIME_BUDGET_TOO_HIGH",
            message=f"Time budget {time_budget}s exceeds maximum "
            f"({config.max_time_budget_seconds}s)",
        )


def _validate_network_access(allow_network: bool) -> None:
    """V1 policy: network access is denied."""
    if allow_network:
        raise PolicyError(
            code="NETWORK_ACCESS_DENIED",
            message="Network access is not allowed in V1. "
            "Set constraints.allow_network to false.",
        )


def _validate_secrets_access(allow_secrets: bool) -> None:
    """V1 policy: secrets access is denied."""
    if allow_secrets:
        raise PolicyError(
            code="SECRETS_ACCESS_DENIED",
            message="Secrets access is not allowed in V1. "
            "Set constraints.allow_secrets to false.",
        )


def evaluate(
    task: TaskCreateLegacyV1, config: Optional[PolicyConfig] = None
) -> TaskCreateLegacyV1:
    """
    Evaluate a task against policy rules and return normalized version.

    This is a pure function: no DB access, no FastAPI request objects.

    Args:
        task: The incoming task to evaluate
        config: Optional policy configuration. If not provided, reads from
                environment variable JCT_ALLOWED_REPO_PREFIXES. Empty or
                unset environment variable = deny-by-default (no repos allowed).

    Returns:
        A new TaskCreateLegacyV1 with normalized values

    Raises:
        PolicyError: If the task violates any policy rule
    """
    if config is None:
        config = _get_default_policy_config()

    # Validate operation
    _validate_operation(task.operation)

    # Validate repository
    _validate_repo(task.target.repo, config)

    # Validate constraints
    _validate_time_budget(task.constraints.time_budget_seconds, config)
    _validate_network_access(task.constraints.allow_network)
    _validate_secrets_access(task.constraints.allow_secrets)

    # Build normalized task
    normalized_target = Target(
        repo=_normalize_repo(task.target.repo),
        ref=task.target.ref if task.target.ref else "main",
        path=task.target.path if task.target.path is not None else "",
    )

    normalized_constraints = Constraints(
        time_budget_seconds=task.constraints.time_budget_seconds,
        allow_network=False,  # Always false in V1
        allow_secrets=False,  # Always false in V1
    )

    normalized_requested_by = RequestedBy(
        kind=task.requested_by.kind,
        id=task.requested_by.id,
        label=task.requested_by.label,
    )

    return TaskCreateLegacyV1(
        version=task.version,
        idempotency_key=task.idempotency_key,
        requested_by=normalized_requested_by,
        objective=task.objective.strip(),
        operation=task.operation,
        target=normalized_target,
        constraints=normalized_constraints,
        inputs=task.inputs,
        metadata=task.metadata,
    )
