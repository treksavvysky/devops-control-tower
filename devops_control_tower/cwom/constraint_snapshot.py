"""
CWOM v0.1 ConstraintSnapshot Schema.

Represents point-in-time operational constraints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import ConstraintScope
from .primitives import Actor, Constraints, generate_ulid, utc_now


class ConstraintSnapshot(BaseModel):
    """Point-in-time operational constraints.

    Invariants:
    - ConstraintSnapshot is immutable once created.
    - To update constraints, create a new snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["ConstraintSnapshot"] = Field(
        default="ConstraintSnapshot", description="Object type identifier"
    )
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # Scope and timing
    scope: ConstraintScope = Field(..., description="Scope of these constraints")
    captured_at: datetime = Field(
        default_factory=utc_now, description="When constraints were captured (UTC)"
    )

    # Owner
    owner: Actor = Field(..., description="Actor who owns these constraints")

    # Constraints
    constraints: Constraints = Field(
        default_factory=Constraints, description="The actual constraints"
    )

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Freeform metadata (namespaced keys recommended)",
    )


class ConstraintSnapshotCreate(BaseModel):
    """Schema for creating a new ConstraintSnapshot."""

    model_config = ConfigDict(extra="forbid")

    scope: ConstraintScope
    owner: Actor
    constraints: Constraints = Field(default_factory=Constraints)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
