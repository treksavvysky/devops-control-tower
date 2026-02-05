"""
CWOM Contract Snapshot Tests.

These tests ensure the CWOM schemas don't accidentally change in breaking ways.
If these tests fail, it means the schema has changed - verify the change is intentional.
"""

import pytest
from pydantic import ValidationError

from devops_control_tower.cwom import (
    # Enums
    ObjectKind,
    Status,
    IssueType,
    Priority,
    RunMode,
    ArtifactType,
    VerificationStatus,
    DoctrineType,
    DoctrinePriority,
    Visibility,
    ActorKind,
    ConstraintScope,
    # Primitives
    Actor,
    Source,
    Ref,
    # Object types
    Repo,
    RepoCreate,
    Issue,
    IssueCreate,
    ContextPacket,
    ContextPacketCreate,
    ConstraintSnapshot,
    ConstraintSnapshotCreate,
    DoctrineRef,
    DoctrineRefCreate,
    Run,
    RunCreate,
    Artifact,
    ArtifactCreate,
    # Version
    __version__,
)


class TestCWOMVersion:
    """Test CWOM version."""

    def test_version_is_0_1(self):
        """CWOM version should be 0.1."""
        assert __version__ == "0.1"


class TestObjectKinds:
    """Test that all 7 CWOM object kinds are defined."""

    @pytest.mark.parametrize(
        "kind",
        ["Repo", "Issue", "ContextPacket", "Run", "Artifact", "ConstraintSnapshot", "DoctrineRef", "EvidencePack", "ReviewDecision"],
    )
    def test_object_kind_exists(self, kind: str):
        """All canonical object kinds must be defined."""
        assert kind in [k.value for k in ObjectKind]


class TestStatusEnum:
    """Test canonical status values."""

    @pytest.mark.parametrize(
        "status",
        ["planned", "ready", "running", "blocked", "done", "failed", "canceled", "under_review"],
    )
    def test_status_exists(self, status: str):
        """All canonical statuses must be defined."""
        assert status in [s.value for s in Status]


class TestIssueTypeEnum:
    """Test issue type values."""

    @pytest.mark.parametrize(
        "issue_type",
        ["feature", "bug", "chore", "research", "ops", "doc", "incident"],
    )
    def test_issue_type_exists(self, issue_type: str):
        """All canonical issue types must be defined."""
        assert issue_type in [t.value for t in IssueType]


class TestArtifactTypeEnum:
    """Test artifact type values."""

    @pytest.mark.parametrize(
        "artifact_type",
        [
            "code_patch", "commit", "pr", "build", "container_image",
            "doc", "report", "dataset", "log", "trace", "binary", "link",
        ],
    )
    def test_artifact_type_exists(self, artifact_type: str):
        """All canonical artifact types must be defined."""
        assert artifact_type in [t.value for t in ArtifactType]


class TestActorSchema:
    """Test Actor primitive schema."""

    def test_actor_required_fields(self):
        """Actor must have actor_kind and actor_id."""
        actor = Actor(actor_kind="human", actor_id="user123")
        assert actor.actor_kind == ActorKind.HUMAN
        assert actor.actor_id == "user123"
        assert actor.display is None

    def test_actor_with_display(self):
        """Actor can have optional display name."""
        actor = Actor(actor_kind="agent", actor_id="bot1", display="Helper Bot")
        assert actor.display == "Helper Bot"

    def test_actor_invalid_kind(self):
        """Actor kind must be human, agent, or system."""
        with pytest.raises(ValidationError):
            Actor(actor_kind="invalid", actor_id="test")


class TestRefSchema:
    """Test Ref primitive schema."""

    def test_ref_required_fields(self):
        """Ref must have kind and id."""
        ref = Ref(kind=ObjectKind.REPO, id="abc123")
        assert ref.kind == ObjectKind.REPO
        assert ref.id == "abc123"
        assert ref.role is None

    def test_ref_with_role(self):
        """Ref can have optional role."""
        ref = Ref(kind=ObjectKind.CONTEXT_PACKET, id="xyz", role="primary_context")
        assert ref.role == "primary_context"


