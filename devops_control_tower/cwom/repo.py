"""
CWOM v0.1 Repo Schema.

Represents a work container (codebase/project/docs boundary).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import Visibility
from .primitives import Actor, Ref, RepoPolicy, Source, generate_ulid, utc_now


class Repo(BaseModel):
    """A work container: codebase, docs base, or project boundary.

    Invariants:
    - slug MUST remain stable even if name changes.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["Repo"] = Field(default="Repo", description="Object type identifier")
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # Core fields
    name: constr(min_length=1, max_length=256) = Field(
        ..., description="Repository name"
    )
    slug: constr(min_length=1, max_length=256) = Field(
        ..., description="Stable identifier (does not change if name changes)"
    )
    source: Source = Field(..., description="External system linkage")
    default_branch: constr(min_length=1, max_length=128) = Field(
        "main", description="Default branch name"
    )
    visibility: Visibility = Field(
        Visibility.PRIVATE, description="Repository visibility"
    )

    # Ownership (simplified for v0.1)
    owners: List[Actor] = Field(
        default_factory=list, description="Repository owners"
    )

    # Policy
    policy: Optional[RepoPolicy] = Field(None, description="Repository policy settings")

    # Links and metadata
    links: List[str] = Field(default_factory=list, description="Related links")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    meta: Dict[str, Any] = Field(
        default_factory=dict, description="Freeform metadata (namespaced keys recommended)"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=utc_now, description="Creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update timestamp (UTC)"
    )


class RepoCreate(BaseModel):
    """Schema for creating a new Repo."""

    model_config = ConfigDict(extra="forbid")

    name: constr(min_length=1, max_length=256)
    slug: constr(min_length=1, max_length=256)
    source: Source
    default_branch: constr(min_length=1, max_length=128) = "main"
    visibility: Visibility = Visibility.PRIVATE
    owners: List[Actor] = Field(default_factory=list)
    policy: Optional[RepoPolicy] = None
    links: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
