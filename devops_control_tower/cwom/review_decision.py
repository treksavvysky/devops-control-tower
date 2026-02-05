"""
CWOM v0.1 ReviewDecision Schema.

Represents a review decision for an EvidencePack, determining whether
the work meets standards for completion.

v0: Internal review only (no GitHub integration)
v1: GitHub PR integration with merge gates
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import CriterionStatus, ReviewDecisionStatus
from .primitives import Actor, Ref, generate_ulid, utc_now


class CriterionOverride(BaseModel):
    """Override for a specific acceptance criterion evaluation."""

    model_config = ConfigDict(extra="forbid")

    criterion_index: int = Field(..., ge=0, description="Index of criterion being overridden")
    original_status: CriterionStatus = Field(
        ..., description="Original automated status from EvidencePack"
    )
    override_status: CriterionStatus = Field(
        ..., description="Reviewer's override status"
    )
    reason: str = Field(..., description="Why this override was necessary")


class ReviewDecision(BaseModel):
    """Review decision for an EvidencePack.

    After Prove creates an EvidencePack, Step 5 (Review) determines whether
    the work meets quality/policy standards before marking as done.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["ReviewDecision"] = Field(
        default="ReviewDecision", description="Object type identifier"
    )
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # References
    for_evidence_pack: Ref = Field(
        ..., description="Reference to the EvidencePack being reviewed"
    )
    for_run: Ref = Field(..., description="Reference to the Run")
    for_issue: Ref = Field(..., description="Reference to the Issue")

    # Decision
    reviewer: Actor = Field(..., description="Who performed the review")
    decision: ReviewDecisionStatus = Field(..., description="Approval decision")
    decision_reason: str = Field(..., description="Explanation of decision")
    reviewed_at: datetime = Field(
        default_factory=utc_now, description="When review was performed"
    )

    # Overrides
    criteria_overrides: List[CriterionOverride] = Field(
        default_factory=list,
        description="Per-criterion overrides by reviewer",
    )

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Freeform metadata",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=utc_now, description="Creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update timestamp (UTC)"
    )


class ReviewDecisionCreate(BaseModel):
    """Schema for creating a new ReviewDecision."""

    model_config = ConfigDict(extra="forbid")

    for_evidence_pack: Ref
    for_run: Ref
    for_issue: Ref
    reviewer: Actor
    decision: ReviewDecisionStatus
    decision_reason: str
    criteria_overrides: List[CriterionOverride] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
