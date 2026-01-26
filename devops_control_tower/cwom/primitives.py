"""
CWOM v0.1 Common Primitives.

These are the building blocks used across all CWOM object types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import ActorKind, ObjectKind


def generate_ulid() -> str:
    """Generate a ULID for object IDs.

    ULIDs are lexicographically sortable and globally unique.
    Falls back to UUID4 if ulid package is not available.
    """
    try:
        from ulid import ULID

        return str(ULID())
    except ImportError:
        import uuid

        return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class Actor(BaseModel):
    """Represents who/what created or executed something.

    Used for audit trails and attribution across CWOM objects.
    """

    model_config = ConfigDict(extra="forbid")

    actor_kind: ActorKind = Field(
        ..., description="Type of actor: human, agent, or system"
    )
    actor_id: constr(min_length=1, max_length=128) = Field(
        ..., description="Unique identifier for the actor"
    )
    display: Optional[constr(min_length=1, max_length=256)] = Field(
        None, description="Human-readable display name"
    )


class Source(BaseModel):
    """Represents linkage to external systems (GitHub, Linear, etc.).

    Used to track where objects originated or are synchronized with.
    """

    model_config = ConfigDict(extra="forbid")

    system: constr(min_length=1, max_length=64) = Field(
        ..., description="External system name (e.g., 'github', 'linear', 'jira')"
    )
    external_id: Optional[constr(min_length=1, max_length=256)] = Field(
        None, description="ID in the external system"
    )
    url: Optional[constr(min_length=1, max_length=2000)] = Field(
        None, description="URL to the object in the external system"
    )


class Ref(BaseModel):
    """Universal reference to another CWOM object.

    Rules:
    - kind + id must resolve to exactly one object
    - role is optional semantic labeling (e.g., 'primary_context', 'governing_doctrine')
    """

    model_config = ConfigDict(extra="forbid")

    kind: ObjectKind = Field(..., description="The type of object being referenced")
    id: constr(min_length=1, max_length=128) = Field(
        ..., description="The unique ID of the referenced object"
    )
    role: Optional[constr(min_length=1, max_length=64)] = Field(
        None, description="Optional semantic role (e.g., 'primary_context')"
    )


class Document(BaseModel):
    """A document reference within a ContextPacket."""

    model_config = ConfigDict(extra="forbid")

    title: constr(min_length=1, max_length=256) = Field(
        ..., description="Document title"
    )
    uri: constr(min_length=1, max_length=2000) = Field(
        ..., description="URI to the document"
    )
    digest: Optional[constr(min_length=1, max_length=128)] = Field(
        None, description="Content hash (sha256 recommended)"
    )
    excerpt: Optional[constr(max_length=4000)] = Field(
        None, description="Relevant excerpt from the document"
    )


class DataBlob(BaseModel):
    """A data blob within a ContextPacket."""

    model_config = ConfigDict(extra="forbid")

    name: constr(min_length=1, max_length=256) = Field(..., description="Blob name")
    media_type: constr(min_length=1, max_length=128) = Field(
        ..., description="MIME type (e.g., 'application/json')"
    )
    uri: Optional[constr(min_length=1, max_length=2000)] = Field(
        None, description="URI to the blob (if stored externally)"
    )
    inline: Optional[str] = Field(
        None, description="Inline content (base64 or raw text for small data)"
    )
    digest: Optional[constr(min_length=1, max_length=128)] = Field(
        None, description="Content hash"
    )


class VerificationCheck(BaseModel):
    """An individual verification check result."""

    model_config = ConfigDict(extra="forbid")

    name: constr(min_length=1, max_length=128) = Field(..., description="Check name")
    status: Literal["passed", "failed", "unverified"] = Field(
        ..., description="Check result"
    )
    evidence_uri: Optional[constr(min_length=1, max_length=2000)] = Field(
        None, description="URI to evidence/logs"
    )


class TimeConstraint(BaseModel):
    """Time-related constraints."""

    model_config = ConfigDict(extra="forbid")

    available_minutes: Optional[int] = Field(
        None, ge=0, description="Minutes available for work"
    )
    deadline: Optional[datetime] = Field(None, description="Hard deadline (UTC)")


class EnergyConstraint(BaseModel):
    """Energy/capacity constraints (for human actors)."""

    model_config = ConfigDict(extra="forbid")

    score_0_5: Optional[int] = Field(
        None, ge=0, le=5, description="Energy level 0-5"
    )
    notes: Optional[constr(max_length=500)] = Field(None, description="Additional notes")


class HealthConstraint(BaseModel):
    """Health-related constraints."""

    model_config = ConfigDict(extra="forbid")

    flags: List[str] = Field(default_factory=list, description="Health flags")
    notes: Optional[constr(max_length=500)] = Field(None, description="Additional notes")


class BudgetConstraint(BaseModel):
    """Budget constraints."""

    model_config = ConfigDict(extra="forbid")

    usd_available: Optional[float] = Field(
        None, ge=0, description="Available budget in USD"
    )
    burn_limit_usd: Optional[float] = Field(
        None, ge=0, description="Maximum spend limit in USD"
    )


class ToolsConstraint(BaseModel):
    """Tool availability constraints."""

    model_config = ConfigDict(extra="forbid")

    allowed: List[str] = Field(default_factory=list, description="Allowed tools")
    blocked: List[str] = Field(default_factory=list, description="Blocked tools")


class EnvironmentConstraint(BaseModel):
    """Environment constraints."""

    model_config = ConfigDict(extra="forbid")

    location: Optional[constr(max_length=128)] = Field(
        None, description="Physical/logical location"
    )
    connectivity: Literal["offline", "limited", "ok"] = Field(
        "ok", description="Network connectivity status"
    )
    device: Optional[constr(max_length=128)] = Field(
        None, description="Device identifier"
    )


class RiskConstraint(BaseModel):
    """Risk tolerance constraints."""

    model_config = ConfigDict(extra="forbid")

    tolerance: Literal["low", "medium", "high"] = Field(
        "medium", description="Risk tolerance level"
    )
    notes: Optional[constr(max_length=500)] = Field(None, description="Risk notes")


class Constraints(BaseModel):
    """Full constraint set for a ConstraintSnapshot."""

    model_config = ConfigDict(extra="forbid")

    time: Optional[TimeConstraint] = Field(None, description="Time constraints")
    energy: Optional[EnergyConstraint] = Field(None, description="Energy constraints")
    health: Optional[HealthConstraint] = Field(None, description="Health constraints")
    budget: Optional[BudgetConstraint] = Field(None, description="Budget constraints")
    tools: Optional[ToolsConstraint] = Field(None, description="Tool constraints")
    environment: Optional[EnvironmentConstraint] = Field(
        None, description="Environment constraints"
    )
    risk: Optional[RiskConstraint] = Field(None, description="Risk constraints")


class Acceptance(BaseModel):
    """Acceptance criteria for an Issue."""

    model_config = ConfigDict(extra="forbid")

    criteria: List[str] = Field(
        default_factory=list, description="Acceptance criteria statements"
    )
    tests_expected: Optional[List[str]] = Field(
        None, description="Expected test names/paths"
    )


class IssueRelationships(BaseModel):
    """Relationships between Issues."""

    model_config = ConfigDict(extra="forbid")

    parent: Optional[Ref] = Field(None, description="Parent issue")
    blocks: List[Ref] = Field(default_factory=list, description="Issues this blocks")
    blocked_by: List[Ref] = Field(
        default_factory=list, description="Issues blocking this"
    )
    duplicates: List[Ref] = Field(
        default_factory=list, description="Duplicate issues"
    )


class Executor(BaseModel):
    """Information about who/what is executing a Run."""

    model_config = ConfigDict(extra="forbid")

    actor: Actor = Field(..., description="The actor performing the run")
    runtime: constr(min_length=1, max_length=64) = Field(
        ..., description="Runtime environment (e.g., 'local', 'ci', 'container')"
    )
    toolchain: List[str] = Field(
        default_factory=list, description="Tools used in execution"
    )


class RunPlan(BaseModel):
    """Execution plan for a Run."""

    model_config = ConfigDict(extra="forbid")

    steps: List[str] = Field(default_factory=list, description="Planned steps")
    risk_notes: List[str] = Field(
        default_factory=list, description="Risk considerations"
    )


class Telemetry(BaseModel):
    """Execution telemetry for a Run."""

    model_config = ConfigDict(extra="forbid")

    started_at: Optional[datetime] = Field(None, description="Run start time (UTC)")
    ended_at: Optional[datetime] = Field(None, description="Run end time (UTC)")
    duration_s: Optional[float] = Field(None, ge=0, description="Duration in seconds")


class Cost(BaseModel):
    """Cost tracking for a Run."""

    model_config = ConfigDict(extra="forbid")

    usd: Optional[float] = Field(None, ge=0, description="Cost in USD")
    tokens: Optional[int] = Field(None, ge=0, description="Tokens consumed")
    compute_s: Optional[float] = Field(None, ge=0, description="Compute seconds used")


class RunOutputs(BaseModel):
    """Outputs from a Run."""

    model_config = ConfigDict(extra="forbid")

    artifacts: List[Ref] = Field(
        default_factory=list, description="References to produced artifacts"
    )
    result_summary: Optional[constr(max_length=4000)] = Field(
        None, description="Summary of results"
    )
    decision_log: List[str] = Field(
        default_factory=list, description="Key decisions made during run"
    )


class Failure(BaseModel):
    """Failure information for a Run."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["policy", "build", "test", "runtime", "dependency", "unknown"] = (
        Field(..., description="Failure category")
    )
    message: constr(min_length=1, max_length=4000) = Field(
        ..., description="Failure message"
    )


