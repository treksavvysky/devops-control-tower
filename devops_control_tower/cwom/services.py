"""
CWOM v0.1 Service Layer.

Provides database operations for CWOM objects with business logic validation.
Each service class handles CRUD operations for a specific CWOM object type.

Audit logging is integrated into all state-changing operations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db.cwom_models import (
    CWOMArtifactModel,
    CWOMConstraintSnapshotModel,
    CWOMContextPacketModel,
    CWOMDoctrineRefModel,
    CWOMIssueModel,
    CWOMRepoModel,
    CWOMRunModel,
    issue_constraint_snapshots,
    issue_context_packets,
    issue_doctrine_refs,
    run_context_packets,
    run_doctrine_refs,
    context_packet_doctrine_refs,
)
from ..db.audit_service import AuditService
from .primitives import generate_ulid, utc_now
from .repo import RepoCreate
from .issue import IssueCreate
from .context_packet import ContextPacketCreate
from .constraint_snapshot import ConstraintSnapshotCreate
from .doctrine_ref import DoctrineRefCreate
from .run import RunCreate, RunUpdate
from .artifact import ArtifactCreate


class ImmutabilityError(Exception):
    """Raised when attempting to modify an immutable object."""

    def __init__(self, object_type: str, object_id: str):
        self.object_type = object_type
        self.object_id = object_id
        self.message = f"{object_type} objects are immutable. Cannot modify {object_id}."
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": "IMMUTABILITY_VIOLATION",
            "object_type": self.object_type,
            "object_id": self.object_id,
            "message": self.message,
        }


class RepoService:
    """Service for managing CWOM Repo objects."""

    def __init__(self, db: Session, audit: Optional[AuditService] = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def create(
        self,
        repo: RepoCreate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> CWOMRepoModel:
        """Create a new Repo."""
        now = datetime.now(timezone.utc)
        db_repo = CWOMRepoModel(
            id=generate_ulid(),
            kind="Repo",
            trace_id=trace_id,
            name=repo.name,
            slug=repo.slug,
            source=repo.source.model_dump(),
            default_branch=repo.default_branch,
            visibility=repo.visibility.value,
            owners=[o.model_dump() for o in repo.owners],
            policy=repo.policy.model_dump() if repo.policy else None,
            links=repo.links,
            tags=repo.tags,
            meta=repo.meta,
            created_at=now,
            updated_at=now,
        )

        self.db.add(db_repo)
        self.db.commit()
        self.db.refresh(db_repo)

        # Audit log
        self.audit.log_create(
            entity_kind="Repo",
            entity_id=db_repo.id,
            after=db_repo.to_dict(),
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id,
        )

        return db_repo

    def get(self, repo_id: str) -> Optional[CWOMRepoModel]:
        """Get a Repo by ID."""
        return self.db.query(CWOMRepoModel).filter(CWOMRepoModel.id == repo_id).first()

    def get_by_slug(self, slug: str) -> Optional[CWOMRepoModel]:
        """Get a Repo by slug."""
        return self.db.query(CWOMRepoModel).filter(CWOMRepoModel.slug == slug).first()

    def list(
        self,
        visibility: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMRepoModel]:
        """List Repos with optional filtering."""
        query = self.db.query(CWOMRepoModel)

        if visibility:
            query = query.filter(CWOMRepoModel.visibility == visibility)

        return (
            query.order_by(desc(CWOMRepoModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )


class IssueService:
    """Service for managing CWOM Issue objects."""

    def __init__(self, db: Session, audit: Optional[AuditService] = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def create(
        self,
        issue: IssueCreate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> CWOMIssueModel:
        """Create a new Issue."""
        now = datetime.now(timezone.utc)
        db_issue = CWOMIssueModel(
            id=generate_ulid(),
            kind="Issue",
            trace_id=trace_id,
            repo_id=issue.repo.id,
            repo_kind=issue.repo.kind.value if hasattr(issue.repo.kind, 'value') else str(issue.repo.kind),
            repo_role=issue.repo.role,
            title=issue.title,
            description=issue.description,
            type=issue.type.value,
            priority=issue.priority.value,
            status=issue.status.value,
            assignees=[a.model_dump() for a in issue.assignees],
            watchers=[w.model_dump() for w in issue.watchers],
            acceptance=issue.acceptance.model_dump() if issue.acceptance else {},
            relationships=issue.relationships.model_dump() if issue.relationships else {},
            runs=[],
            tags=issue.tags,
            meta=issue.meta,
            created_at=now,
            updated_at=now,
        )

        self.db.add(db_issue)
        self.db.commit()
        self.db.refresh(db_issue)

        # Audit log
        self.audit.log_create(
            entity_kind="Issue",
            entity_id=db_issue.id,
            after=db_issue.to_dict(),
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id,
        )

        return db_issue

    def get(self, issue_id: str) -> Optional[CWOMIssueModel]:
        """Get an Issue by ID with related objects."""
        return self.db.query(CWOMIssueModel).filter(CWOMIssueModel.id == issue_id).first()

    def list(
        self,
        repo_id: Optional[str] = None,
        status: Optional[str] = None,
        issue_type: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMIssueModel]:
        """List Issues with optional filtering."""
        query = self.db.query(CWOMIssueModel)

        if repo_id:
            query = query.filter(CWOMIssueModel.repo_id == repo_id)
        if status:
            query = query.filter(CWOMIssueModel.status == status)
        if issue_type:
            query = query.filter(CWOMIssueModel.type == issue_type)
        if priority:
            query = query.filter(CWOMIssueModel.priority == priority)

        return (
            query.order_by(desc(CWOMIssueModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_status(
        self,
        issue_id: str,
        status: str,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> Optional[CWOMIssueModel]:
        """Update Issue status."""
        issue = self.get(issue_id)
        if not issue:
            return None

        old_status = issue.status
        issue.status = status
        issue.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(issue)

        # Audit log
        self.audit.log_status_change(
            entity_kind="Issue",
            entity_id=issue.id,
            old_status=old_status,
            new_status=status,
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id or issue.trace_id,
        )

        return issue

    def link_context_packet(
        self,
        issue_id: str,
        context_packet_id: str,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> bool:
        """Link a ContextPacket to an Issue."""
        stmt = issue_context_packets.insert().values(
            issue_id=issue_id,
            context_packet_id=context_packet_id,
        )
        try:
            self.db.execute(stmt)
            self.db.commit()

            # Audit log
            self.audit.log_link(
                entity_kind="Issue",
                entity_id=issue_id,
                linked_kind="ContextPacket",
                linked_id=context_packet_id,
                actor_kind=actor_kind,
                actor_id=actor_id,
                trace_id=trace_id,
            )

            return True
        except Exception:
            self.db.rollback()
            return False

    def link_doctrine_ref(
        self,
        issue_id: str,
        doctrine_ref_id: str,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> bool:
        """Link a DoctrineRef to an Issue."""
        stmt = issue_doctrine_refs.insert().values(
            issue_id=issue_id,
            doctrine_ref_id=doctrine_ref_id,
        )
        try:
            self.db.execute(stmt)
            self.db.commit()

            # Audit log
            self.audit.log_link(
                entity_kind="Issue",
                entity_id=issue_id,
                linked_kind="DoctrineRef",
                linked_id=doctrine_ref_id,
                actor_kind=actor_kind,
                actor_id=actor_id,
                trace_id=trace_id,
            )

            return True
        except Exception:
            self.db.rollback()
            return False

    def link_constraint_snapshot(
        self,
        issue_id: str,
        constraint_snapshot_id: str,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> bool:
        """Link a ConstraintSnapshot to an Issue."""
        stmt = issue_constraint_snapshots.insert().values(
            issue_id=issue_id,
            constraint_snapshot_id=constraint_snapshot_id,
        )
        try:
            self.db.execute(stmt)
            self.db.commit()

            # Audit log
            self.audit.log_link(
                entity_kind="Issue",
                entity_id=issue_id,
                linked_kind="ConstraintSnapshot",
                linked_id=constraint_snapshot_id,
                actor_kind=actor_kind,
                actor_id=actor_id,
                trace_id=trace_id,
            )

            return True
        except Exception:
            self.db.rollback()
            return False


class ContextPacketService:
    """Service for managing CWOM ContextPacket objects.

    Note: ContextPackets are IMMUTABLE. Once created, they cannot be modified.
    To update context, create a new ContextPacket with an incremented version.
    """

    def __init__(self, db: Session, audit: Optional[AuditService] = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def create(
        self,
        packet: ContextPacketCreate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> CWOMContextPacketModel:
        """Create a new ContextPacket."""
        now = datetime.now(timezone.utc)
        db_packet = CWOMContextPacketModel(
            id=generate_ulid(),
            kind="ContextPacket",
            trace_id=trace_id,
            for_issue_id=packet.for_issue.id,
            for_issue_kind=packet.for_issue.kind.value if hasattr(packet.for_issue.kind, 'value') else str(packet.for_issue.kind),
            for_issue_role=packet.for_issue.role,
            version=packet.version,
            summary=packet.summary,
            inputs=packet.inputs.model_dump() if packet.inputs else {},
            assumptions=packet.assumptions,
            open_questions=packet.open_questions,
            instructions=packet.instructions,
            constraint_snapshot_id=packet.constraint_snapshot.id if packet.constraint_snapshot else None,
            tags=packet.tags,
            meta=packet.meta,
            created_at=now,
            updated_at=now,
        )

        self.db.add(db_packet)
        self.db.commit()
        self.db.refresh(db_packet)

        # Link doctrine refs if provided
        if packet.doctrine_refs:
            for ref in packet.doctrine_refs:
                stmt = context_packet_doctrine_refs.insert().values(
                    context_packet_id=db_packet.id,
                    doctrine_ref_id=ref.id,
                )
                try:
                    self.db.execute(stmt)
                except Exception:
                    pass  # Ignore duplicate links
            self.db.commit()

        # Audit log
        self.audit.log_create(
            entity_kind="ContextPacket",
            entity_id=db_packet.id,
            after=db_packet.to_dict(),
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id,
            note="Immutable object created",
        )

        return db_packet

    def get(self, packet_id: str) -> Optional[CWOMContextPacketModel]:
        """Get a ContextPacket by ID."""
        return (
            self.db.query(CWOMContextPacketModel)
            .filter(CWOMContextPacketModel.id == packet_id)
            .first()
        )

    def list_for_issue(
        self,
        issue_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMContextPacketModel]:
        """List ContextPackets for an Issue."""
        return (
            self.db.query(CWOMContextPacketModel)
            .filter(CWOMContextPacketModel.for_issue_id == issue_id)
            .order_by(desc(CWOMContextPacketModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_latest_for_issue(self, issue_id: str) -> Optional[CWOMContextPacketModel]:
        """Get the latest ContextPacket for an Issue."""
        return (
            self.db.query(CWOMContextPacketModel)
            .filter(CWOMContextPacketModel.for_issue_id == issue_id)
            .order_by(desc(CWOMContextPacketModel.created_at))
            .first()
        )


class ConstraintSnapshotService:
    """Service for managing CWOM ConstraintSnapshot objects.

    Note: ConstraintSnapshots are IMMUTABLE. Once created, they cannot be modified.
    To update constraints, create a new ConstraintSnapshot.
    """

    def __init__(self, db: Session, audit: Optional[AuditService] = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def create(
        self,
        snapshot: ConstraintSnapshotCreate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> CWOMConstraintSnapshotModel:
        """Create a new ConstraintSnapshot."""
        now = datetime.now(timezone.utc)
        db_snapshot = CWOMConstraintSnapshotModel(
            id=generate_ulid(),
            kind="ConstraintSnapshot",
            trace_id=trace_id,
            scope=snapshot.scope.value,
            captured_at=now,  # Always captured at creation time
            owner_kind=snapshot.owner.actor_kind.value if hasattr(snapshot.owner.actor_kind, 'value') else str(snapshot.owner.actor_kind),
            owner_id=snapshot.owner.actor_id,
            owner_display=snapshot.owner.display,
            constraints=snapshot.constraints.model_dump() if snapshot.constraints else {},
            tags=snapshot.tags,
            meta=snapshot.meta,
        )

        self.db.add(db_snapshot)
        self.db.commit()
        self.db.refresh(db_snapshot)

        # Audit log
        self.audit.log_create(
            entity_kind="ConstraintSnapshot",
            entity_id=db_snapshot.id,
            after=db_snapshot.to_dict(),
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id,
            note="Immutable object created",
        )

        return db_snapshot

    def get(self, snapshot_id: str) -> Optional[CWOMConstraintSnapshotModel]:
        """Get a ConstraintSnapshot by ID."""
        return (
            self.db.query(CWOMConstraintSnapshotModel)
            .filter(CWOMConstraintSnapshotModel.id == snapshot_id)
            .first()
        )

    def list(
        self,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMConstraintSnapshotModel]:
        """List ConstraintSnapshots with optional filtering."""
        query = self.db.query(CWOMConstraintSnapshotModel)

        if scope:
            query = query.filter(CWOMConstraintSnapshotModel.scope == scope)
        if owner_id:
            query = query.filter(CWOMConstraintSnapshotModel.owner_id == owner_id)

        return (
            query.order_by(desc(CWOMConstraintSnapshotModel.captured_at))
            .offset(offset)
            .limit(limit)
            .all()
        )


class DoctrineRefService:
    """Service for managing CWOM DoctrineRef objects."""

    def __init__(self, db: Session, audit: Optional[AuditService] = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def create(
        self,
        doctrine: DoctrineRefCreate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> CWOMDoctrineRefModel:
        """Create a new DoctrineRef."""
        now = datetime.now(timezone.utc)
        db_doctrine = CWOMDoctrineRefModel(
            id=generate_ulid(),
            kind="DoctrineRef",
            trace_id=trace_id,
            namespace=doctrine.namespace,
            name=doctrine.name,
            version=doctrine.version,
            type=doctrine.type.value,
            priority=doctrine.priority.value,
            statement=doctrine.statement,
            rationale=doctrine.rationale,
            links=doctrine.links,
            applicability=doctrine.applicability.model_dump() if doctrine.applicability else {},
            tags=doctrine.tags,
            meta=doctrine.meta,
            created_at=now,
            updated_at=now,
        )

        self.db.add(db_doctrine)
        self.db.commit()
        self.db.refresh(db_doctrine)

        # Audit log
        self.audit.log_create(
            entity_kind="DoctrineRef",
            entity_id=db_doctrine.id,
            after=db_doctrine.to_dict(),
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id,
        )

        return db_doctrine

    def get(self, doctrine_id: str) -> Optional[CWOMDoctrineRefModel]:
        """Get a DoctrineRef by ID."""
        return (
            self.db.query(CWOMDoctrineRefModel)
            .filter(CWOMDoctrineRefModel.id == doctrine_id)
            .first()
        )

    def get_by_name(
        self, namespace: str, name: str, version: Optional[str] = None
    ) -> Optional[CWOMDoctrineRefModel]:
        """Get a DoctrineRef by namespace, name, and optionally version."""
        query = self.db.query(CWOMDoctrineRefModel).filter(
            CWOMDoctrineRefModel.namespace == namespace,
            CWOMDoctrineRefModel.name == name,
        )
        if version:
            query = query.filter(CWOMDoctrineRefModel.version == version)
        else:
            # Get latest version
            query = query.order_by(desc(CWOMDoctrineRefModel.created_at))

        return query.first()

    def list(
        self,
        namespace: Optional[str] = None,
        doctrine_type: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMDoctrineRefModel]:
        """List DoctrineRefs with optional filtering."""
        query = self.db.query(CWOMDoctrineRefModel)

        if namespace:
            query = query.filter(CWOMDoctrineRefModel.namespace == namespace)
        if doctrine_type:
            query = query.filter(CWOMDoctrineRefModel.type == doctrine_type)
        if priority:
            query = query.filter(CWOMDoctrineRefModel.priority == priority)

        return (
            query.order_by(CWOMDoctrineRefModel.namespace, CWOMDoctrineRefModel.name)
            .offset(offset)
            .limit(limit)
            .all()
        )


class RunService:
    """Service for managing CWOM Run objects."""

    def __init__(self, db: Session, audit: Optional[AuditService] = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def create(
        self,
        run: RunCreate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> CWOMRunModel:
        """Create a new Run."""
        from .enums import Status

        now = datetime.now(timezone.utc)

        # RunCreate doesn't include status - new runs start as "planned"
        status = Status.PLANNED

        db_run = CWOMRunModel(
            id=generate_ulid(),
            kind="Run",
            trace_id=trace_id,
            for_issue_id=run.for_issue.id,
            for_issue_kind=run.for_issue.kind.value if hasattr(run.for_issue.kind, 'value') else str(run.for_issue.kind),
            for_issue_role=run.for_issue.role,
            repo_id=run.repo.id,
            repo_kind=run.repo.kind.value if hasattr(run.repo.kind, 'value') else str(run.repo.kind),
            repo_role=run.repo.role,
            status=status.value,
            mode=run.mode.value,
            executor=run.executor.model_dump(),
            inputs=run.inputs.model_dump() if run.inputs else {},
            constraint_snapshot_id=None,  # Set via update if needed
            plan=run.plan.model_dump() if run.plan else {},
            telemetry={},  # Set via update
            cost={},  # Set via update
            outputs={},  # Set via update
            failure=None,  # Set via update if failed
            tags=run.tags,
            meta=run.meta,
            created_at=now,
            updated_at=now,
        )

        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)

        # Link context packets if provided in inputs
        if run.inputs and run.inputs.context_packets:
            for ref in run.inputs.context_packets:
                stmt = run_context_packets.insert().values(
                    run_id=db_run.id,
                    context_packet_id=ref.id,
                )
                try:
                    self.db.execute(stmt)
                except Exception:
                    pass
            self.db.commit()

        # Link doctrine refs if provided in inputs
        if run.inputs and run.inputs.doctrine_refs:
            for ref in run.inputs.doctrine_refs:
                stmt = run_doctrine_refs.insert().values(
                    run_id=db_run.id,
                    doctrine_ref_id=ref.id,
                )
                try:
                    self.db.execute(stmt)
                except Exception:
                    pass
            self.db.commit()

        # Audit log
        self.audit.log_create(
            entity_kind="Run",
            entity_id=db_run.id,
            after=db_run.to_dict(),
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id,
        )

        return db_run

    def get(self, run_id: str) -> Optional[CWOMRunModel]:
        """Get a Run by ID."""
        return self.db.query(CWOMRunModel).filter(CWOMRunModel.id == run_id).first()

    def list(
        self,
        issue_id: Optional[str] = None,
        repo_id: Optional[str] = None,
        status: Optional[str] = None,
        mode: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMRunModel]:
        """List Runs with optional filtering."""
        query = self.db.query(CWOMRunModel)

        if issue_id:
            query = query.filter(CWOMRunModel.for_issue_id == issue_id)
        if repo_id:
            query = query.filter(CWOMRunModel.repo_id == repo_id)
        if status:
            query = query.filter(CWOMRunModel.status == status)
        if mode:
            query = query.filter(CWOMRunModel.mode == mode)

        return (
            query.order_by(desc(CWOMRunModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update(
        self,
        run_id: str,
        update: RunUpdate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> Optional[CWOMRunModel]:
        """Update a Run's mutable fields (status, outputs, telemetry, etc.)."""
        run = self.get(run_id)
        if not run:
            return None

        # Capture before state for audit
        before_state = run.to_dict()
        old_status = run.status

        # Update allowed fields
        # Use mode='json' to serialize datetime objects properly
        if update.status is not None:
            run.status = update.status.value if hasattr(update.status, 'value') else str(update.status)

        if update.telemetry is not None:
            run.telemetry = update.telemetry.model_dump(mode='json')

        if update.cost is not None:
            run.cost = update.cost.model_dump(mode='json')

        if update.outputs is not None:
            run.outputs = update.outputs.model_dump(mode='json')

        if update.failure is not None:
            run.failure = update.failure.model_dump(mode='json')

        run.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(run)

        # Audit log - status change or general update
        effective_trace_id = trace_id or run.trace_id
        if update.status is not None and old_status != run.status:
            self.audit.log_status_change(
                entity_kind="Run",
                entity_id=run.id,
                old_status=old_status,
                new_status=run.status,
                actor_kind=actor_kind,
                actor_id=actor_id,
                trace_id=effective_trace_id,
            )
        else:
            self.audit.log_update(
                entity_kind="Run",
                entity_id=run.id,
                before=before_state,
                after=run.to_dict(),
                actor_kind=actor_kind,
                actor_id=actor_id,
                trace_id=effective_trace_id,
            )

        return run


