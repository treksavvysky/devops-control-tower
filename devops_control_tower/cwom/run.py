"""
CWOM v0.1 Run Schema.

Represents one execution attempt against an Issue.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

from .enums import RunMode, Status
from .primitives import (
    Cost,
    Executor,
    Failure,
    Ref,
    RunInputs,
    RunOutputs,
    RunPlan,
    Telemetry,
    generate_ulid,
    utc_now,
)


class Run(BaseModel):
    """One execution attempt against an Issue.

    Invariants:
    - A Run MUST reference an Issue and Repo.
    - A Run SHOULD reference at least one ContextPacket once it transitions to running.
    - A Run SHOULD pin a ConstraintSnapshot at start for auditability.
    - Run inputs/outputs SHOULD be treated as append-only; supersede by creating a new Run.
    """

    model_config = ConfigDict(extra="forbid")

    # Object identity
    kind: Literal["Run"] = Field(default="Run", description="Object type identifier")
    id: constr(min_length=1, max_length=128) = Field(
        default_factory=generate_ulid, description="Globally unique identifier (ULID)"
    )

    # References
    for_issue: Ref = Field(..., description="Reference to the Issue being worked")
    repo: Ref = Field(..., description="Reference to the Repo")

    # Status
    status: Status = Field(Status.PLANNED, description="Current run status")
    mode: RunMode = Field(..., description="How this run is being executed")

    # Executor
    executor: Executor = Field(..., description="Who/what is executing this run")

    # Inputs
    inputs: RunInputs = Field(
        default_factory=RunInputs, description="Inputs to this run"
    )

    # Plan
    plan: RunPlan = Field(default_factory=RunPlan, description="Execution plan")

    # Telemetry
    telemetry: Telemetry = Field(
        default_factory=Telemetry, description="Execution telemetry"
    )

    # Cost
    cost: Cost = Field(default_factory=Cost, description="Cost tracking")

    # Outputs
    outputs: RunOutputs = Field(default_factory=RunOutputs, description="Run outputs")

    # Failure (if failed)
    failure: Optional[Failure] = Field(
        None, description="Failure information (if run failed)"
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


class RunCreate(BaseModel):
    """Schema for creating a new Run."""

    model_config = ConfigDict(extra="forbid")

    for_issue: Ref
    repo: Ref
    mode: RunMode
    executor: Executor
    inputs: RunInputs = Field(default_factory=RunInputs)
    plan: RunPlan = Field(default_factory=RunPlan)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class RunUpdate(BaseModel):
    """Schema for updating a Run (status, outputs, telemetry)."""

    model_config = ConfigDict(extra="forbid")

    status: Optional[Status] = None
    telemetry: Optional[Telemetry] = None
    cost: Optional[Cost] = None
    outputs: Optional[RunOutputs] = None
    failure: Optional[Failure] = None
