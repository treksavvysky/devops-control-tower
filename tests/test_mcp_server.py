"""
Tests for JCT MCP Server tools.

Uses the same test DB pattern as conftest.py (in-memory SQLite, StaticPool).
Patches _get_db in mcp.py to use test sessions.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test env before any app imports
os.environ.setdefault("JCT_ALLOWED_REPO_PREFIXES", "testorg/")

from devops_control_tower.db import base as db_base
from devops_control_tower.db.base import Base

# Create test DB
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

# Patch SessionLocal before importing anything that uses it
db_base.SessionLocal = _TestSession


import devops_control_tower.mcp as mcp_module

# Now import MCP tools (after DB patch)
from devops_control_tower.mcp import (
    _active_claims,
    jct_claim_task,
    jct_complete_task,
    jct_enqueue_task,
    jct_get_audit_trail,
    jct_get_context,
    jct_get_evidence,
    jct_get_run,
    jct_get_task,
    jct_list_pending_reviews,
    jct_list_tasks,
    jct_report_artifact,
    jct_submit_review,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once."""
    from devops_control_tower.db import audit_models  # noqa: F401
    from devops_control_tower.db import cwom_models  # noqa: F401
    from devops_control_tower.db import models  # noqa: F401

    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(autouse=True)
def _patch_get_db(_create_tables):
    """Patch _get_db to return test sessions and clean up claims."""
    conn = _test_engine.connect()
    txn = conn.begin()
    session = _TestSession(bind=conn)

    def _test_db():
        return session

    with patch.object(mcp_module, "_get_db", _test_db):
        _active_claims.clear()
        yield session

    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture
def db(_patch_get_db) -> Session:
    """Direct DB access for seeding test data."""
    return _patch_get_db


@pytest.fixture
def trace_dir():
    """Temporary trace directory."""
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ, {"JCT_TRACE_ROOT": f"file://{d}"}):
            # Reset cached settings
            from devops_control_tower import config as cfg_mod

            old = cfg_mod.settings
            cfg_mod.settings = cfg_mod.Settings()
            yield d
            cfg_mod.settings = old


def _seed_queued_task(db: Session, objective="Test objective", operation="code_change"):
    """Seed a queued task with CWOM objects and return task_id."""
    result = json.loads(
        jct_enqueue_task(
            objective=objective,
            operation=operation,
            target_repo="testorg/test-repo",
            target_ref="main",
            time_budget_seconds=300,
        )
    )
    assert result["success"], f"Enqueue failed: {result}"
    return result["task_id"]


