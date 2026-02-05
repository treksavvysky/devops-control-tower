"""
Unit tests for ReviewDecision CWOM object.

Tests schema validation, enum values, and Pydantic models.
"""

import pytest
from pydantic import ValidationError

from devops_control_tower.cwom import (
    ReviewDecision,
    ReviewDecisionCreate,
    CriterionOverride,
    ReviewDecisionStatus,
    CriterionStatus,
    Actor,
    ActorKind,
    Ref,
    ObjectKind,
    Status,
)


class TestReviewDecisionStatus:
    """Test ReviewDecisionStatus enum."""

    def test_values(self):
        assert ReviewDecisionStatus.APPROVED.value == "approved"
        assert ReviewDecisionStatus.REJECTED.value == "rejected"
        assert ReviewDecisionStatus.NEEDS_CHANGES.value == "needs_changes"

    def test_all_values_present(self):
        values = {s.value for s in ReviewDecisionStatus}
        assert values == {"approved", "rejected", "needs_changes"}


class TestUnderReviewStatus:
    """Test that UNDER_REVIEW was added to Status enum."""

    def test_under_review_exists(self):
        assert Status.UNDER_REVIEW.value == "under_review"
        assert "under_review" in [s.value for s in Status]


class TestReviewDecisionObjectKind:
    """Test that ReviewDecision was added to ObjectKind."""

    def test_review_decision_kind_exists(self):
        assert ObjectKind.REVIEW_DECISION.value == "ReviewDecision"


class TestCriterionOverride:
    """Test CriterionOverride nested model."""

    def test_valid_override(self):
        override = CriterionOverride(
            criterion_index=0,
            original_status=CriterionStatus.UNVERIFIED,
            override_status=CriterionStatus.SATISFIED,
            reason="Manually verified",
        )
        assert override.criterion_index == 0
        assert override.original_status == CriterionStatus.UNVERIFIED
        assert override.override_status == CriterionStatus.SATISFIED

    def test_negative_index_rejected(self):
        with pytest.raises(ValidationError):
            CriterionOverride(
                criterion_index=-1,
                original_status=CriterionStatus.UNVERIFIED,
                override_status=CriterionStatus.SATISFIED,
                reason="test",
            )

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            CriterionOverride(
                criterion_index=0,
                original_status=CriterionStatus.UNVERIFIED,
                override_status=CriterionStatus.SATISFIED,
                reason="test",
                extra_field="should fail",
            )


class TestReviewDecisionSchema:
    """Test ReviewDecision Pydantic schema."""

    def _make_review(self, **kwargs):
        defaults = {
            "for_evidence_pack": Ref(kind=ObjectKind.EVIDENCE_PACK, id="ep1"),
            "for_run": Ref(kind=ObjectKind.RUN, id="run1"),
            "for_issue": Ref(kind=ObjectKind.ISSUE, id="issue1"),
            "reviewer": Actor(actor_kind=ActorKind.HUMAN, actor_id="alice"),
            "decision": ReviewDecisionStatus.APPROVED,
            "decision_reason": "LGTM",
        }
        defaults.update(kwargs)
        return ReviewDecision(**defaults)

    def test_minimal_review(self):
        review = self._make_review()
        assert review.kind == "ReviewDecision"
        assert review.decision == ReviewDecisionStatus.APPROVED
        assert review.reviewer.actor_kind == ActorKind.HUMAN
        assert len(review.criteria_overrides) == 0
        assert review.id is not None
        assert review.created_at is not None

    def test_rejected_review(self):
        review = self._make_review(
            decision=ReviewDecisionStatus.REJECTED,
            decision_reason="Tests incomplete",
        )
        assert review.decision == ReviewDecisionStatus.REJECTED
        assert review.decision_reason == "Tests incomplete"

    def test_needs_changes_review(self):
        review = self._make_review(
            decision=ReviewDecisionStatus.NEEDS_CHANGES,
            decision_reason="Fix linting issues",
        )
        assert review.decision == ReviewDecisionStatus.NEEDS_CHANGES

    def test_with_overrides(self):
        override = CriterionOverride(
            criterion_index=0,
            original_status=CriterionStatus.UNVERIFIED,
            override_status=CriterionStatus.SATISFIED,
            reason="Manually verified",
        )
        review = self._make_review(criteria_overrides=[override])
        assert len(review.criteria_overrides) == 1
        assert review.criteria_overrides[0].override_status == CriterionStatus.SATISFIED

    def test_with_tags_and_meta(self):
        review = self._make_review(
            tags=["auto-approved", "v0"],
            meta={"source": "worker"},
        )
        assert "auto-approved" in review.tags
        assert review.meta["source"] == "worker"

    def test_system_reviewer(self):
        review = self._make_review(
            reviewer=Actor(
                actor_kind=ActorKind.SYSTEM,
                actor_id="auto-approve",
                display="Auto Review",
            ),
        )
        assert review.reviewer.actor_kind == ActorKind.SYSTEM
        assert review.reviewer.display == "Auto Review"


class TestReviewDecisionCreateSchema:
    """Test ReviewDecisionCreate schema."""

    def test_create_schema(self):
        create = ReviewDecisionCreate(
            for_evidence_pack=Ref(kind=ObjectKind.EVIDENCE_PACK, id="ep1"),
            for_run=Ref(kind=ObjectKind.RUN, id="run1"),
            for_issue=Ref(kind=ObjectKind.ISSUE, id="issue1"),
            reviewer=Actor(actor_kind=ActorKind.HUMAN, actor_id="alice"),
            decision=ReviewDecisionStatus.APPROVED,
            decision_reason="LGTM",
        )
        assert create.decision == ReviewDecisionStatus.APPROVED
        assert create.criteria_overrides == []
        assert create.tags == []
        assert create.meta == {}

    def test_create_missing_required_field(self):
        with pytest.raises(ValidationError):
            ReviewDecisionCreate(
                for_evidence_pack=Ref(kind=ObjectKind.EVIDENCE_PACK, id="ep1"),
                # missing for_run, for_issue, reviewer, decision, decision_reason
            )
