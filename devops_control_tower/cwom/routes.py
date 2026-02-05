"""
CWOM v0.1 API Routes.

REST endpoints for CWOM object CRUD operations.
All endpoints are prefixed with /cwom.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db.base import get_db
from .services import (
    ArtifactService,
    ConstraintSnapshotService,
    ContextPacketService,
    DoctrineRefService,
    EvidencePackService,
    ImmutabilityError,
    IssueService,
    RepoService,
    ReviewDecisionService,
    RunService,
)
from .review_decision import ReviewDecisionCreate
from .repo import RepoCreate
from .issue import IssueCreate
from .context_packet import ContextPacketCreate
from .constraint_snapshot import ConstraintSnapshotCreate
from .doctrine_ref import DoctrineRefCreate
from .run import RunCreate, RunUpdate
from .artifact import ArtifactCreate

router = APIRouter(prefix="/cwom", tags=["CWOM"])


# =============================================================================
# Repo Endpoints
# =============================================================================


@router.post("/repos", status_code=201)
async def create_repo(
    repo: RepoCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new Repo."""
    service = RepoService(db)

    # Check if slug already exists
    existing = service.get_by_slug(repo.slug)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Repo with slug '{repo.slug}' already exists",
        )

    db_repo = service.create(repo)
    return {
        "status": "success",
        "repo": db_repo.to_dict(),
    }