# ---------------------------------------------------------------------------
# TestListTasks
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_empty_queue(self):
        result = json.loads(jct_list_tasks())
        assert result["success"] is True
        assert result["count"] == 0
        assert result["tasks"] == []

    def test_queued_tasks_visible(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        result = json.loads(jct_list_tasks())
        assert result["success"] is True
        assert result["count"] == 1
        assert result["tasks"][0]["task_id"] == task_id
        assert result["tasks"][0]["status"] == "queued"

    def test_filter_by_operation(self, db, trace_dir):
        _seed_queued_task(db, operation="code_change")
        _seed_queued_task(db, objective="Write docs for API", operation="docs")

        code_tasks = json.loads(jct_list_tasks(operation="code_change"))
        assert code_tasks["count"] >= 1
        for t in code_tasks["tasks"]:
            assert t["operation"] == "code_change"

    def test_filter_by_status(self, db, trace_dir):
        _seed_queued_task(db)
        result = json.loads(jct_list_tasks(status="running"))
        assert result["success"] is True
        # No running tasks yet
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# TestClaimTask
# ---------------------------------------------------------------------------


class TestClaimTask:
    def test_claim_creates_run(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        result = json.loads(jct_claim_task(task_id))

        assert result["success"] is True
        assert result["task_id"] == task_id
        assert result["run_id"] is not None
        assert result["objective"] == "Test objective"
        assert result["operation"] == "code_change"
        assert result["constraints"]["time_budget_seconds"] == 300

    def test_claim_sets_agent_mode(self, db, trace_dir):
        from devops_control_tower.db.cwom_models import CWOMRunModel

        task_id = _seed_queued_task(db)
        result = json.loads(jct_claim_task(task_id))
        run_id = result["run_id"]

        run = db.query(CWOMRunModel).filter(CWOMRunModel.id == run_id).first()
        assert run is not None
        assert run.mode == "agent"
        assert run.executor["type"] == "mcp_agent"
        assert run.executor["worker_id"] == "test-executor@pytest"

    def test_claim_returns_context_packet(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        result = json.loads(jct_claim_task(task_id))

        assert result["success"] is True
        assert result["context_packet"] is not None
        assert "id" in result["context_packet"]

    def test_claim_already_claimed(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        # First claim succeeds
        r1 = json.loads(jct_claim_task(task_id))
        assert r1["success"] is True

        # Second claim fails
        r2 = json.loads(jct_claim_task(task_id))
        assert r2["success"] is False
        assert r2["error"]["code"] == "TASK_ALREADY_CLAIMED"

    def test_claim_nonexistent_task(self):
        result = json.loads(jct_claim_task("nonexistent-id"))
        assert result["success"] is False
        assert result["error"]["code"] == "TASK_NOT_FOUND"

    def test_claim_stores_active_claim(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        result = json.loads(jct_claim_task(task_id))
        assert task_id in _active_claims
        assert _active_claims[task_id]["run_id"] == result["run_id"]


# ---------------------------------------------------------------------------
# TestGetContext
# ---------------------------------------------------------------------------


class TestGetContext:
    def test_get_context_for_claimed_task(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        jct_claim_task(task_id)

        result = json.loads(jct_get_context(task_id))
        assert result["success"] is True
        assert result["task_id"] == task_id
        assert "issue" in result
        assert "context_packet" in result

    def test_get_context_nonexistent_task(self):
        result = json.loads(jct_get_context("nonexistent-id"))
        assert result["success"] is False
        assert result["error"]["code"] == "TASK_NOT_FOUND"


# ---------------------------------------------------------------------------
# TestReportArtifact
# ---------------------------------------------------------------------------


class TestReportArtifact:
    def test_report_with_content(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        jct_claim_task(task_id)

        result = json.loads(
            jct_report_artifact(
                task_id=task_id,
                title="Code changes",
                artifact_type="code_patch",
                content="diff --git a/foo.py b/foo.py\n+hello",
                media_type="application/x-patch",
            )
        )

        assert result["success"] is True
        assert result["artifact_id"] is not None
        assert result["title"] == "Code changes"
        assert result["type"] == "code_patch"
        assert result["uri"] is not None

    def test_report_creates_cwom_artifact(self, db, trace_dir):
        from devops_control_tower.db.cwom_models import CWOMArtifactModel

        task_id = _seed_queued_task(db)
        jct_claim_task(task_id)

        result = json.loads(
            jct_report_artifact(
                task_id=task_id,
                title="Test results",
                artifact_type="log",
                content="All tests passed",
            )
        )

        artifact = (
            db.query(CWOMArtifactModel)
            .filter(CWOMArtifactModel.id == result["artifact_id"])
            .first()
        )
        assert artifact is not None
        assert artifact.type == "log"
        assert artifact.title == "Test results"

    def test_report_without_claim(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        # Don't claim — just try to report
        # Need to claim to make it running first, otherwise task won't be found
        # as running. The tool should still work if task exists but no claim.
        result = json.loads(
            jct_report_artifact(
                task_id=task_id,
                title="Orphan",
                artifact_type="doc",
                content="test",
            )
        )
        # Should error because no active claim
        assert result["success"] is False
        assert result["error"]["code"] == "NO_ACTIVE_CLAIM"


# ---------------------------------------------------------------------------
# TestCompleteTask
# ---------------------------------------------------------------------------


class TestCompleteTask:
    def test_success_triggers_prove(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        jct_claim_task(task_id)

        # Report an artifact first
        jct_report_artifact(
            task_id=task_id,
            title="Output",
            artifact_type="doc",
            content="Result content",
        )

        result = json.loads(
            jct_complete_task(
                task_id=task_id,
                success=True,
                summary="Work completed successfully",
            )
        )

        assert result["success"] is True
        assert result["task_status"] == "completed"
        assert result["run_status"] in ("done", "under_review")
        assert "evidence_pack" in result
        assert result["evidence_pack"]["verdict"] in (
            "pass",
            "fail",
            "partial",
        )

    def test_failure_sets_failed(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        jct_claim_task(task_id)

        result = json.loads(
            jct_complete_task(
                task_id=task_id,
                success=False,
                summary="Could not complete",
                error_message="Dependency conflict",
            )
        )

        assert result["success"] is True
        assert result["task_status"] == "failed"
        assert result["run_status"] == "failed"
        # Prove still runs on failure
        assert result["evidence_pack"]["verdict"] == "fail"

    def test_auto_approve_flow(self, db, trace_dir):
        # Enable auto-approve
        from devops_control_tower import config as cfg_mod

        old = cfg_mod.settings
        cfg_mod.settings = cfg_mod.Settings(
            jct_review_auto_approve=True,
            jct_review_auto_approve_verdicts="pass",
        )

        try:
            task_id = _seed_queued_task(db)
            jct_claim_task(task_id)
            jct_report_artifact(
                task_id=task_id,
                title="Output",
                artifact_type="doc",
                content="Done",
            )

            result = json.loads(
                jct_complete_task(
                    task_id=task_id,
                    success=True,
                    summary="All done",
                )
            )

            assert result["success"] is True
            # Auto-approve may set done if verdict=pass
            if result["evidence_pack"]["verdict"] == "pass":
                assert result["review"]["status"] == "auto_approved"
                assert result["run_status"] == "done"
        finally:
            cfg_mod.settings = old

    def test_complete_not_running_task(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        # Don't claim — task is still queued
        result = json.loads(
            jct_complete_task(
                task_id=task_id,
                success=True,
                summary="test",
            )
        )
        assert result["success"] is False
        assert result["error"]["code"] == "TASK_NOT_RUNNING"

    def test_complete_clears_active_claim(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        jct_claim_task(task_id)
        assert task_id in _active_claims

        jct_complete_task(
            task_id=task_id,
            success=True,
            summary="Done",
        )
        assert task_id not in _active_claims


# ---------------------------------------------------------------------------
# TestEnqueueTask
# ---------------------------------------------------------------------------


class TestEnqueueTask:
    def test_enqueue_creates_task(self, db, trace_dir):
        result = json.loads(
            jct_enqueue_task(
                objective="Add a hello endpoint",
                operation="code_change",
                target_repo="testorg/api",
                time_budget_seconds=600,
            )
        )

        assert result["success"] is True
        assert result["task_id"] is not None
        assert result["trace_id"] is not None
        assert result["status"] == "queued"

    def test_enqueue_creates_cwom(self, db, trace_dir):
        result = json.loads(
            jct_enqueue_task(
                objective="Write docs",
                operation="docs",
                target_repo="testorg/docs-repo",
            )
        )

        assert result["success"] is True
        assert "cwom" in result
        assert result["cwom"]["issue_id"] is not None
        assert result["cwom"]["context_packet_id"] is not None

    def test_enqueue_policy_rejection(self, db, trace_dir):
        result = json.loads(
            jct_enqueue_task(
                objective="Hack the mainframe",
                operation="code_change",
                target_repo="evil-org/bad-repo",
            )
        )

        assert result["success"] is False
        assert result["error"]["code"] == "REPO_NOT_ALLOWED"

    def test_enqueue_idempotency(self, db, trace_dir):
        key = f"idem-{uuid.uuid4().hex[:8]}"

        r1 = json.loads(
            jct_enqueue_task(
                objective="First attempt",
                operation="analysis",
                target_repo="testorg/repo",
                idempotency_key=key,
            )
        )
        assert r1["success"] is True

        r2 = json.loads(
            jct_enqueue_task(
                objective="Duplicate attempt",
                operation="analysis",
                target_repo="testorg/repo",
                idempotency_key=key,
            )
        )
        assert r2["success"] is False
        assert r2["error"]["code"] == "IDEMPOTENCY_CONFLICT"


# ---------------------------------------------------------------------------
# TestObservationTools
# ---------------------------------------------------------------------------


class TestObservationTools:
    def test_get_task(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        result = json.loads(jct_get_task(task_id))

        assert result["success"] is True
        assert result["task"]["task_id"] == task_id

    def test_get_task_not_found(self):
        result = json.loads(jct_get_task("nonexistent"))
        assert result["success"] is False
        assert result["error"]["code"] == "TASK_NOT_FOUND"

    def test_get_run(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        claim = json.loads(jct_claim_task(task_id))
        run_id = claim["run_id"]

        result = json.loads(jct_get_run(run_id))
        assert result["success"] is True
        assert result["run"]["id"] == run_id
        assert result["run"]["mode"] == "agent"

    def test_get_run_not_found(self):
        result = json.loads(jct_get_run("nonexistent"))
        assert result["success"] is False
        assert result["error"]["code"] == "RUN_NOT_FOUND"

    def test_get_evidence(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        claim = json.loads(jct_claim_task(task_id))
        run_id = claim["run_id"]

        jct_report_artifact(
            task_id=task_id,
            title="Output",
            artifact_type="doc",
            content="Content",
        )
        jct_complete_task(
            task_id=task_id,
            success=True,
            summary="Done",
        )

        result = json.loads(jct_get_evidence(run_id))
        assert result["success"] is True
        assert "evidence_pack" in result
        assert result["evidence_pack"]["verdict"] in (
            "pass",
            "fail",
            "partial",
        )

    def test_get_evidence_not_found(self):
        result = json.loads(jct_get_evidence("nonexistent"))
        assert result["success"] is False
        assert result["error"]["code"] == "EVIDENCE_NOT_FOUND"

    def test_get_audit_trail(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        claim = json.loads(jct_claim_task(task_id))
        run_id = claim["run_id"]

        result = json.loads(jct_get_audit_trail(entity_kind="Run", entity_id=run_id))
        assert result["success"] is True
        assert result["count"] >= 1
        # Should have at least the "created" audit entry
        assert any(e["action"] == "created" for e in result["entries"])


# ---------------------------------------------------------------------------
# TestReviewTools
# ---------------------------------------------------------------------------


class TestReviewTools:
    def test_list_pending_reviews_empty(self):
        result = json.loads(jct_list_pending_reviews())
        assert result["success"] is True
        assert result["count"] == 0

    def test_submit_review_invalid_decision(self, db, trace_dir):
        result = json.loads(
            jct_submit_review(
                evidence_pack_id="fake",
                decision="maybe",
                reason="not sure",
            )
        )
        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_DECISION"

    def test_submit_review_not_found(self, db, trace_dir):
        result = json.loads(
            jct_submit_review(
                evidence_pack_id="nonexistent",
                decision="approved",
                reason="looks good",
            )
        )
        assert result["success"] is False
        assert result["error"]["code"] == "EVIDENCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# TestFullWorkflow
# ---------------------------------------------------------------------------


class TestFullWorkflow:
    def test_enqueue_claim_report_complete(self, db, trace_dir):
        """End-to-end: enqueue → claim → report → complete → evidence."""
        # 1. Enqueue
        enqueue = json.loads(
            jct_enqueue_task(
                objective="Add hello endpoint to API",
                operation="code_change",
                target_repo="testorg/api-service",
                time_budget_seconds=600,
            )
        )
        assert enqueue["success"] is True
        task_id = enqueue["task_id"]

        # 2. List and verify
        tasks = json.loads(jct_list_tasks())
        task_ids = [t["task_id"] for t in tasks["tasks"]]
        assert task_id in task_ids

        # 3. Claim
        claim = json.loads(jct_claim_task(task_id))
        assert claim["success"] is True
        assert claim["run_id"] is not None
        run_id = claim["run_id"]

        # 4. Get context
        ctx = json.loads(jct_get_context(task_id))
        assert ctx["success"] is True

        # 5. Report artifacts
        art = json.loads(
            jct_report_artifact(
                task_id=task_id,
                title="Code diff",
                artifact_type="code_patch",
                content="--- a/main.py\n+++ b/main.py\n+# hello",
            )
        )
        assert art["success"] is True

        # 6. Complete
        complete = json.loads(
            jct_complete_task(
                task_id=task_id,
                success=True,
                summary="Added hello endpoint",
            )
        )
        assert complete["success"] is True
        assert complete["task_status"] == "completed"
        assert "evidence_pack" in complete

        # 7. Verify via observation tools
        task_detail = json.loads(jct_get_task(task_id))
        assert task_detail["task"]["status"] == "completed"

        run_detail = json.loads(jct_get_run(run_id))
        assert run_detail["success"] is True

        evidence = json.loads(jct_get_evidence(run_id))
        assert evidence["success"] is True

        audit = json.loads(jct_get_audit_trail(entity_kind="Run", entity_id=run_id))
        assert audit["count"] >= 1


# ---------------------------------------------------------------------------
# Execution record fixes (DEVOPS-CON-3): G1 identity, G3 self-review,
# G5 artifact digest, G7 claim leases
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402
import hashlib  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from datetime import timedelta  # noqa: E402


@contextmanager
def _as_actor(actor):
    """Temporarily run MCP tools as a different JCT_ACTOR_ID (None = unset)."""
    from devops_control_tower import config as cfg_mod

    old = cfg_mod.settings.jct_actor_id
    cfg_mod.settings.jct_actor_id = actor
    try:
        yield
    finally:
        cfg_mod.settings.jct_actor_id = old


def _claimed_task(db, budget=300):
    task_id = json.loads(
        jct_enqueue_task(
            objective="Lease/identity test",
            operation="analysis",
            target_repo="testorg/test-repo",
            time_budget_seconds=budget,
        )
    )["task_id"]
    claim = json.loads(jct_claim_task(task_id))
    assert claim["success"], claim
    return task_id, claim


def _completed_for_review(db):
    """Enqueue, claim, report and complete as the default executor (manual review)."""
    task_id, claim = _claimed_task(db)
    jct_report_artifact(
        task_id=task_id, title="Report", artifact_type="doc", content="findings"
    )
    done = json.loads(jct_complete_task(task_id=task_id, success=True, summary="ok"))
    assert done["success"], done
    return task_id, claim["run_id"], done["evidence_pack"]["id"]


def _expire_lease(db, task_id):
    from devops_control_tower.db.models import TaskModel

    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    task.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()


class TestExecutorIdentity:
    def test_claim_refused_without_actor(self, db, trace_dir):
        task_id = _seed_queued_task(db)
        with _as_actor(None):
            result = json.loads(jct_claim_task(task_id))
        assert result["success"] is False
        assert result["error"]["code"] == "ACTOR_NOT_CONFIGURED"
        task = json.loads(jct_get_task(task_id))["task"]
        assert task["status"] == "queued"

    def test_claim_records_actor_everywhere(self, db, trace_dir):
        from devops_control_tower.db.audit_models import AuditLogModel
        from devops_control_tower.db.cwom_models import CWOMRunModel
        from devops_control_tower.db.models import TaskModel

        with _as_actor("Codex@codejourney"):
            task_id, claim = _claimed_task(db)
            jct_report_artifact(
                task_id=task_id, title="R", artifact_type="doc", content="x"
            )
            jct_complete_task(task_id=task_id, success=True, summary="ok")

        assert claim["executor"] == "Codex@codejourney"
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        assert task.assigned_to == "Codex@codejourney"
        run = db.query(CWOMRunModel).filter(CWOMRunModel.id == claim["run_id"]).first()
        assert run.executor["worker_id"] == "Codex@codejourney"

        agent_rows = (
            db.query(AuditLogModel)
            .filter(AuditLogModel.actor_kind == "agent")
            .all()
        )
        assert agent_rows
        assert all(r.actor_id != "claude-code" for r in agent_rows)
        assert {"Codex@codejourney"} >= {
            r.actor_id for r in agent_rows if r.entity_kind in ("Run", "Artifact")
        }

    def test_other_actor_cannot_complete(self, db, trace_dir):
        task_id, _ = _claimed_task(db)
        with _as_actor("Someone@else"):
            result = json.loads(
                jct_complete_task(task_id=task_id, success=True, summary="hijack")
            )
        assert result["success"] is False
        assert result["error"]["code"] == "CLAIM_NOT_HELD"


class TestNoSelfReview:
    def test_mcp_self_review_refused(self, db, trace_dir):
        _, _, ep_id = _completed_for_review(db)
        result = json.loads(
            jct_submit_review(
                evidence_pack_id=ep_id, decision="approved", reason="lgtm"
            )
        )
        assert result["success"] is False
        assert result["error"]["code"] == "SELF_REVIEW_FORBIDDEN"

    def test_mcp_review_ignores_reviewer_name_for_identity(self, db, trace_dir):
        _, _, ep_id = _completed_for_review(db)
        result = json.loads(
            jct_submit_review(
                evidence_pack_id=ep_id,
                decision="approved",
                reason="lgtm",
                reviewer_name="George",  # display only; identity is still the executor
            )
        )
        assert result["error"]["code"] == "SELF_REVIEW_FORBIDDEN"

    def test_mcp_review_by_other_actor_accepted(self, db, trace_dir):
        from devops_control_tower.db.cwom_models import CWOMReviewDecisionModel

        _, run_id, ep_id = _completed_for_review(db)
        with _as_actor("Reviewer@codejourney"):
            result = json.loads(
                jct_submit_review(
                    evidence_pack_id=ep_id, decision="approved", reason="checked"
                )
            )
        assert result["success"] is True, result
        review = (
            db.query(CWOMReviewDecisionModel)
            .filter(CWOMReviewDecisionModel.id == result["review_id"])
            .first()
        )
        assert review.reviewer_id == "Reviewer@codejourney"
        assert review.for_run_id == run_id

    def _rest_review(self, db, run_id, ep_id, issue_id, reviewer_id):
        from devops_control_tower.cwom.review_decision import ReviewDecisionCreate
        from devops_control_tower.cwom.routes import create_review

        body = ReviewDecisionCreate(
            for_evidence_pack={"kind": "EvidencePack", "id": ep_id},
            for_run={"kind": "Run", "id": run_id},
            for_issue={"kind": "Issue", "id": issue_id},
            reviewer={"actor_kind": "human", "actor_id": reviewer_id},
            decision="approved",
            decision_reason="test",
        )
        return asyncio.run(create_review(body, db=db))

    def _ids(self, db, run_id):
        from devops_control_tower.db.cwom_models import CWOMRunModel

        run = db.query(CWOMRunModel).filter(CWOMRunModel.id == run_id).first()
        return run.for_issue_id

    def test_rest_self_review_is_403(self, db, trace_dir):
        from fastapi import HTTPException

        _, run_id, ep_id = _completed_for_review(db)
        with pytest.raises(HTTPException) as exc:
            self._rest_review(
                db, run_id, ep_id, self._ids(db, run_id), "test-executor@pytest"
            )
        assert exc.value.status_code == 403

    def test_rest_review_by_human_accepted(self, db, trace_dir):
        _, run_id, ep_id = _completed_for_review(db)
        out = self._rest_review(db, run_id, ep_id, self._ids(db, run_id), "george")
        assert out["status"] == "success"
        assert out["review"]["decision"] == "approved"

    def test_rest_review_run_must_match_evidence(self, db, trace_dir):
        from fastapi import HTTPException

        _, run_a, ep_a = _completed_for_review(db)
        _, run_b, _ = _completed_for_review(db)
        with pytest.raises(HTTPException) as exc:
            self._rest_review(db, run_b, ep_a, self._ids(db, run_a), "george")
        assert exc.value.status_code == 400


class TestArtifactDigest:
    def test_digest_and_size_recorded(self, db, trace_dir):
        from devops_control_tower.db.cwom_models import CWOMArtifactModel

        content = "## Findings\n\nnon-ASCII: é ✓\n"
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        task_id, _ = _claimed_task(db)
        art = json.loads(
            jct_report_artifact(
                task_id=task_id,
                title="findings.md",
                artifact_type="doc",
                content=content,
            )
        )
        assert art["success"] is True
        assert art["digest"] == f"sha256:{expected}"
        assert art["size_bytes"] == len(content.encode("utf-8"))

        row = (
            db.query(CWOMArtifactModel)
            .filter(CWOMArtifactModel.id == art["artifact_id"])
            .first()
        )
        assert row.digest == f"sha256:{expected}"
        assert row.size_bytes == len(content.encode("utf-8"))

        # The stored file hashes to the same digest
        path = art["uri"].replace("file://", "", 1)
        with open(path, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == expected

    def test_final_manifest_lists_digest_and_executor(self, db, trace_dir):
        task_id, claim = _claimed_task(db)
        art = json.loads(
            jct_report_artifact(
                task_id=task_id, title="out", artifact_type="doc", content="abc"
            )
        )
        jct_complete_task(task_id=task_id, success=True, summary="ok")
        manifest_path = os.path.join(trace_dir, claim["run_id"], "manifest.json")
        with open(manifest_path) as fh:
            manifest = json.load(fh)
        assert manifest["executor"]["worker_id"] == "test-executor@pytest"
        assert manifest["artifacts"][0]["digest"] == art["digest"]
        assert manifest["artifacts"][0]["size_bytes"] == 3


class TestClaimLeases:
    def test_claim_sets_lease_budget_plus_grace(self, db, trace_dir):
        from devops_control_tower.db.models import TaskModel
        from devops_control_tower.worker.leases import _as_utc

        before = datetime.now(timezone.utc)
        task_id, claim = _claimed_task(db, budget=600)
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        lease = _as_utc(task.lease_expires_at)
        assert before + timedelta(seconds=900) <= lease
        assert lease <= datetime.now(timezone.utc) + timedelta(seconds=901)
        assert claim["lease_expires_at"]

    def test_expired_lease_requeued_on_list(self, db, trace_dir):
        from devops_control_tower.db.audit_models import AuditLogModel
        from devops_control_tower.db.cwom_models import CWOMRunModel

        task_id, claim = _claimed_task(db)
        _expire_lease(db, task_id)

        listed = json.loads(jct_list_tasks())
        assert task_id in [t["task_id"] for t in listed["tasks"]]

        task = json.loads(jct_get_task(task_id))["task"]
        assert task["status"] == "queued"
        assert task["assigned_to"] is None
        run = db.query(CWOMRunModel).filter(CWOMRunModel.id == claim["run_id"]).first()
        assert run.status == "failed"
        assert run.failure["code"] == "LEASE_EXPIRED"
        audit = (
            db.query(AuditLogModel)
            .filter(
                AuditLogModel.entity_kind == "Task",
                AuditLogModel.entity_id == task_id,
                AuditLogModel.action == "status_changed",
            )
            .all()
        )
        assert any(a.actor_id.startswith("lease-reaper") for a in audit)

    def test_late_completion_after_reclaim_refused(self, db, trace_dir):
        task_id, first = _claimed_task(db)
        _expire_lease(db, task_id)

        # Another executor reclaims the task
        with _as_actor("Second@executor"):
            second = json.loads(jct_claim_task(task_id))
        assert second["success"] is True, second
        assert second["run_id"] != first["run_id"]

        # The first executor's late completion is refused
        late = json.loads(
            jct_complete_task(task_id=task_id, success=True, summary="late")
        )
        assert late["success"] is False
        assert late["error"]["code"] in ("CLAIM_NOT_HELD", "CLAIM_LOST")

        # The second executor can still complete
        with _as_actor("Second@executor"):
            ok = json.loads(
                jct_complete_task(task_id=task_id, success=True, summary="ok")
            )
        assert ok["success"] is True, ok

    def test_same_actor_stale_claim_refused(self, db, trace_dir):
        """Same identity, new session: the stale run's late completion is refused."""
        task_id, first = _claimed_task(db)
        _expire_lease(db, task_id)
        stale_claim = dict(_active_claims[task_id])
        _active_claims.clear()  # simulate a new session for the same identity
        second = json.loads(jct_claim_task(task_id))
        assert second["success"] is True
        _active_claims[task_id] = stale_claim  # the old session still holds the old run
        late = json.loads(
            jct_complete_task(task_id=task_id, success=True, summary="late")
        )
        assert late["success"] is False
        assert late["error"]["code"] == "CLAIM_LOST"

    def test_report_after_expiry_refused(self, db, trace_dir):
        task_id, _ = _claimed_task(db)
        _expire_lease(db, task_id)
        result = json.loads(
            jct_report_artifact(
                task_id=task_id, title="late", artifact_type="doc", content="x"
            )
        )
        assert result["success"] is False
        assert result["error"]["code"] in (
            "TASK_NOT_RUNNING",
            "NO_ACTIVE_CLAIM",
            "CLAIM_LOST",
        )

    def test_unexpired_lease_not_requeued(self, db, trace_dir):
        from devops_control_tower.worker.leases import requeue_expired

        task_id, _ = _claimed_task(db)
        assert requeue_expired(db) == []
        assert json.loads(jct_get_task(task_id))["task"]["status"] == "running"

    def test_completion_clears_lease(self, db, trace_dir):
        from devops_control_tower.db.models import TaskModel

        task_id, _ = _claimed_task(db)
        jct_complete_task(task_id=task_id, success=True, summary="ok")
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        assert task.lease_expires_at is None


class TestWorkerLease:
    def test_worker_claim_sets_lease_and_reaps(self, db, trace_dir):
        from devops_control_tower.db.models import TaskModel
        from devops_control_tower.worker.leases import requeue_expired
        from devops_control_tower.worker.loop import WorkerLoop

        task_id = _seed_queued_task(db)
        worker = WorkerLoop(executor_type="stub")
        claimed = worker._claim_task(db)
        assert claimed is not None and str(claimed.id) == task_id
        assert claimed.assigned_to == worker.worker_id
        assert claimed.lease_expires_at is not None

        _expire_lease(db, task_id)
        assert requeue_expired(db, actor_id=f"lease-reaper:{worker.worker_id}") == [
            task_id
        ]
        task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
        db.refresh(task)
        assert task.status == "queued"
