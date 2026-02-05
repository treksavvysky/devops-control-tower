"""
API tests for ReviewDecision endpoints.

Tests the review flow: POST review -> status transitions, GET, LIST.
"""

import pytest
from fastapi.testclient import TestClient

from devops_control_tower.api import app
from devops_control_tower.db.base import get_db
from devops_control_tower.db.cwom_models import (
    CWOMEvidencePackModel,
    CWOMIssueModel,
    CWOMRepoModel,
    CWOMReviewDecisionModel,
    CWOMRunModel,
)

# Use module-level client (DB configured in conftest.py)
client = TestClient(app)

# Unique suffix per module to avoid collisions with other test files
_SUFFIX = "review"


def _seed_review_data(suffix: str = ""):
    """Seed repo -> issue -> run -> evidence_pack for review testing.

    Returns dict with all created IDs.
    """
    tag = f"{_SUFFIX}-{suffix}" if suffix else _SUFFIX

    # Create repo
    resp = client.post(
        "/cwom/repos",
        json={
            "name": f"Review Test Repo {tag}",
            "slug": f"testorg/review-{tag}",
            "source": {"system": "github"},
        },
    )
    assert resp.status_code == 201, resp.text
    repo_id = resp.json()["repo"]["id"]

    # Create issue
    resp = client.post(
        "/cwom/issues",
        json={
            "repo": {"kind": "Repo", "id": repo_id},
            "title": f"Review test issue {tag}",
            "type": "feature",
        },
    )
    assert resp.status_code == 201, resp.text
    issue_id = resp.json()["issue"]["id"]

    # Create run
    resp = client.post(
        "/cwom/runs",
        json={
            "for_issue": {"kind": "Issue", "id": issue_id},
            "repo": {"kind": "Repo", "id": repo_id},
            "mode": "agent",
            "executor": {
                "actor": {"actor_kind": "system", "actor_id": "worker-1"},
                "runtime": "local",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["run"]["id"]

    # Update run to done (prover expects this)
    resp = client.patch(
        f"/cwom/runs/{run_id}",
        json={"status": "done"},
    )
    assert resp.status_code == 200, resp.text

    # Update issue to under_review (required for review submission)
    resp = client.patch(
        f"/cwom/issues/{issue_id}/status?status=under_review",
    )
    assert resp.status_code == 200, resp.text

    # Create evidence pack via the prover or directly
    # Since there's no POST endpoint for evidence packs, we'll create via DB
    # But let's check if there's a create endpoint...
    # No POST endpoint exists for evidence packs - they're created by the prover.
    # We need to create one directly in the DB via the service or a test helper.
    # For now, use the internal route.

    return {
        "repo_id": repo_id,
        "issue_id": issue_id,
        "run_id": run_id,
    }


def _create_evidence_pack_direct(run_id: str, issue_id: str) -> str:
    """Create an evidence pack directly via DB since there's no POST endpoint."""
    from tests.conftest import TestSessionLocal
    from devops_control_tower.cwom.primitives import generate_ulid

    # Use the test session (same DB as TestClient)
    db = TestSessionLocal()
    try:
        ep = CWOMEvidencePackModel(
            id=generate_ulid(),
            kind="EvidencePack",
            for_run_id=run_id,
            for_run_kind="Run",
            for_issue_id=issue_id,
            for_issue_kind="Issue",
            verdict="pass",
            verdict_reason="All checks passed",
            evaluated_by_kind="system",
            evaluated_by_id="prover-test",
            criteria_results=[],
            evidence_collected=[],
            evidence_missing=[],
            checks_passed=3,
            checks_failed=0,
            checks_skipped=0,
        )
        db.add(ep)
        db.commit()
        return ep.id
    finally:
        db.close()


class TestCreateReview:
    """Test POST /cwom/reviews."""

    def test_approve_review(self):
        """Approved review transitions Issue/Run to done."""
        ids = _seed_review_data("approve")
        ep_id = _create_evidence_pack_direct(ids["run_id"], ids["issue_id"])

        resp = client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {
                    "actor_kind": "human",
                    "actor_id": "alice",
                    "display": "Alice (Lead)",
                },
                "decision": "approved",
                "decision_reason": "LGTM - all checks passed",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "success"
        assert data["review"]["decision"] == "approved"
        assert data["review"]["reviewer"]["actor_id"] == "alice"

        # Verify Issue transitioned to done
        issue_resp = client.get(f"/cwom/issues/{ids['issue_id']}")
        assert issue_resp.json()["status"] == "done"

        # Verify Run transitioned to done
        run_resp = client.get(f"/cwom/runs/{ids['run_id']}")
        assert run_resp.json()["status"] == "done"

    def test_reject_review(self):
        """Rejected review transitions Issue/Run to failed."""
        ids = _seed_review_data("reject")
        ep_id = _create_evidence_pack_direct(ids["run_id"], ids["issue_id"])

        resp = client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {
                    "actor_kind": "human",
                    "actor_id": "bob",
                },
                "decision": "rejected",
                "decision_reason": "Tests incomplete",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["review"]["decision"] == "rejected"

        # Verify Issue/Run transitioned to failed
        issue_resp = client.get(f"/cwom/issues/{ids['issue_id']}")
        assert issue_resp.json()["status"] == "failed"

    def test_needs_changes_review(self):
        """needs_changes review transitions Issue/Run to failed."""
        ids = _seed_review_data("needschanges")
        ep_id = _create_evidence_pack_direct(ids["run_id"], ids["issue_id"])

        resp = client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {"actor_kind": "human", "actor_id": "carol"},
                "decision": "needs_changes",
                "decision_reason": "Fix linting",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["review"]["decision"] == "needs_changes"

    def test_review_wrong_issue_status(self):
        """Review on issue not in under_review status returns 400."""
        ids = _seed_review_data("wrongstatus")
        ep_id = _create_evidence_pack_direct(ids["run_id"], ids["issue_id"])

        # Change issue to done first
        client.patch(
            f"/cwom/issues/{ids['issue_id']}/status?status=done",
        )

        resp = client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {"actor_kind": "human", "actor_id": "alice"},
                "decision": "approved",
                "decision_reason": "LGTM",
            },
        )
        assert resp.status_code == 400
        assert "not under review" in resp.json()["detail"].lower()

    def test_review_nonexistent_evidence_pack(self):
        """Review referencing missing evidence pack returns 400."""
        ids = _seed_review_data("noep")

        resp = client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": "nonexistent"},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {"actor_kind": "human", "actor_id": "alice"},
                "decision": "approved",
                "decision_reason": "LGTM",
            },
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()