class TestRepoSchema:
    """Test Repo object schema."""

    def test_repo_required_fields(self):
        """Repo must have name, slug, and source."""
        source = Source(system="github", external_id="org/repo")
        repo = Repo(name="Test Repo", slug="org/repo", source=source)
        assert repo.kind == "Repo"
        assert repo.name == "Test Repo"
        assert repo.slug == "org/repo"
        assert repo.default_branch == "main"
        assert repo.visibility == Visibility.PRIVATE

    def test_repo_has_id(self):
        """Repo gets auto-generated ID."""
        source = Source(system="github")
        repo = Repo(name="Test", slug="test", source=source)
        assert repo.id is not None
        assert len(repo.id) > 0


class TestIssueSchema:
    """Test Issue object schema."""

    def test_issue_required_fields(self):
        """Issue must have repo, title, and type."""
        repo_ref = Ref(kind=ObjectKind.REPO, id="repo123")
        issue = Issue(
            repo=repo_ref,
            title="Add feature X",
            type=IssueType.FEATURE,
        )
        assert issue.kind == "Issue"
        assert issue.title == "Add feature X"
        assert issue.type == IssueType.FEATURE
        assert issue.status == Status.PLANNED
        assert issue.priority == Priority.P2


class TestRunSchema:
    """Test Run object schema."""

    def test_run_required_fields(self):
        """Run must have for_issue, repo, mode, and executor."""
        from devops_control_tower.cwom import Executor

        actor = Actor(actor_kind="agent", actor_id="agent1")
        executor = Executor(actor=actor, runtime="local")
        issue_ref = Ref(kind=ObjectKind.ISSUE, id="issue123")
        repo_ref = Ref(kind=ObjectKind.REPO, id="repo123")

        run = Run(
            for_issue=issue_ref,
            repo=repo_ref,
            mode=RunMode.AGENT,
            executor=executor,
        )
        assert run.kind == "Run"
        assert run.mode == RunMode.AGENT
        assert run.status == Status.PLANNED


class TestArtifactSchema:
    """Test Artifact object schema."""

    def test_artifact_required_fields(self):
        """Artifact must have produced_by, for_issue, type, title, and uri."""
        run_ref = Ref(kind=ObjectKind.RUN, id="run123")
        issue_ref = Ref(kind=ObjectKind.ISSUE, id="issue123")

        artifact = Artifact(
            produced_by=run_ref,
            for_issue=issue_ref,
            type=ArtifactType.PR,
            title="Fix bug #42",
            uri="https://github.com/org/repo/pull/42",
        )
        assert artifact.kind == "Artifact"
        assert artifact.type == ArtifactType.PR
        assert artifact.verification.status == VerificationStatus.UNVERIFIED


