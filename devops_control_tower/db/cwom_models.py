"""
CWOM v0.1 SQLAlchemy Database Models.

These models map the Pydantic CWOM schemas to database tables.
Following the CWOM spec guidelines:
- Tables for each object kind
- Join tables for many-to-many refs
- meta stored as JSON
- Do not store primary relationships solely as JSON arrays
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


# =============================================================================
# Join Tables for Many-to-Many Relationships
# =============================================================================

# Issue <-> ContextPacket (convenience backlink from Issue)
issue_context_packets = Table(
    "cwom_issue_context_packets",
    Base.metadata,
    Column("issue_id", String(128), ForeignKey("cwom_issues.id"), primary_key=True),
    Column(
        "context_packet_id",
        String(128),
        ForeignKey("cwom_context_packets.id"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), default=func.now()),
)

# Issue <-> DoctrineRef
issue_doctrine_refs = Table(
    "cwom_issue_doctrine_refs",
    Base.metadata,
    Column("issue_id", String(128), ForeignKey("cwom_issues.id"), primary_key=True),
    Column(
        "doctrine_ref_id",
        String(128),
        ForeignKey("cwom_doctrine_refs.id"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), default=func.now()),
)

# Issue <-> ConstraintSnapshot (Issues can reference multiple constraint snapshots)
issue_constraint_snapshots = Table(
    "cwom_issue_constraint_snapshots",
    Base.metadata,
    Column("issue_id", String(128), ForeignKey("cwom_issues.id"), primary_key=True),
    Column(
        "constraint_snapshot_id",
        String(128),
        ForeignKey("cwom_constraint_snapshots.id"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), default=func.now()),
)

# Run <-> ContextPacket (Runs consume context packets)
run_context_packets = Table(
    "cwom_run_context_packets",
    Base.metadata,
    Column("run_id", String(128), ForeignKey("cwom_runs.id"), primary_key=True),
    Column(
        "context_packet_id",
        String(128),
        ForeignKey("cwom_context_packets.id"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), default=func.now()),
)

# Run <-> DoctrineRef (Runs apply doctrine refs)
run_doctrine_refs = Table(
    "cwom_run_doctrine_refs",
    Base.metadata,
    Column("run_id", String(128), ForeignKey("cwom_runs.id"), primary_key=True),
    Column(
        "doctrine_ref_id",
        String(128),
        ForeignKey("cwom_doctrine_refs.id"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), default=func.now()),
)

# ContextPacket <-> DoctrineRef
context_packet_doctrine_refs = Table(
    "cwom_context_packet_doctrine_refs",
    Base.metadata,
    Column(
        "context_packet_id",
        String(128),
        ForeignKey("cwom_context_packets.id"),
        primary_key=True,
    ),
    Column(
        "doctrine_ref_id",
        String(128),
        ForeignKey("cwom_doctrine_refs.id"),
        primary_key=True,
    ),
    Column("created_at", DateTime(timezone=True), default=func.now()),
)


# =============================================================================
# CWOM Enums as Database Enums
# =============================================================================

# These mirror devops_control_tower/cwom/enums.py
cwom_object_kind_enum = Enum(
    "Repo",
    "Issue",
    "ContextPacket",
    "Run",
    "Artifact",
    "ConstraintSnapshot",
    "DoctrineRef",
    name="cwom_object_kind",
)

cwom_status_enum = Enum(
    "planned",
    "ready",
    "running",
    "blocked",
    "done",
    "failed",
    "canceled",
    name="cwom_status",
)

cwom_issue_type_enum = Enum(
    "feature",
    "bug",
    "chore",
    "research",
    "ops",
    "doc",
    "incident",
    name="cwom_issue_type",
)

cwom_priority_enum = Enum(
    "P0", "P1", "P2", "P3", "P4", name="cwom_priority"
)

cwom_run_mode_enum = Enum(
    "human", "agent", "hybrid", "system", name="cwom_run_mode"
)

cwom_artifact_type_enum = Enum(
    "code_patch",
    "commit",
    "pr",
    "build",
    "container_image",
    "doc",
    "report",
    "dataset",
    "log",
    "trace",
    "binary",
    "link",
    name="cwom_artifact_type",
)

cwom_verification_status_enum = Enum(
    "unverified", "passed", "failed", name="cwom_verification_status"
)

cwom_doctrine_type_enum = Enum(
    "principle", "policy", "procedure", "heuristic", "pattern",
    name="cwom_doctrine_type",
)

cwom_doctrine_priority_enum = Enum(
    "must", "should", "may", name="cwom_doctrine_priority"
)

cwom_visibility_enum = Enum(
    "public", "private", "internal", name="cwom_visibility"
)

cwom_actor_kind_enum = Enum(
    "human", "agent", "system", name="cwom_actor_kind"
)

cwom_constraint_scope_enum = Enum(
    "personal", "repo", "org", "system", "run", name="cwom_constraint_scope"
)


# =============================================================================
# CWOM Database Models
# =============================================================================


class CWOMRepoModel(Base):
    """SQLAlchemy model for CWOM Repo objects."""

    __tablename__ = "cwom_repos"

    # Object identity (ULID string)
    id = Column(String(128), primary_key=True)
    kind = Column(String(20), nullable=False, default="Repo")

    # Trace ID for unified traceability (Sprint-0)
    trace_id = Column(String(36), nullable=True, index=True)

    # Core fields
    name = Column(String(256), nullable=False, index=True)
    slug = Column(String(256), nullable=False, unique=True, index=True)
    default_branch = Column(String(128), nullable=False, default="main")
    visibility = Column(cwom_visibility_enum, nullable=False, default="private")

    # Source (external system linkage) - stored as JSON
    source = Column(JSON, nullable=False)

    # Ownership - stored as JSON array of Actor objects
    owners = Column(JSON, nullable=False, default=list)

    # Policy - stored as JSON
    policy = Column(JSON, nullable=True)

    # Links and metadata
    links = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    issues = relationship("CWOMIssueModel", back_populates="repo_obj")

    # Indexes
    __table_args__ = (
        Index("ix_cwom_repos_visibility", "visibility"),
        Index("ix_cwom_repos_created_at", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary matching CWOM Pydantic schema."""
        return {
            "kind": self.kind,
            "id": self.id,
            "trace_id": self.trace_id,
            "name": self.name,
            "slug": self.slug,
            "source": self.source,
            "default_branch": self.default_branch,
            "visibility": self.visibility,
            "owners": self.owners,
            "policy": self.policy,
            "links": self.links,
            "tags": self.tags,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CWOMIssueModel(Base):
    """SQLAlchemy model for CWOM Issue objects."""

    __tablename__ = "cwom_issues"

    # Object identity (ULID string)
    id = Column(String(128), primary_key=True)
    kind = Column(String(20), nullable=False, default="Issue")

    # Trace ID for unified traceability (Sprint-0)
    trace_id = Column(String(36), nullable=True, index=True)

    # Repository reference (foreign key)
    repo_id = Column(String(128), ForeignKey("cwom_repos.id"), nullable=False, index=True)
    repo_kind = Column(String(20), nullable=False, default="Repo")
    repo_role = Column(String(64), nullable=True)

    # Core fields
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False, default="")
    type = Column(cwom_issue_type_enum, nullable=False, index=True)
    priority = Column(cwom_priority_enum, nullable=False, default="P2", index=True)
    status = Column(cwom_status_enum, nullable=False, default="planned", index=True)

    # People - stored as JSON arrays of Actor objects
    assignees = Column(JSON, nullable=False, default=list)
    watchers = Column(JSON, nullable=False, default=list)

    # Acceptance criteria - stored as JSON
    acceptance = Column(JSON, nullable=False, default=dict)

    # Relationships (Issue relationships like parent, blocks, etc.)
    relationships = Column(JSON, nullable=False, default=dict)

    # Runs backlink - stored as JSON array of Ref objects
    runs = Column(JSON, nullable=False, default=list)

    # Metadata
    tags = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    # SQLAlchemy Relationships
    repo_obj = relationship("CWOMRepoModel", back_populates="issues")
    context_packets = relationship(
        "CWOMContextPacketModel",
        secondary=issue_context_packets,
        back_populates="issues",
    )
    doctrine_refs_rel = relationship(
        "CWOMDoctrineRefModel",
        secondary=issue_doctrine_refs,
        back_populates="issues",
    )
    constraint_snapshots = relationship(
        "CWOMConstraintSnapshotModel",
        secondary=issue_constraint_snapshots,
        back_populates="issues",
    )
    runs_rel = relationship("CWOMRunModel", back_populates="issue_obj")

    # Indexes
    __table_args__ = (
        Index("ix_cwom_issues_type_status", "type", "status"),
        Index("ix_cwom_issues_priority_status", "priority", "status"),
        Index("ix_cwom_issues_created_at", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary matching CWOM Pydantic schema."""
        return {
            "kind": self.kind,
            "id": self.id,
            "trace_id": self.trace_id,
            "repo": {
                "kind": self.repo_kind,
                "id": self.repo_id,
                "role": self.repo_role,
            },
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "status": self.status,
            "assignees": self.assignees,
            "watchers": self.watchers,
            "doctrine_refs": [
                {"kind": "DoctrineRef", "id": dr.id}
                for dr in self.doctrine_refs_rel
            ] if self.doctrine_refs_rel else [],
            "constraints": [
                {"kind": "ConstraintSnapshot", "id": cs.id}
                for cs in self.constraint_snapshots
            ] if self.constraint_snapshots else [],
            "context_packets": [
                {"kind": "ContextPacket", "id": cp.id}
                for cp in self.context_packets
            ] if self.context_packets else [],
            "acceptance": self.acceptance,
            "relationships": self.relationships,
            "runs": self.runs,
            "tags": self.tags,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CWOMContextPacketModel(Base):
    """SQLAlchemy model for CWOM ContextPacket objects.

    Note: ContextPackets are immutable. Updates create new packets.
    """

    __tablename__ = "cwom_context_packets"

    # Object identity (ULID string)
    id = Column(String(128), primary_key=True)
    kind = Column(String(20), nullable=False, default="ContextPacket")

    # Trace ID for unified traceability (Sprint-0)
    trace_id = Column(String(36), nullable=True, index=True)

    # Issue reference (foreign key)
    for_issue_id = Column(
        String(128), ForeignKey("cwom_issues.id"), nullable=False, index=True
    )
    for_issue_kind = Column(String(20), nullable=False, default="Issue")
    for_issue_role = Column(String(64), nullable=True)

    # Version (index defined in __table_args__)
    version = Column(String(64), nullable=False)

    # Content
    summary = Column(Text, nullable=False)
    inputs = Column(JSON, nullable=False, default=dict)  # ContextInputs as JSON
    assumptions = Column(JSON, nullable=False, default=list)
    open_questions = Column(JSON, nullable=False, default=list)
    instructions = Column(Text, nullable=False, default="")

    # Constraint snapshot reference (optional foreign key)
    constraint_snapshot_id = Column(
        String(128), ForeignKey("cwom_constraint_snapshots.id"), nullable=True
    )

    # Metadata
    tags = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    # SQLAlchemy Relationships
    issues = relationship(
        "CWOMIssueModel",
        secondary=issue_context_packets,
        back_populates="context_packets",
    )
    doctrine_refs_rel = relationship(
        "CWOMDoctrineRefModel",
        secondary=context_packet_doctrine_refs,
        back_populates="context_packets",
    )
    constraint_snapshot_obj = relationship(
        "CWOMConstraintSnapshotModel", foreign_keys=[constraint_snapshot_id]
    )
    runs = relationship(
        "CWOMRunModel",
        secondary=run_context_packets,
        back_populates="context_packets",
    )

    # Indexes
    __table_args__ = (
        Index("ix_cwom_context_packets_version", "version"),
        Index("ix_cwom_context_packets_created_at", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary matching CWOM Pydantic schema."""
        return {
            "kind": self.kind,
            "id": self.id,
            "trace_id": self.trace_id,
            "for_issue": {
                "kind": self.for_issue_kind,
                "id": self.for_issue_id,
                "role": self.for_issue_role,
            },
            "version": self.version,
            "summary": self.summary,
            "inputs": self.inputs,
            "assumptions": self.assumptions,
            "open_questions": self.open_questions,
            "instructions": self.instructions,
            "doctrine_refs": [
                {"kind": "DoctrineRef", "id": dr.id}
                for dr in self.doctrine_refs_rel
            ] if self.doctrine_refs_rel else [],
            "constraint_snapshot": {
                "kind": "ConstraintSnapshot",
                "id": self.constraint_snapshot_id,
            } if self.constraint_snapshot_id else None,
            "tags": self.tags,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CWOMConstraintSnapshotModel(Base):
    """SQLAlchemy model for CWOM ConstraintSnapshot objects.

    Note: ConstraintSnapshots are immutable. Updates create new snapshots.
    """

    __tablename__ = "cwom_constraint_snapshots"

    # Object identity (ULID string)
    id = Column(String(128), primary_key=True)
    kind = Column(String(20), nullable=False, default="ConstraintSnapshot")

    # Trace ID for unified traceability (Sprint-0)
    trace_id = Column(String(36), nullable=True, index=True)

    # Scope (index defined in __table_args__)
    scope = Column(cwom_constraint_scope_enum, nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Owner (Actor) - stored as JSON
    owner_kind = Column(cwom_actor_kind_enum, nullable=False)
    owner_id = Column(String(128), nullable=False, index=True)
    owner_display = Column(String(256), nullable=True)

    # Constraints - stored as JSON (Constraints object)
    constraints = Column(JSON, nullable=False, default=dict)

    # Metadata
    tags = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)

    # SQLAlchemy Relationships
    issues = relationship(
        "CWOMIssueModel",
        secondary=issue_constraint_snapshots,
        back_populates="constraint_snapshots",
    )
    runs = relationship("CWOMRunModel", back_populates="constraint_snapshot_obj")

    # Indexes
    __table_args__ = (
        Index("ix_cwom_constraint_snapshots_scope", "scope"),
        Index("ix_cwom_constraint_snapshots_captured_at", "captured_at"),
        Index("ix_cwom_constraint_snapshots_owner", "owner_kind", "owner_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary matching CWOM Pydantic schema."""
        return {
            "kind": self.kind,
            "id": self.id,
            "trace_id": self.trace_id,
            "scope": self.scope,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "owner": {
                "actor_kind": self.owner_kind,
                "actor_id": self.owner_id,
                "display": self.owner_display,
            },
            "constraints": self.constraints,
            "tags": self.tags,
            "meta": self.meta,
        }


class CWOMDoctrineRefModel(Base):
    """SQLAlchemy model for CWOM DoctrineRef objects."""

    __tablename__ = "cwom_doctrine_refs"

    # Object identity (ULID string)
    id = Column(String(128), primary_key=True)
    kind = Column(String(20), nullable=False, default="DoctrineRef")

    # Trace ID for unified traceability (Sprint-0)
    trace_id = Column(String(36), nullable=True, index=True)

    # Core fields
    namespace = Column(String(128), nullable=False, index=True)
    name = Column(String(256), nullable=False, index=True)
    version = Column(String(64), nullable=False, index=True)
    type = Column(cwom_doctrine_type_enum, nullable=False, index=True)
    priority = Column(cwom_doctrine_priority_enum, nullable=False, default="should")

    # Content
    statement = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)

    # References
    links = Column(JSON, nullable=False, default=list)

    # Applicability - stored as JSON (DoctrineApplicability object)
    applicability = Column(JSON, nullable=False, default=dict)

    # Metadata
    tags = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    # SQLAlchemy Relationships
    issues = relationship(
        "CWOMIssueModel",
        secondary=issue_doctrine_refs,
        back_populates="doctrine_refs_rel",
    )
    context_packets = relationship(
        "CWOMContextPacketModel",
        secondary=context_packet_doctrine_refs,
        back_populates="doctrine_refs_rel",
    )
    runs = relationship(
        "CWOMRunModel",
        secondary=run_doctrine_refs,
        back_populates="doctrine_refs_rel",
    )

    # Indexes
    __table_args__ = (
        Index("ix_cwom_doctrine_refs_namespace_name", "namespace", "name"),
        Index("ix_cwom_doctrine_refs_type_priority", "type", "priority"),
        Index("ix_cwom_doctrine_refs_created_at", "created_at"),
        UniqueConstraint("namespace", "name", "version", name="uq_doctrine_ref_nv"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary matching CWOM Pydantic schema."""
        return {
            "kind": self.kind,
            "id": self.id,
            "trace_id": self.trace_id,
            "namespace": self.namespace,
            "name": self.name,
            "version": self.version,
            "type": self.type,
            "priority": self.priority,
            "statement": self.statement,
            "rationale": self.rationale,
            "links": self.links,
            "applicability": self.applicability,
            "tags": self.tags,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CWOMRunModel(Base):
    """SQLAlchemy model for CWOM Run objects."""

    __tablename__ = "cwom_runs"

    # Object identity (ULID string)
    id = Column(String(128), primary_key=True)
    kind = Column(String(20), nullable=False, default="Run")

    # Trace ID for unified traceability (Sprint-0)
    trace_id = Column(String(36), nullable=True, index=True)

    # Issue reference (foreign key)
    for_issue_id = Column(
        String(128), ForeignKey("cwom_issues.id"), nullable=False, index=True
    )
    for_issue_kind = Column(String(20), nullable=False, default="Issue")
    for_issue_role = Column(String(64), nullable=True)

    # Repo reference (foreign key)
    repo_id = Column(
        String(128), ForeignKey("cwom_repos.id"), nullable=False, index=True
    )
    repo_kind = Column(String(20), nullable=False, default="Repo")
    repo_role = Column(String(64), nullable=True)

    # Status
    status = Column(cwom_status_enum, nullable=False, default="planned", index=True)
    mode = Column(cwom_run_mode_enum, nullable=False, index=True)

    # Executor - stored as JSON (Executor object)
    executor = Column(JSON, nullable=False)

    # Inputs - stored as JSON (RunInputs object)
    # Note: many-to-many relationships also tracked via join tables
    inputs = Column(JSON, nullable=False, default=dict)

    # Constraint snapshot pinned at run start
    constraint_snapshot_id = Column(
        String(128), ForeignKey("cwom_constraint_snapshots.id"), nullable=True
    )

    # Plan - stored as JSON (RunPlan object)
    plan = Column(JSON, nullable=False, default=dict)

    # Telemetry - stored as JSON (Telemetry object)
    telemetry = Column(JSON, nullable=False, default=dict)

    # Cost - stored as JSON (Cost object)
    cost = Column(JSON, nullable=False, default=dict)

    # Outputs - stored as JSON (RunOutputs object)
    outputs = Column(JSON, nullable=False, default=dict)

    # Failure - stored as JSON (Failure object) if failed
    failure = Column(JSON, nullable=True)

    # Trace storage URI (v0: file://, v2: s3://)
    # Example: file:///var/lib/jct/runs/{run_id}/
    artifact_root_uri = Column(String(2000), nullable=True)

    # Metadata
    tags = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    # SQLAlchemy Relationships
    issue_obj = relationship("CWOMIssueModel", back_populates="runs_rel")
    context_packets = relationship(
        "CWOMContextPacketModel",
        secondary=run_context_packets,
        back_populates="runs",
    )
    doctrine_refs_rel = relationship(
        "CWOMDoctrineRefModel",
        secondary=run_doctrine_refs,
        back_populates="runs",
    )
    constraint_snapshot_obj = relationship(
        "CWOMConstraintSnapshotModel",
        back_populates="runs",
        foreign_keys=[constraint_snapshot_id],
    )
    artifacts = relationship("CWOMArtifactModel", back_populates="run_obj")

    # Indexes
    __table_args__ = (
        Index("ix_cwom_runs_status_mode", "status", "mode"),
        Index("ix_cwom_runs_created_at", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary matching CWOM Pydantic schema."""
        return {
            "kind": self.kind,
            "id": self.id,
            "trace_id": self.trace_id,
            "for_issue": {
                "kind": self.for_issue_kind,
                "id": self.for_issue_id,
                "role": self.for_issue_role,
            },
            "repo": {
                "kind": self.repo_kind,
                "id": self.repo_id,
                "role": self.repo_role,
            },
            "status": self.status,
            "mode": self.mode,
            "executor": self.executor,
            "inputs": self.inputs,
            "plan": self.plan,
            "telemetry": self.telemetry,
            "cost": self.cost,
            "outputs": self.outputs,
            "failure": self.failure,
            "artifact_root_uri": self.artifact_root_uri,
            "tags": self.tags,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CWOMArtifactModel(Base):
    """SQLAlchemy model for CWOM Artifact objects."""

    __tablename__ = "cwom_artifacts"

    # Object identity (ULID string)
    id = Column(String(128), primary_key=True)
    kind = Column(String(20), nullable=False, default="Artifact")

    # Trace ID for unified traceability (Sprint-0)
    trace_id = Column(String(36), nullable=True, index=True)

    # Run reference (foreign key)
    produced_by_id = Column(
        String(128), ForeignKey("cwom_runs.id"), nullable=False, index=True
    )
    produced_by_kind = Column(String(20), nullable=False, default="Run")
    produced_by_role = Column(String(64), nullable=True)

    # Issue reference (foreign key)
    for_issue_id = Column(
        String(128), ForeignKey("cwom_issues.id"), nullable=False, index=True
    )
    for_issue_kind = Column(String(20), nullable=False, default="Issue")
    for_issue_role = Column(String(64), nullable=True)

    # Content (type index defined in __table_args__)
    type = Column(cwom_artifact_type_enum, nullable=False)
    title = Column(String(512), nullable=False)
    uri = Column(String(2000), nullable=False)

    # Verification
    digest = Column(String(128), nullable=True)
    media_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    preview = Column(Text, nullable=True)

    # Verification status - stored as JSON (Verification object)
    verification = Column(JSON, nullable=False, default=dict)

    # Metadata
    tags = Column(JSON, nullable=False, default=list)
    meta = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    # SQLAlchemy Relationships
    run_obj = relationship("CWOMRunModel", back_populates="artifacts")

    # Indexes
    __table_args__ = (
        Index("ix_cwom_artifacts_type", "type"),
        Index("ix_cwom_artifacts_created_at", "created_at"),
        Index("ix_cwom_artifacts_digest", "digest"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary matching CWOM Pydantic schema."""
        return {
            "kind": self.kind,
            "id": self.id,
            "trace_id": self.trace_id,
            "produced_by": {
                "kind": self.produced_by_kind,
                "id": self.produced_by_id,
                "role": self.produced_by_role,
            },
            "for_issue": {
                "kind": self.for_issue_kind,
                "id": self.for_issue_id,
                "role": self.for_issue_role,
            },
            "type": self.type,
            "title": self.title,
            "uri": self.uri,
            "digest": self.digest,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "preview": self.preview,
            "verification": self.verification,
            "tags": self.tags,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