class TestGetReview:
    """Test GET /cwom/reviews/{id}."""

    def test_get_by_id(self):
        """Get review by ID."""
        ids = _seed_review_data("getbyid")
        ep_id = _create_evidence_pack_direct(ids["run_id"], ids["issue_id"])

        # Create review
        create_resp = client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {"actor_kind": "human", "actor_id": "alice"},
                "decision": "approved",
                "decision_reason": "LGTM",
            },
        )
        review_id = create_resp.json()["review"]["id"]

        # Get by ID
        resp = client.get(f"/cwom/reviews/{review_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == review_id
        assert resp.json()["decision"] == "approved"

    def test_get_not_found(self):
        """Get nonexistent review returns 404."""
        resp = client.get("/cwom/reviews/nonexistent")
        assert resp.status_code == 404


class TestListReviews:
    """Test GET /cwom/reviews and convenience list endpoints."""

    def test_list_all(self):
        """List all reviews returns 200."""
        resp = client.get("/cwom/reviews")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_with_decision_filter(self):
        """List reviews filtered by decision."""
        resp = client.get("/cwom/reviews?decision=approved")
        assert resp.status_code == 200
        for r in resp.json():
            assert r["decision"] == "approved"


class TestReviewConvenienceEndpoints:
    """Test convenience endpoints for reviews."""

    def test_get_review_for_evidence_pack(self):
        """GET /cwom/evidence-packs/{id}/review."""
        ids = _seed_review_data("epconv")
        ep_id = _create_evidence_pack_direct(ids["run_id"], ids["issue_id"])

        # Create review
        client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {"actor_kind": "human", "actor_id": "alice"},
                "decision": "approved",
                "decision_reason": "LGTM",
            },
        )

        resp = client.get(f"/cwom/evidence-packs/{ep_id}/review")
        assert resp.status_code == 200
        assert resp.json()["for_evidence_pack"]["id"] == ep_id

    def test_get_review_for_ep_not_found(self):
        """GET /cwom/evidence-packs/{id}/review returns 404 when no review."""
        resp = client.get("/cwom/evidence-packs/nonexistent/review")
        assert resp.status_code == 404

    def test_list_reviews_for_issue(self):
        """GET /cwom/issues/{id}/reviews."""
        ids = _seed_review_data("issueconv")
        ep_id = _create_evidence_pack_direct(ids["run_id"], ids["issue_id"])

        client.post(
            "/cwom/reviews",
            json={
                "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
                "for_run": {"kind": "Run", "id": ids["run_id"]},
                "for_issue": {"kind": "Issue", "id": ids["issue_id"]},
                "reviewer": {"actor_kind": "human", "actor_id": "alice"},
                "decision": "approved",
                "decision_reason": "LGTM",
            },
        )

        resp = client.get(f"/cwom/issues/{ids['issue_id']}/reviews")
        assert resp.status_code == 200
        reviews = resp.json()
        assert len(reviews) >= 1
        assert reviews[0]["for_issue"]["id"] == ids["issue_id"]