@router.get("/repos/{repo_id}")
async def get_repo(
    repo_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a Repo by ID."""
    service = RepoService(db)
    repo = service.get(repo_id)

    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")

    return repo.to_dict()


@router.get("/repos")
async def list_repos(
    visibility: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List Repos with optional filtering."""
    service = RepoService(db)
    repos = service.list(visibility=visibility, limit=limit, offset=offset)
    return [r.to_dict() for r in repos]


# =============================================================================
# Issue Endpoints
# =============================================================================


@router.post("/issues", status_code=201)
async def create_issue(
    issue: IssueCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new Issue."""
    # Verify repo exists
    repo_service = RepoService(db)
    repo = repo_service.get(issue.repo.id)
    if not repo:
        raise HTTPException(
            status_code=422,
            detail=f"Referenced Repo '{issue.repo.id}' does not exist",
        )

    service = IssueService(db)
    db_issue = service.create(issue)
    return {
        "status": "success",
        "issue": db_issue.to_dict(),
    }


@router.get("/issues/{issue_id}")
async def get_issue(
    issue_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an Issue by ID with related objects."""
    service = IssueService(db)
    issue = service.get(issue_id)

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    return issue.to_dict()


@router.get("/issues")
async def list_issues(
    repo_id: Optional[str] = None,
    status: Optional[str] = None,
    issue_type: Optional[str] = Query(None, alias="type"),
    priority: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List Issues with optional filtering."""
    service = IssueService(db)
    issues = service.list(
        repo_id=repo_id,
        status=status,
        issue_type=issue_type,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return [i.to_dict() for i in issues]


@router.patch("/issues/{issue_id}/status")
async def update_issue_status(
    issue_id: str,
    status: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update Issue status."""
    service = IssueService(db)
    issue = service.update_status(issue_id, status)

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    return {
        "status": "success",
        "issue": issue.to_dict(),
    }


# =============================================================================
# ContextPacket Endpoints
# =============================================================================


@router.post("/context-packets", status_code=201)
async def create_context_packet(
    packet: ContextPacketCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new ContextPacket.

    Note: ContextPackets are immutable. Once created, they cannot be modified.
    """
    # Verify issue exists
    issue_service = IssueService(db)
    issue = issue_service.get(packet.for_issue.id)
    if not issue:
        raise HTTPException(
            status_code=422,
            detail=f"Referenced Issue '{packet.for_issue.id}' does not exist",
        )

    service = ContextPacketService(db)
    db_packet = service.create(packet)

    # Auto-link to the issue
    issue_service.link_context_packet(packet.for_issue.id, db_packet.id)

    return {
        "status": "success",
        "context_packet": db_packet.to_dict(),
    }


@router.get("/context-packets/{packet_id}")
async def get_context_packet(
    packet_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a ContextPacket by ID."""
    service = ContextPacketService(db)
    packet = service.get(packet_id)

    if not packet:
        raise HTTPException(status_code=404, detail="ContextPacket not found")

    return packet.to_dict()


@router.get("/issues/{issue_id}/context-packets")
async def list_context_packets_for_issue(
    issue_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List ContextPackets for an Issue."""
    service = ContextPacketService(db)
    packets = service.list_for_issue(issue_id, limit=limit, offset=offset)
    return [p.to_dict() for p in packets]


@router.put("/context-packets/{packet_id}")
@router.patch("/context-packets/{packet_id}")
async def update_context_packet_blocked(packet_id: str) -> None:
    """ContextPackets are immutable and cannot be modified.

    To update context, create a new ContextPacket with an incremented version.
    """
    raise HTTPException(
        status_code=405,
        detail={
            "error": "IMMUTABILITY_VIOLATION",
            "message": "ContextPackets are immutable. Create a new ContextPacket with an incremented version instead.",
            "object_id": packet_id,
        },
    )


# =============================================================================
# ConstraintSnapshot Endpoints
# =============================================================================


@router.post("/constraint-snapshots", status_code=201)
async def create_constraint_snapshot(
    snapshot: ConstraintSnapshotCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new ConstraintSnapshot.

    Note: ConstraintSnapshots are immutable. Once created, they cannot be modified.
    """
    service = ConstraintSnapshotService(db)
    db_snapshot = service.create(snapshot)
    return {
        "status": "success",
        "constraint_snapshot": db_snapshot.to_dict(),
    }


@router.get("/constraint-snapshots/{snapshot_id}")
async def get_constraint_snapshot(
    snapshot_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a ConstraintSnapshot by ID."""
    service = ConstraintSnapshotService(db)
    snapshot = service.get(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail="ConstraintSnapshot not found")

    return snapshot.to_dict()


@router.put("/constraint-snapshots/{snapshot_id}")
@router.patch("/constraint-snapshots/{snapshot_id}")
async def update_constraint_snapshot_blocked(snapshot_id: str) -> None:
    """ConstraintSnapshots are immutable and cannot be modified.

    To update constraints, create a new ConstraintSnapshot.
    """
    raise HTTPException(
        status_code=405,
        detail={
            "error": "IMMUTABILITY_VIOLATION",
            "message": "ConstraintSnapshots are immutable. Create a new ConstraintSnapshot instead.",
            "object_id": snapshot_id,
        },
    )


@router.get("/constraint-snapshots")
async def list_constraint_snapshots(
    scope: Optional[str] = None,
    owner_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List ConstraintSnapshots with optional filtering."""
    service = ConstraintSnapshotService(db)
    snapshots = service.list(
        scope=scope,
        owner_id=owner_id,
        limit=limit,
        offset=offset,
    )
    return [s.to_dict() for s in snapshots]


# =============================================================================
# DoctrineRef Endpoints
# =============================================================================


@router.post("/doctrine-refs", status_code=201)
async def create_doctrine_ref(
    doctrine: DoctrineRefCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new DoctrineRef."""
    service = DoctrineRefService(db)

    # Check for existing doctrine with same namespace/name/version
    existing = service.get_by_name(
        doctrine.namespace, doctrine.name, doctrine.version
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"DoctrineRef '{doctrine.namespace}/{doctrine.name}@{doctrine.version}' already exists",
        )

    db_doctrine = service.create(doctrine)
    return {
        "status": "success",
        "doctrine_ref": db_doctrine.to_dict(),
    }


@router.get("/doctrine-refs/{doctrine_id}")
async def get_doctrine_ref(
    doctrine_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a DoctrineRef by ID."""
    service = DoctrineRefService(db)
    doctrine = service.get(doctrine_id)

    if not doctrine:
        raise HTTPException(status_code=404, detail="DoctrineRef not found")

    return doctrine.to_dict()


@router.get("/doctrine-refs")
async def list_doctrine_refs(
    namespace: Optional[str] = None,
    doctrine_type: Optional[str] = Query(None, alias="type"),
    priority: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List DoctrineRefs with optional filtering."""
    service = DoctrineRefService(db)
    doctrines = service.list(
        namespace=namespace,
        doctrine_type=doctrine_type,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return [d.to_dict() for d in doctrines]


# =============================================================================
# Run Endpoints
# =============================================================================


@router.post("/runs", status_code=201)
async def create_run(
    run: RunCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new Run."""
    # Verify issue exists
    issue_service = IssueService(db)
    issue = issue_service.get(run.for_issue.id)
    if not issue:
        raise HTTPException(
            status_code=422,
            detail=f"Referenced Issue '{run.for_issue.id}' does not exist",
        )

    # Verify repo exists
    repo_service = RepoService(db)
    repo = repo_service.get(run.repo.id)
    if not repo:
        raise HTTPException(
            status_code=422,
            detail=f"Referenced Repo '{run.repo.id}' does not exist",
        )

    service = RunService(db)
    db_run = service.create(run)
    return {
        "status": "success",
        "run": db_run.to_dict(),
    }


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a Run by ID."""
    service = RunService(db)
    run = service.get(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run.to_dict()


@router.get("/runs")
async def list_runs(
    issue_id: Optional[str] = None,
    repo_id: Optional[str] = None,
    status: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List Runs with optional filtering."""
    service = RunService(db)
    runs = service.list(
        issue_id=issue_id,
        repo_id=repo_id,
        status=status,
        mode=mode,
        limit=limit,
        offset=offset,
    )
    return [r.to_dict() for r in runs]


@router.patch("/runs/{run_id}")
async def update_run(
    run_id: str,
    update: RunUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update a Run's mutable fields (status, outputs, telemetry, etc.)."""
    service = RunService(db)
    run = service.update(run_id, update)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "status": "success",
        "run": run.to_dict(),
    }


# =============================================================================
# Artifact Endpoints
# =============================================================================


@router.post("/artifacts", status_code=201)
async def create_artifact(
    artifact: ArtifactCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new Artifact."""
    # Verify run exists
    run_service = RunService(db)
    run = run_service.get(artifact.produced_by.id)
    if not run:
        raise HTTPException(
            status_code=422,
            detail=f"Referenced Run '{artifact.produced_by.id}' does not exist",
        )

    # Verify issue exists
    issue_service = IssueService(db)
    issue = issue_service.get(artifact.for_issue.id)
    if not issue:
        raise HTTPException(
            status_code=422,
            detail=f"Referenced Issue '{artifact.for_issue.id}' does not exist",
        )

    service = ArtifactService(db)
    db_artifact = service.create(artifact)
    return {
        "status": "success",
        "artifact": db_artifact.to_dict(),
    }


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an Artifact by ID."""
    service = ArtifactService(db)
    artifact = service.get(artifact_id)

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return artifact.to_dict()


@router.get("/runs/{run_id}/artifacts")
async def list_artifacts_for_run(
    run_id: str,
    artifact_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List Artifacts produced by a Run."""
    service = ArtifactService(db)
    artifacts = service.list_for_run(
        run_id,
        artifact_type=artifact_type,
        limit=limit,
        offset=offset,
    )
    return [a.to_dict() for a in artifacts]


@router.get("/issues/{issue_id}/artifacts")
async def list_artifacts_for_issue(
    issue_id: str,
    artifact_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List Artifacts for an Issue."""
    service = ArtifactService(db)
    artifacts = service.list_for_issue(
        issue_id,
        artifact_type=artifact_type,
        limit=limit,
        offset=offset,
    )
    return [a.to_dict() for a in artifacts]


# =============================================================================
# EvidencePack Endpoints
# =============================================================================


@router.get("/evidence-packs/{evidence_pack_id}")
async def get_evidence_pack(
    evidence_pack_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get an EvidencePack by ID."""
    service = EvidencePackService(db)
    evidence_pack = service.get(evidence_pack_id)

    if not evidence_pack:
        raise HTTPException(status_code=404, detail="EvidencePack not found")

    return evidence_pack.to_dict()


@router.get("/evidence-packs")
async def list_evidence_packs(
    run_id: Optional[str] = None,
    issue_id: Optional[str] = None,
    verdict: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List EvidencePacks with optional filtering."""
    service = EvidencePackService(db)
    evidence_packs = service.list(
        run_id=run_id,
        issue_id=issue_id,
        verdict=verdict,
        limit=limit,
        offset=offset,
    )
    return [ep.to_dict() for ep in evidence_packs]


@router.get("/runs/{run_id}/evidence-pack")
async def get_evidence_pack_for_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the EvidencePack for a Run."""
    # Verify run exists
    run_service = RunService(db)
    run = run_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    service = EvidencePackService(db)
    evidence_pack = service.get_for_run(run_id)

    if not evidence_pack:
        raise HTTPException(
            status_code=404,
            detail=f"No EvidencePack found for Run '{run_id}'"
        )

    return evidence_pack.to_dict()


@router.get("/issues/{issue_id}/evidence-packs")
async def list_evidence_packs_for_issue(
    issue_id: str,
    verdict: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List EvidencePacks for an Issue."""
    service = EvidencePackService(db)
    evidence_packs = service.list_for_issue(
        issue_id,
        verdict=verdict,
        limit=limit,
        offset=offset,
    )
    return [ep.to_dict() for ep in evidence_packs]


# =============================================================================
# ReviewDecision Endpoints
# =============================================================================


@router.post("/reviews", status_code=201)
async def create_review(
    review: ReviewDecisionCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit a review decision for an EvidencePack.

    Updates Issue and Run status based on decision:
    - approved -> Issue/Run status = done
    - rejected/needs_changes -> Issue/Run status = failed
    """
    service = ReviewDecisionService(db)

    try:
        db_review = service.create(
            review_data=review.model_dump(),
            actor_kind=review.reviewer.actor_kind.value
            if hasattr(review.reviewer.actor_kind, "value")
            else str(review.reviewer.actor_kind),
            actor_id=review.reviewer.actor_id,
        )
        return {
            "status": "success",
            "review": db_review.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reviews/{review_id}")
async def get_review(
    review_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a ReviewDecision by ID."""
    service = ReviewDecisionService(db)
    review = service.get(review_id)

    if not review:
        raise HTTPException(status_code=404, detail="ReviewDecision not found")

    return review.to_dict()


@router.get("/reviews")
async def list_reviews(
    evidence_pack_id: Optional[str] = None,
    issue_id: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List ReviewDecisions with optional filtering."""
    service = ReviewDecisionService(db)
    reviews = service.list(
        evidence_pack_id=evidence_pack_id,
        issue_id=issue_id,
        decision=decision,
        limit=limit,
        offset=offset,
    )
    return [r.to_dict() for r in reviews]


@router.get("/evidence-packs/{evidence_pack_id}/review")
async def get_review_for_evidence_pack(
    evidence_pack_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get the ReviewDecision for an EvidencePack."""
    service = ReviewDecisionService(db)
    review = service.get_for_evidence_pack(evidence_pack_id)

    if not review:
        raise HTTPException(
            status_code=404,
            detail="No ReviewDecision found for this EvidencePack",
        )

    return review.to_dict()


@router.get("/issues/{issue_id}/reviews")
async def list_reviews_for_issue(
    issue_id: str,
    decision: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List ReviewDecisions for an Issue."""
    service = ReviewDecisionService(db)
    reviews = service.list_for_issue(
        issue_id,
        decision=decision,
        limit=limit,
        offset=offset,
    )
    return [r.to_dict() for r in reviews]
