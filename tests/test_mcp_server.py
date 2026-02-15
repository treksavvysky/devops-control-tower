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
_TestSession = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine
)

# Patch SessionLocal before importing anything that uses it
db_base.SessionLocal = _TestSession


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
import devops_control_tower.mcp as mcp_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once."""
    from devops_control_tower.db import models  # noqa: F401
    from devops_control_tower.db import cwom_models  # noqa: F401
    from devops_control_tower.db import audit_models  # noqa: F401

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
        with patch.dict(
            os.environ, {"JCT_TRACE_ROOT": f"file://{d}"}
        ):
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
        assert run.executor["type"] == "claude_code"

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

        result = json.loads(
            jct_get_audit_trail(entity_kind="Run", entity_id=run_id)
        )
        assert result["success"] is True
        assert result["count"] >= 1
        # Should have at least the "created" audit entry
        assert any(
            e["action"] == "created" for e in result["entries"]
        )


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

        audit = json.loads(
            jct_get_audit_trail(entity_kind="Run", entity_id=run_id)
        )
        assert audit["count"] >= 1