class Verification(BaseModel):
    """Verification status for an Artifact."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["unverified", "passed", "failed"] = Field(
        "unverified", description="Overall verification status"
    )
    checks: List[VerificationCheck] = Field(
        default_factory=list, description="Individual verification checks"
    )


class RepoPolicy(BaseModel):
    """Policy settings for a Repo."""

    model_config = ConfigDict(extra="forbid")

    allowed_tools: List[str] = Field(
        default_factory=list, description="Tools allowed in this repo"
    )
    secrets_profile: Optional[constr(max_length=64)] = Field(
        None, description="Secrets profile name"
    )


class DoctrineApplicability(BaseModel):
    """Defines where a DoctrineRef applies."""

    model_config = ConfigDict(extra="forbid")

    repo_refs: List[Ref] = Field(
        default_factory=list, description="Repos where this applies"
    )
    issue_types: List[str] = Field(
        default_factory=list, description="Issue types where this applies"
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags where this applies"
    )


class ContextInputs(BaseModel):
    """Input documents and data for a ContextPacket."""

    model_config = ConfigDict(extra="forbid")

    documents: List[Document] = Field(
        default_factory=list, description="Reference documents"
    )
    data_blobs: List[DataBlob] = Field(
        default_factory=list, description="Data blobs"
    )
    links: List[str] = Field(default_factory=list, description="Related links")


class RunInputs(BaseModel):
    """Inputs to a Run."""

    model_config = ConfigDict(extra="forbid")

    context_packets: List[Ref] = Field(
        default_factory=list, description="Context packets consumed"
    )
    doctrine_refs: List[Ref] = Field(
        default_factory=list, description="Doctrine refs applied"
    )
    constraint_snapshot: Optional[Ref] = Field(
        None, description="Constraints pinned at run start"
    )