class ArtifactService:
    """Service for managing CWOM Artifact objects."""

    def __init__(self, db: Session, audit: Optional[AuditService] = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def create(
        self,
        artifact: ArtifactCreate,
        actor_kind: str = "system",
        actor_id: str = "cwom-service",
        trace_id: Optional[str] = None,
    ) -> CWOMArtifactModel:
        """Create a new Artifact."""
        now = datetime.now(timezone.utc)
        db_artifact = CWOMArtifactModel(
            id=generate_ulid(),
            kind="Artifact",
            trace_id=trace_id,
            produced_by_id=artifact.produced_by.id,
            produced_by_kind=artifact.produced_by.kind.value if hasattr(artifact.produced_by.kind, 'value') else str(artifact.produced_by.kind),
            produced_by_role=artifact.produced_by.role,
            for_issue_id=artifact.for_issue.id,
            for_issue_kind=artifact.for_issue.kind.value if hasattr(artifact.for_issue.kind, 'value') else str(artifact.for_issue.kind),
            for_issue_role=artifact.for_issue.role,
            type=artifact.type.value,
            title=artifact.title,
            uri=artifact.uri,
            digest=artifact.digest,
            media_type=artifact.media_type,
            size_bytes=artifact.size_bytes,
            preview=artifact.preview,
            verification=artifact.verification.model_dump() if artifact.verification else {},
            tags=artifact.tags,
            meta=artifact.meta,
            created_at=now,
            updated_at=now,
        )

        self.db.add(db_artifact)
        self.db.commit()
        self.db.refresh(db_artifact)

        # Audit log
        self.audit.log_create(
            entity_kind="Artifact",
            entity_id=db_artifact.id,
            after=db_artifact.to_dict(),
            actor_kind=actor_kind,
            actor_id=actor_id,
            trace_id=trace_id,
        )

        return db_artifact

    def get(self, artifact_id: str) -> Optional[CWOMArtifactModel]:
        """Get an Artifact by ID."""
        return (
            self.db.query(CWOMArtifactModel)
            .filter(CWOMArtifactModel.id == artifact_id)
            .first()
        )

    def list_for_run(
        self,
        run_id: str,
        artifact_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMArtifactModel]:
        """List Artifacts produced by a Run."""
        query = self.db.query(CWOMArtifactModel).filter(
            CWOMArtifactModel.produced_by_id == run_id
        )

        if artifact_type:
            query = query.filter(CWOMArtifactModel.type == artifact_type)

        return (
            query.order_by(desc(CWOMArtifactModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_for_issue(
        self,
        issue_id: str,
        artifact_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CWOMArtifactModel]:
        """List Artifacts for an Issue."""
        query = self.db.query(CWOMArtifactModel).filter(
            CWOMArtifactModel.for_issue_id == issue_id
        )

        if artifact_type:
            query = query.filter(CWOMArtifactModel.type == artifact_type)

        return (
            query.order_by(desc(CWOMArtifactModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
