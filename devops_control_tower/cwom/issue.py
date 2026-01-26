"""
CWOM v0.1 Issue Schema.

Represents a unit of intent: a problem to solve or outcome to produce.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import IssueType, Priority, Status
from .primitives import (
    Acceptance,
    Actor,
    IssueRelationships,
    Ref,
    generate_ulid,
    utc_now,
)


class Issue(BaseModel):
    """A unit of intent: what we want to achieve.

    Invariants:
    - Issue is intent, not execution.
    - Runs SHOULD link back to Issue; Issue MAY store Run refs for convenience.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["Issue"] = Field(
        default="Issue", description="Object type identifier"
    )
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # Repository reference
    repo: Ref = Field(..., description="Reference to the containing Repo")

    # Core fields
    title: constr(min_length=1, max_length=512) = Field(
        ..., description="Issue title"
    )
    description: constr(max_length=16000) = Field(
        "", description="Detailed description"
    )
    type: IssueType = Field(..., description="Issue type")
    priority: Priority = Field(Priority.P2, description="Priority level")
    status: Status = Field(Status.PLANNED, description="Current status")

    # People
    assignees: List[Actor] = Field(default_factory=list, description="Assigned actors")
    watchers: List[Actor] = Field(default_factory=list, description="Watching actors")

    # CWOM references
    doctrine_refs: List[Ref] = Field(
        default_factory=list, description="Governing doctrine references"
    )
    constraints: List[Ref] = Field(
        default_factory=list, description="Constraint snapshots (typically 'current')"
    )
    context_packets: List[Ref] = Field(
        default_factory=list, description="Context packets for this issue"
    )

    # Acceptance criteria
    acceptance: Acceptance = Field(
        default_factory=Acceptance, description="Acceptance criteria"
    )

    # Relationships
    relationships: IssueRelationships = Field(
        default_factory=IssueRelationships, description="Issue relationships"
    )

    # Runs (convenience backlink)
    runs: List[Ref] = Field(
        default_factory=list, description="Runs targeting this issue"
    )

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Freeform metadata (namespaced keys recommended)",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=utc_now, description="Creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update timestamp (UTC)"
    )


class IssueCreate(BaseModel):
    """Schema for creating a new Issue."""

    model_config = ConfigDict(extra="forbid")

    repo: Ref
    title: constr(min_length=1, max_length=512)
    description: constr(max_length=16000) = ""
    type: IssueType
    priority: Priority = Priority.P2
    status: Status = Status.PLANNED
    assignees: List[Actor] = Field(default_factory=list)
    watchers: List[Actor] = Field(default_factory=list)
    doctrine_refs: List[Ref] = Field(default_factory=list)
    constraints: List[Ref] = Field(default_factory=list)
    context_packets: List[Ref] = Field(default_factory=list)
    acceptance: Acceptance = Field(default_factory=Acceptance)
    relationships: IssueRelationships = Field(default_factory=IssueRelationships)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