class TestCausalityChain:
    """Test the CWOM causality chain can be constructed."""

    def test_full_chain(self):
        """Test: Issue + ContextPacket + Constraints + Doctrine → Run → Artifact."""
        from devops_control_tower.cwom import (
            ConstraintSnapshotCreate,
            ContextPacketCreate,
            DoctrineRefCreate,
            Executor,
        )

        # 1. Create Repo
        source = Source(system="github", external_id="myorg/myrepo")
        repo = Repo(name="My Repo", slug="myorg/myrepo", source=source)
        repo_ref = Ref(kind=ObjectKind.REPO, id=repo.id)

        # 2. Create Issue
        issue = Issue(
            repo=repo_ref,
            title="Add /healthz endpoint",
            type=IssueType.FEATURE,
            description="Implement health check endpoint",
        )
        issue_ref = Ref(kind=ObjectKind.ISSUE, id=issue.id)

        # 3. Create ContextPacket
        context = ContextPacket(
            for_issue=issue_ref,
            version="1.0",
            summary="Context for healthz implementation",
            instructions="Add GET /healthz returning {status: ok}",
        )
        context_ref = Ref(kind=ObjectKind.CONTEXT_PACKET, id=context.id)

        # 4. Create ConstraintSnapshot
        actor = Actor(actor_kind="human", actor_id="dev1")
        from devops_control_tower.cwom import Constraints, TimeConstraint

        constraints_data = Constraints(time=TimeConstraint(available_minutes=60))
        constraint = ConstraintSnapshot(
            scope=ConstraintScope.RUN,
            owner=actor,
            constraints=constraints_data,
        )
        constraint_ref = Ref(kind=ObjectKind.CONSTRAINT_SNAPSHOT, id=constraint.id)

        # 5. Create DoctrineRef
        doctrine = DoctrineRef(
            namespace="org/quality",
            name="test-coverage",
            version="1.0",
            type=DoctrineType.POLICY,
            priority=DoctrinePriority.MUST,
            statement="All new endpoints must have tests",
        )
        doctrine_ref = Ref(kind=ObjectKind.DOCTRINE_REF, id=doctrine.id)

        # 6. Create Run with inputs
        from devops_control_tower.cwom import RunInputs

        run_inputs = RunInputs(
            context_packets=[context_ref],
            doctrine_refs=[doctrine_ref],
            constraint_snapshot=constraint_ref,
        )
        executor = Executor(
            actor=Actor(actor_kind="agent", actor_id="claude"),
            runtime="container",
            toolchain=["pytest", "black"],
        )
        run = Run(
            for_issue=issue_ref,
            repo=repo_ref,
            mode=RunMode.AGENT,
            executor=executor,
            inputs=run_inputs,
        )
        run_ref = Ref(kind=ObjectKind.RUN, id=run.id)

        # 7. Create Artifact
        artifact = Artifact(
            produced_by=run_ref,
            for_issue=issue_ref,
            type=ArtifactType.PR,
            title="Add /healthz endpoint",
            uri="https://github.com/myorg/myrepo/pull/1",
        )

        # Verify chain is complete
        assert repo.kind == "Repo"
        assert issue.kind == "Issue"
        assert context.kind == "ContextPacket"
        assert constraint.kind == "ConstraintSnapshot"
        assert doctrine.kind == "DoctrineRef"
        assert run.kind == "Run"
        assert artifact.kind == "Artifact"

        # Verify references
        assert run.inputs.context_packets[0].id == context.id
        assert run.inputs.doctrine_refs[0].id == doctrine.id
        assert run.inputs.constraint_snapshot.id == constraint.id
        assert artifact.produced_by.id == run.id


class TestReviewDecisionContract:
    """Test ReviewDecision schema contract."""

    def test_review_decision_importable(self):
        """ReviewDecision types must be importable from cwom."""
        from devops_control_tower.cwom import (
            ReviewDecision,
            ReviewDecisionCreate,
            CriterionOverride,
            ReviewDecisionStatus,
        )
        assert ReviewDecision is not None
        assert ReviewDecisionCreate is not None
        assert CriterionOverride is not None
        assert ReviewDecisionStatus is not None

    def test_review_decision_status_values(self):
        """ReviewDecisionStatus must have all required values."""
        from devops_control_tower.cwom import ReviewDecisionStatus
        values = {s.value for s in ReviewDecisionStatus}
        assert values == {"approved", "rejected", "needs_changes"}

    def test_review_decision_required_fields(self):
        """ReviewDecision must have required fields."""
        from devops_control_tower.cwom import (
            ReviewDecision,
            ReviewDecisionStatus,
        )
        review = ReviewDecision(
            for_evidence_pack=Ref(kind=ObjectKind.EVIDENCE_PACK, id="ep1"),
            for_run=Ref(kind=ObjectKind.RUN, id="run1"),
            for_issue=Ref(kind=ObjectKind.ISSUE, id="issue1"),
            reviewer=Actor(actor_kind=ActorKind.HUMAN, actor_id="reviewer1"),
            decision=ReviewDecisionStatus.APPROVED,
            decision_reason="Approved",
        )
        assert review.kind == "ReviewDecision"
        assert review.id is not None
