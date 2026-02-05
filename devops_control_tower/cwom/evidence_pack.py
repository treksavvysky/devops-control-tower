"""
CWOM v0.1 EvidencePack Schema.

Represents proof that a Run's outputs meet the acceptance criteria.
The EvidencePack is the "judgment" step - did the work actually succeed?
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import CriterionStatus, Verdict
from .primitives import Actor, Ref, generate_ulid, utc_now


class CriterionResult(BaseModel):
    """Result of evaluating a single acceptance criterion."""

    model_config = ConfigDict(extra="forbid")

    # The criterion text (from task's acceptance_criteria)
    criterion: str = Field(..., description="The acceptance criterion being evaluated")
    index: int = Field(..., ge=0, description="Index in the original criteria list")

    # Evaluation result
    status: CriterionStatus = Field(
        ..., description="Whether this criterion was satisfied"
    )
    reason: Optional[str] = Field(
        None, description="Explanation of the evaluation result"
    )

    # Evidence supporting this evaluation
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="Paths to evidence files supporting this evaluation",
    )


class EvidenceItem(BaseModel):
    """An item of evidence collected to prove work completion."""

    model_config = ConfigDict(extra="forbid")

    # What was required
    requirement: str = Field(
        ..., description="The evidence requirement (from task's evidence_requirements)"
    )
    index: int = Field(..., ge=0, description="Index in the original requirements list")

    # What was found
    found: bool = Field(..., description="Whether this evidence was found")
    artifact_uri: Optional[str] = Field(
        None, description="URI to the artifact that satisfies this requirement"
    )
    artifact_type: Optional[str] = Field(
        None, description="Type of artifact found"
    )
    notes: Optional[str] = Field(
        None, description="Additional notes about the evidence"
    )


class EvidencePack(BaseModel):
    """Proof that a Run's outputs meet acceptance criteria.

    The EvidencePack is created after a Run completes, evaluating:
    1. Did the run complete successfully?
    2. Are all required evidence artifacts present?
    3. Do the outputs satisfy acceptance criteria?

    v0: Automated checks only (evidence existence, run status)
    v1+: LLM-based evaluation of acceptance criteria
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["EvidencePack"] = Field(
        default="EvidencePack", description="Object type identifier"
    )
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # References
    for_run: Ref = Field(..., description="Reference to the Run being evaluated")
    for_issue: Ref = Field(..., description="Reference to the Issue")

    # Verdict
    verdict: Verdict = Field(..., description="Overall proof outcome")
    verdict_reason: str = Field(..., description="Explanation of the verdict")

    # Evaluation details
    evaluated_at: datetime = Field(
        default_factory=utc_now, description="When the evaluation was performed"
    )
    evaluated_by: Actor = Field(..., description="Who/what performed the evaluation")

    # Results
    criteria_results: List[CriterionResult] = Field(
        default_factory=list,
        description="Per-criterion evaluation results",
    )
    evidence_collected: List[EvidenceItem] = Field(
        default_factory=list,
        description="Evidence items found",
    )
    evidence_missing: List[str] = Field(
        default_factory=list,
        description="Evidence requirements that could not be satisfied",
    )

    # Checks performed
    checks_passed: int = Field(
        default=0, ge=0, description="Number of checks that passed"
    )
    checks_failed: int = Field(
        default=0, ge=0, description="Number of checks that failed"
    )
    checks_skipped: int = Field(
        default=0, ge=0, description="Number of checks skipped (unverifiable in v0)"
    )

    # Storage
    evidence_uri: Optional[str] = Field(
        None,
        description="URI to evidence folder in trace storage",
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


class EvidencePackCreate(BaseModel):
    """Schema for creating a new EvidencePack."""

    model_config = ConfigDict(extra="forbid")

    for_run: Ref
    for_issue: Ref
    verdict: Verdict
    verdict_reason: str
    evaluated_by: Actor
    criteria_results: List[CriterionResult] = Field(default_factory=list)
    evidence_collected: List[EvidenceItem] = Field(default_factory=list)
    evidence_missing: List[str] = Field(default_factory=list)
    checks_passed: int = Field(default=0, ge=0)
    checks_failed: int = Field(default=0, ge=0)
    checks_skipped: int = Field(default=0, ge=0)
    evidence_uri: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
