"""
CWOM v0.1 ContextPacket Schema.

Represents a versioned briefing bundle for a Run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .primitives import ContextInputs, Ref, generate_ulid, utc_now


class ContextPacket(BaseModel):
    """A versioned briefing: what we know + assumptions + instructions.

    Invariants:
    - ContextPacket is immutable once created.
    - New info requires creating a new ContextPacket with a new version.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["ContextPacket"] = Field(
        default="ContextPacket", description="Object type identifier"
    )
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # Issue reference
    for_issue: Ref = Field(..., description="Reference to the Issue this is for")

    # Version
    version: constr(min_length=1, max_length=64) = Field(
        ..., description="Version string (e.g., '1.0', '2024-01-15-a')"
    )

    # Content
    summary: constr(min_length=1, max_length=4000) = Field(
        ..., description="Summary of the context"
    )
    inputs: ContextInputs = Field(
        default_factory=ContextInputs, description="Input documents and data"
    )

    # Briefing content
    assumptions: List[str] = Field(
        default_factory=list, description="Assumptions being made"
    )
    open_questions: List[str] = Field(
        default_factory=list, description="Unresolved questions"
    )
    instructions: constr(max_length=8000) = Field(
        "", description="Instructions for the executor"
    )

    # CWOM references
    doctrine_refs: List[Ref] = Field(
        default_factory=list, description="Doctrine references applicable to this context"
    )
    constraint_snapshot: Optional[Ref] = Field(
        None, description="Constraint snapshot pinned at packet creation"
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


class ContextPacketCreate(BaseModel):
    """Schema for creating a new ContextPacket."""

    model_config = ConfigDict(extra="forbid")

    for_issue: Ref
    version: constr(min_length=1, max_length=64)
    summary: constr(min_length=1, max_length=4000)
    inputs: ContextInputs = Field(default_factory=ContextInputs)
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    instructions: constr(max_length=8000) = ""
    doctrine_refs: List[Ref] = Field(default_factory=list)
    constraint_snapshot: Optional[Ref] = None
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
