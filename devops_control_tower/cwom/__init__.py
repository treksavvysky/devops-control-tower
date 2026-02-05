"""
Canonical Work Object Model (CWOM) v0.1

CWOM provides the data contract for representing work as a system of interoperable
objects. It defines the minimal, stable schema for:

- Repo: Work container (codebase, docs base, project boundary)
- Issue: Unit of intent (what we want)
- ContextPacket: Versioned briefing (what we know + assumptions + instructions)
- ConstraintSnapshot: Operating envelope at a moment (time, money, health, policies)
- DoctrineRef: Governing rules for "how we decide / how we work"
- Run: Execution attempt (agent/human/CI doing work)
- Artifact: Output of a Run (PR, commit, report, build) with verification
- EvidencePack: Proof that a Run's outputs meet acceptance criteria

Causality Chain:
    Issue + ContextPacket + ConstraintSnapshot + DoctrineRef → Run → Artifact → EvidencePack

Spec: docs/cwom/cwom-spec-v0.1.md
"""

# Enums
from .enums import (
    ActorKind,
    ArtifactType,
    CheckStatus,
    Connectivity,
    ConstraintScope,
    CriterionStatus,
    DoctrinePriority,
    DoctrineType,
    FailureCategory,
    IssueType,
    ObjectKind,
    Priority,
    ReviewDecisionStatus,
    RiskTolerance,
    RunMode,
    Status,
    Verdict,
    VerificationStatus,
    Visibility,
)

# Primitives
from .primitives import (
    Acceptance,
    Actor,
    BudgetConstraint,
    Constraints,
    ContextInputs,
    Cost,
    DataBlob,
    DoctrineApplicability,
    Document,
    EnergyConstraint,
    EnvironmentConstraint,
    Executor,
    Failure,
    HealthConstraint,
    IssueRelationships,
    Ref,
    RepoPolicy,
    RiskConstraint,
    RunInputs,
    RunOutputs,
    RunPlan,
    Source,
    Telemetry,
    TimeConstraint,
    ToolsConstraint,
    Verification,
    VerificationCheck,
    generate_ulid,
    utc_now,
)

# Object types
from .repo import Repo, RepoCreate
from .issue import Issue, IssueCreate
from .context_packet import ContextPacket, ContextPacketCreate
from .constraint_snapshot import ConstraintSnapshot, ConstraintSnapshotCreate
from .doctrine_ref import DoctrineRef, DoctrineRefCreate
from .run import Run, RunCreate, RunUpdate
from .artifact import Artifact, ArtifactCreate
from .evidence_pack import EvidencePack, EvidencePackCreate, CriterionResult, EvidenceItem
from .review_decision import ReviewDecision, ReviewDecisionCreate, CriterionOverride

__version__ = "0.1"

__all__ = [
    # Version
    "__version__",
    # Enums
    "ObjectKind",
    "Status",
    "IssueType",
    "Priority",
    "RunMode",
    "ArtifactType",
    "VerificationStatus",
    "DoctrineType",
    "DoctrinePriority",
    "Visibility",
    "ActorKind",
    "ConstraintScope",
    "Connectivity",
    "RiskTolerance",
    "FailureCategory",
    "CheckStatus",
    # Primitives
    "Actor",
    "Source",
    "Ref",
    "Document",
    "DataBlob",
    "VerificationCheck",
    "TimeConstraint",
    "EnergyConstraint",
    "HealthConstraint",
    "BudgetConstraint",
    "ToolsConstraint",
    "EnvironmentConstraint",
    "RiskConstraint",
    "Constraints",
    "Acceptance",
    "IssueRelationships",
    "Executor",
    "RunPlan",
    "Telemetry",
    "Cost",
    "RunOutputs",
    "Failure",
    "Verification",
    "RepoPolicy",
    "DoctrineApplicability",
    "ContextInputs",
    "RunInputs",
    "generate_ulid",
    "utc_now",
    # Object types
    "Repo",
    "RepoCreate",
    "Issue",
    "IssueCreate",
    "ContextPacket",
    "ContextPacketCreate",
    "ConstraintSnapshot",
    "ConstraintSnapshotCreate",
    "DoctrineRef",
    "DoctrineRefCreate",
    "Run",
    "RunCreate",
    "RunUpdate",
    "Artifact",
    "ArtifactCreate",
    "EvidencePack",
    "EvidencePackCreate",
    "CriterionResult",
    "EvidenceItem",
    "ReviewDecision",
    "ReviewDecisionCreate",
    "CriterionOverride",
    "Verdict",
    "CriterionStatus",
    "ReviewDecisionStatus",
]
