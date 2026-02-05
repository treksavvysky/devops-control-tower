"""
JCT Prover - evaluates Run outputs and creates Evidence Packs.

Step 4: Prove → Evidence Pack

v0 Automated Checks:
- Run completed successfully (status=done)
- No execution errors (failure=null)
- Evidence requirements satisfied (artifacts exist)
- Acceptance criteria (marked as "unverified" in v0, v1+ uses LLM)

Verdict Logic:
- FAIL: Run failed or errored
- PARTIAL: Some evidence missing
- PASS: All evidence present, run succeeded
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..db.cwom_models import (
    CWOMRunModel,
    CWOMIssueModel,
    CWOMContextPacketModel,
    CWOMEvidencePackModel,
    CWOMArtifactModel,
)
from ..db.models import TaskModel
from ..db.audit_service import AuditService
from .storage import TraceStore, create_trace_store

logger = logging.getLogger(__name__)


@dataclass
class CriterionResult:
    """Result of evaluating a single acceptance criterion."""
    criterion: str
    index: int
    status: str  # "satisfied", "not_satisfied", "unverified", "skipped"
    reason: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)


@dataclass
class EvidenceItem:
    """An item of evidence collected."""
    requirement: str
    index: int
    found: bool
    artifact_uri: Optional[str] = None
    artifact_type: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ProofResult:
    """Result of the prove phase."""
    verdict: str  # "pass", "fail", "partial", "pending"
    verdict_reason: str
    criteria_results: List[CriterionResult]
    evidence_collected: List[EvidenceItem]
    evidence_missing: List[str]
    checks_passed: int
    checks_failed: int
    checks_skipped: int


class Prover:
    """Evaluates Run outputs and creates Evidence Packs.

    v0: Automated checks only
    - Check run status
    - Check for evidence artifacts
    - Mark acceptance criteria as "unverified" (v1 will use LLM)
    """

    def __init__(self, prover_id: Optional[str] = None):
        """Initialize prover.

        Args:
            prover_id: Unique identifier for this prover instance
        """
        self.prover_id = prover_id or f"prover-{uuid.uuid4().hex[:8]}"
        logger.info(f"Prover initialized: {self.prover_id}")

    def prove(
        self,
        db: Session,
        run: CWOMRunModel,
        task: TaskModel,
        trace_store: Optional[TraceStore] = None,
    ) -> CWOMEvidencePackModel:
        """Evaluate a Run and create an Evidence Pack.

        Args:
            db: Database session
            run: The CWOM Run to evaluate
            task: The Task associated with this run
            trace_store: Optional TraceStore for writing evidence files

        Returns:
            CWOMEvidencePackModel with verdict and evidence
        """
        logger.info(f"Proving run {run.id} for task {task.id}")

        # Get acceptance criteria and evidence requirements from task/context
        acceptance_criteria = self._get_acceptance_criteria(db, run, task)
        evidence_requirements = self._get_evidence_requirements(db, run, task)

        # Collect artifacts produced by this run
        artifacts = self._get_run_artifacts(db, run)

        # Perform checks
        result = self._evaluate(
            run=run,
            acceptance_criteria=acceptance_criteria,
            evidence_requirements=evidence_requirements,
            artifacts=artifacts,
        )

        # Write evidence to trace folder if store available
        evidence_uri = None
        if trace_store:
            evidence_uri = self._write_evidence(trace_store, run, task, result)

        # Create EvidencePack record
        evidence_pack = self._create_evidence_pack(
            db=db,
            run=run,
            task=task,
            result=result,
            evidence_uri=evidence_uri,
        )

        logger.info(
            f"Evidence pack created: {evidence_pack.id}, verdict={result.verdict}"
        )

        return evidence_pack

    def _get_acceptance_criteria(
        self, db: Session, run: CWOMRunModel, task: TaskModel
    ) -> List[str]:
        """Get acceptance criteria from task metadata or context packet."""
        # First check task metadata
        task_meta = task.task_metadata or {}
        if "acceptance_criteria" in task_meta:
            return task_meta["acceptance_criteria"]

        # Check context packet meta
        context_packet = db.query(CWOMContextPacketModel).filter(
            CWOMContextPacketModel.for_issue_id == run.for_issue_id
        ).first()

        if context_packet and context_packet.meta:
            meta = context_packet.meta
            if "acceptance_criteria" in meta:
                return meta["acceptance_criteria"]

        return []

    def _get_evidence_requirements(
        self, db: Session, run: CWOMRunModel, task: TaskModel
    ) -> List[str]:
        """Get evidence requirements from task metadata or context packet."""
        # First check task metadata
        task_meta = task.task_metadata or {}
        if "evidence_requirements" in task_meta:
            return task_meta["evidence_requirements"]

        # Check context packet meta
        context_packet = db.query(CWOMContextPacketModel).filter(
            CWOMContextPacketModel.for_issue_id == run.for_issue_id
        ).first()

        if context_packet and context_packet.meta:
            meta = context_packet.meta
            if "evidence_requirements" in meta:
                return meta["evidence_requirements"]

        return []

    def _get_run_artifacts(
        self, db: Session, run: CWOMRunModel
    ) -> List[CWOMArtifactModel]:
        """Get all artifacts produced by this run."""
        return db.query(CWOMArtifactModel).filter(
            CWOMArtifactModel.produced_by_id == run.id
        ).all()

    def _evaluate(
        self,
        run: CWOMRunModel,
        acceptance_criteria: List[str],
        evidence_requirements: List[str],
        artifacts: List[CWOMArtifactModel],
    ) -> ProofResult:
        """Perform automated checks and produce proof result.

        v0 checks:
        1. Run status is 'done'
        2. No failure recorded
        3. Evidence requirements have matching artifacts
        4. Acceptance criteria marked as 'unverified' (v1 will evaluate)
        """
        checks_passed = 0
        checks_failed = 0
        checks_skipped = 0

        criteria_results: List[CriterionResult] = []
        evidence_collected: List[EvidenceItem] = []
        evidence_missing: List[str] = []

        # Check 1: Run status
        run_succeeded = run.status == "done"
        if run_succeeded:
            checks_passed += 1
        else:
            checks_failed += 1

        # Check 2: No failure
        has_failure = run.failure is not None
        if not has_failure:
            checks_passed += 1
        else:
            checks_failed += 1

        # Check 3: Evidence requirements
        artifact_map = {a.title.lower(): a for a in artifacts}
        artifact_types = {a.type: a for a in artifacts}

        for i, requirement in enumerate(evidence_requirements):
            req_lower = requirement.lower()

            # Try to match by title or type keywords
            found_artifact = None

            # Check exact title match
            if req_lower in artifact_map:
                found_artifact = artifact_map[req_lower]

            # Check for keyword matches
            if not found_artifact:
                for title, artifact in artifact_map.items():
                    # Simple keyword matching
                    if any(word in title for word in req_lower.split()):
                        found_artifact = artifact
                        break

            # Check for type matches (e.g., "pytest output" -> "log" type)
            if not found_artifact:
                if "test" in req_lower or "pytest" in req_lower:
                    found_artifact = artifact_types.get("log") or artifact_types.get("trace")
                elif "screenshot" in req_lower or "image" in req_lower:
                    found_artifact = artifact_types.get("binary")
                elif "doc" in req_lower or "readme" in req_lower:
                    found_artifact = artifact_types.get("doc")

            if found_artifact:
                evidence_collected.append(EvidenceItem(
                    requirement=requirement,
                    index=i,
                    found=True,
                    artifact_uri=found_artifact.uri,
                    artifact_type=found_artifact.type,
                    notes=f"Matched artifact: {found_artifact.title}",
                ))
                checks_passed += 1
            else:
                evidence_collected.append(EvidenceItem(
                    requirement=requirement,
                    index=i,
                    found=False,
                    notes="No matching artifact found",
                ))
                evidence_missing.append(requirement)
                checks_failed += 1

        # Check 4: Acceptance criteria (v0: mark as unverified)
        for i, criterion in enumerate(acceptance_criteria):
            criteria_results.append(CriterionResult(
                criterion=criterion,
                index=i,
                status="unverified",
                reason="v0: Automated verification not available. Requires LLM evaluation in v1.",
            ))
            checks_skipped += 1

        # Determine verdict
        if not run_succeeded or has_failure:
            verdict = "fail"
            verdict_reason = f"Run {'failed' if has_failure else 'did not complete successfully'}"
            if has_failure and isinstance(run.failure, dict):
                verdict_reason += f": {run.failure.get('message', 'Unknown error')}"
        elif evidence_missing:
            verdict = "partial"
            verdict_reason = f"Missing evidence: {', '.join(evidence_missing)}"
        else:
            verdict = "pass"
            verdict_reason = "All automated checks passed"
            if checks_skipped > 0:
                verdict_reason += f" ({checks_skipped} criteria require manual/LLM verification)"

        return ProofResult(
            verdict=verdict,
            verdict_reason=verdict_reason,
            criteria_results=criteria_results,
            evidence_collected=evidence_collected,
            evidence_missing=evidence_missing,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            checks_skipped=checks_skipped,
        )

    def _write_evidence(
        self,
        store: TraceStore,
        run: CWOMRunModel,
        task: TaskModel,
        result: ProofResult,
    ) -> str:
        """Write evidence files to trace folder.

        Returns:
            URI to evidence folder
        """
        store.ensure_dir("evidence")
        store.ensure_dir("evidence/criteria")

        # Write verdict.json
        verdict_data = {
            "verdict": result.verdict,
            "verdict_reason": result.verdict_reason,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evaluated_by": {
                "kind": "system",
                "id": self.prover_id,
            },
            "summary": {
                "checks_passed": result.checks_passed,
                "checks_failed": result.checks_failed,
                "checks_skipped": result.checks_skipped,
            },
        }
        store.write_json("evidence/verdict.json", verdict_data)

        # Write per-criterion results
        for cr in result.criteria_results:
            criterion_data = {
                "criterion": cr.criterion,
                "index": cr.index,
                "status": cr.status,
                "reason": cr.reason,
                "evidence_refs": cr.evidence_refs,
            }
            store.write_json(f"evidence/criteria/criterion_{cr.index}.json", criterion_data)

        # Write collected evidence summary
        collected_data = {
            "evidence_collected": [
                {
                    "requirement": e.requirement,
                    "index": e.index,
                    "found": e.found,
                    "artifact_uri": e.artifact_uri,
                    "artifact_type": e.artifact_type,
                    "notes": e.notes,
                }
                for e in result.evidence_collected
            ],
            "evidence_missing": result.evidence_missing,
        }
        store.write_json("evidence/collected.json", collected_data)

        # Log event
        store.append_event({
            "event": "evidence_pack_created",
            "verdict": result.verdict,
            "checks_passed": result.checks_passed,
            "checks_failed": result.checks_failed,
            "checks_skipped": result.checks_skipped,
        })

        return f"{store.get_uri()}/evidence/"

    def _create_evidence_pack(
        self,
        db: Session,
        run: CWOMRunModel,
        task: TaskModel,
        result: ProofResult,
        evidence_uri: Optional[str],
    ) -> CWOMEvidencePackModel:
        """Create EvidencePack record in database."""
        evidence_pack_id = str(uuid.uuid4())

        evidence_pack = CWOMEvidencePackModel(
            id=evidence_pack_id,
            kind="EvidencePack",
            trace_id=task.trace_id,
            for_run_id=run.id,
            for_run_kind="Run",
            for_issue_id=run.for_issue_id,
            for_issue_kind="Issue",
            verdict=result.verdict,
            verdict_reason=result.verdict_reason,
            evaluated_by_kind="system",
            evaluated_by_id=self.prover_id,
            criteria_results=[
                {
                    "criterion": cr.criterion,
                    "index": cr.index,
                    "status": cr.status,
                    "reason": cr.reason,
                    "evidence_refs": cr.evidence_refs,
                }
                for cr in result.criteria_results
            ],
            evidence_collected=[
                {
                    "requirement": e.requirement,
                    "index": e.index,
                    "found": e.found,
                    "artifact_uri": e.artifact_uri,
                    "artifact_type": e.artifact_type,
                    "notes": e.notes,
                }
                for e in result.evidence_collected
            ],
            evidence_missing=result.evidence_missing,
            checks_passed=result.checks_passed,
            checks_failed=result.checks_failed,
            checks_skipped=result.checks_skipped,
            evidence_uri=evidence_uri,
        )

        db.add(evidence_pack)

        # Audit log
        audit = AuditService(db)
        audit.log_create(
            entity_kind="EvidencePack",
            entity_id=evidence_pack_id,
            after=evidence_pack.to_dict(),
            actor_kind="system",
            actor_id=self.prover_id,
            note=f"Evidence pack created with verdict: {result.verdict}",
            trace_id=task.trace_id,
        )

        db.commit()

        return evidence_pack
