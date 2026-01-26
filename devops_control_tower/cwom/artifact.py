"""
CWOM v0.1 Artifact Schema.

Represents an output produced by a Run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import ArtifactType
from .primitives import Ref, Verification, generate_ulid, utc_now


class Artifact(BaseModel):
    """An output produced by a Run: PR, commit, report, build, etc.

    Invariants:
    - Artifact MUST reference the Run that produced it.
    - Artifact SHOULD be retrievable by uri and/or verifiable by digest.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["Artifact"] = Field(
        default="Artifact", description="Object type identifier"
    )
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # References
    produced_by: Ref = Field(..., description="Reference to the Run that produced this")
    for_issue: Ref = Field(..., description="Reference to the Issue this is for")

    # Content
    type: ArtifactType = Field(..., description="Type of artifact")
    title: constr(min_length=1, max_length=512) = Field(
        ..., description="Artifact title"
    )
    uri: constr(min_length=1, max_length=2000) = Field(
        ..., description="URI to the artifact"
    )

    # Verification
    digest: Optional[constr(min_length=1, max_length=128)] = Field(
        None, description="Content hash (sha256, git hash, etc.)"
    )
    media_type: Optional[constr(min_length=1, max_length=128)] = Field(
        None, description="MIME type"
    )
    size_bytes: Optional[int] = Field(None, ge=0, description="Size in bytes")
    preview: Optional[constr(max_length=4000)] = Field(
        None, description="Preview/summary of content"
    )

    # Verification status
    verification: Verification = Field(
        default_factory=Verification, description="Verification status and checks"
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


class ArtifactCreate(BaseModel):
    """Schema for creating a new Artifact."""

    model_config = ConfigDict(extra="forbid")

    produced_by: Ref
    for_issue: Ref
    type: ArtifactType
    title: constr(min_length=1, max_length=512)
    uri: constr(min_length=1, max_length=2000)
    digest: Optional[constr(min_length=1, max_length=128)] = None
    media_type: Optional[constr(min_length=1, max_length=128)] = None
    size_bytes: Optional[int] = Field(None, ge=0)
    preview: Optional[constr(max_length=4000)] = None
    verification: Verification = Field(default_factory=Verification)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
