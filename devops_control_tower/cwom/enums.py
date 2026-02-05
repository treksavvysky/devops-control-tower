"""
CWOM v0.1 Canonical Enums.

These enums define the allowed values for various fields across CWOM objects.
Adapters MUST map tool-specific values into these canonical sets.
"""

from enum import Enum


class ObjectKind(str, Enum):
    """Valid CWOM object kinds (v0.1)."""

    REPO = "Repo"
    ISSUE = "Issue"
    CONTEXT_PACKET = "ContextPacket"
    RUN = "Run"
    ARTIFACT = "Artifact"
    CONSTRAINT_SNAPSHOT = "ConstraintSnapshot"
    DOCTRINE_REF = "DoctrineRef"
    EVIDENCE_PACK = "EvidencePack"


class Status(str, Enum):
    """Canonical status shared across objects where applicable."""

    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class IssueType(str, Enum):
    """Types of issues/work items."""

    FEATURE = "feature"
    BUG = "bug"
    CHORE = "chore"
    RESEARCH = "research"
    OPS = "ops"
    DOC = "doc"
    INCIDENT = "incident"


class Priority(str, Enum):
    """Priority levels."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class RunMode(str, Enum):
    """How a Run is executed."""

    HUMAN = "human"
    AGENT = "agent"
    HYBRID = "hybrid"
    SYSTEM = "system"


class ArtifactType(str, Enum):
    """Types of artifacts produced by Runs."""

    CODE_PATCH = "code_patch"
    COMMIT = "commit"
    PR = "pr"
    BUILD = "build"
    CONTAINER_IMAGE = "container_image"
    DOC = "doc"
    REPORT = "report"
    DATASET = "dataset"
    LOG = "log"
    TRACE = "trace"
    BINARY = "binary"
    LINK = "link"


class VerificationStatus(str, Enum):
    """Artifact verification status."""

    UNVERIFIED = "unverified"
    PASSED = "passed"
    FAILED = "failed"


class DoctrineType(str, Enum):
    """Types of doctrine/governance rules."""

    PRINCIPLE = "principle"
    POLICY = "policy"
    PROCEDURE = "procedure"
    HEURISTIC = "heuristic"
    PATTERN = "pattern"


class DoctrinePriority(str, Enum):
    """How binding a doctrine is."""

    MUST = "must"
    SHOULD = "should"
    MAY = "may"


class Visibility(str, Enum):
    """Repository visibility levels."""

    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


class ActorKind(str, Enum):
    """Types of actors that can perform work."""

    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class ConstraintScope(str, Enum):
    """Scope of a constraint snapshot."""

    PERSONAL = "personal"
    REPO = "repo"
    ORG = "org"
    SYSTEM = "system"
    RUN = "run"


class Connectivity(str, Enum):
    """Network connectivity status."""

    OFFLINE = "offline"
    LIMITED = "limited"
    OK = "ok"


class RiskTolerance(str, Enum):
    """Risk tolerance levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FailureCategory(str, Enum):
    """Categories of Run failures."""

    POLICY = "policy"
    BUILD = "build"
    TEST = "test"
    RUNTIME = "runtime"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


class CheckStatus(str, Enum):
    """Status of individual verification checks."""

    PASSED = "passed"
    FAILED = "failed"
    UNVERIFIED = "unverified"


class Verdict(str, Enum):
    """Evidence pack verdict (proof outcome)."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    PENDING = "pending"


class CriterionStatus(str, Enum):
    """Status of individual acceptance criterion evaluation."""

    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNVERIFIED = "unverified"  # v0: can't verify without LLM
    SKIPPED = "skipped"
