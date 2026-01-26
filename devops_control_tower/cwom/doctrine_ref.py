"""
CWOM v0.1 DoctrineRef Schema.

Represents governing doctrine: principles, policies, procedures, heuristics, patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import DoctrinePriority, DoctrineType
from .primitives import DoctrineApplicability, generate_ulid, utc_now


class DoctrineRef(BaseModel):
    """Governing doctrine: how we decide / how we work.

    Invariants:
    - DoctrineRef SHOULD be versioned.
    - Consumers MUST reference a specific version when reproducibility matters.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["DoctrineRef"] = Field(
        default="DoctrineRef", description="Object type identifier"
    )
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # Core fields
    namespace: constr(min_length=1, max_length=128) = Field(
        ..., description="Namespace for grouping (e.g., 'org/security', 'team/quality')"
    )
    name: constr(min_length=1, max_length=256) = Field(
        ..., description="Doctrine name"
    )
    version: constr(min_length=1, max_length=64) = Field(
        ..., description="Version string"
    )
    type: DoctrineType = Field(..., description="Type of doctrine")
    priority: DoctrinePriority = Field(
        DoctrinePriority.SHOULD, description="How binding this doctrine is"
    )

    # Content
    statement: constr(min_length=1, max_length=4000) = Field(
        ..., description="The doctrine statement"
    )
    rationale: Optional[constr(max_length=4000)] = Field(
        None, description="Why this doctrine exists"
    )

    # References
    links: List[str] = Field(
        default_factory=list, description="Links to supporting documentation"
    )

    # Applicability
    applicability: DoctrineApplicability = Field(
        default_factory=DoctrineApplicability,
        description="Where this doctrine applies",
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


class DoctrineRefCreate(BaseModel):
    """Schema for creating a new DoctrineRef."""

    model_config = ConfigDict(extra="forbid")

    namespace: constr(min_length=1, max_length=128)
    name: constr(min_length=1, max_length=256)
    version: constr(min_length=1, max_length=64)
    type: DoctrineType
    priority: DoctrinePriority = DoctrinePriority.SHOULD
    statement: constr(min_length=1, max_length=4000)
    rationale: Optional[constr(max_length=4000)] = None
    links: List[str] = Field(default_factory=list)
    applicability: DoctrineApplicability = Field(default_factory=DoctrineApplicability)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
