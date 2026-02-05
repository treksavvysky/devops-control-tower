"""Phase 3: CWOM CRUD Integration Tests.

Tests DB round-trips, relationship loading, join table queries, the full
causality chain, immutability enforcement, status transitions, audit trails,
and edge cases — all through the CWOM service layer against a real database.
"""

import time

import pytest
from datetime import datetime, timezone

from devops_control_tower.cwom import (
    RepoCreate,
    IssueCreate,
    ContextPacketCreate,
    ConstraintSnapshotCreate,
    DoctrineRefCreate,
    RunCreate,
    RunUpdate,
    ArtifactCreate,
    Actor,
    ActorKind,
    Source,
    Ref,
    ObjectKind,
    Executor,
    IssueType,
    Priority,
    Status,
    RunMode,
    ArtifactType,
    ConstraintScope,
    DoctrineType,
    DoctrinePriority,
    Constraints,
    RunInputs,
    Telemetry,
    Failure,
    FailureCategory,
    generate_ulid,
)
from devops_control_tower.cwom.services import (
    RepoService,
    IssueService,
    ContextPacketService,
    ConstraintSnapshotService,
    DoctrineRefService,
    RunService,
    ArtifactService,
    EvidencePackService,
    ReviewDecisionService,
)
from devops_control_tower.db.cwom_models import (
    CWOMEvidencePackModel,
    CWOMRepoModel,
)
from devops_control_tower.db.audit_service import AuditService


# =============================================================================
# Factory helpers — return Pydantic *Create schemas with unique identifiers
# =============================================================================

_counter = 0


def _next():
    global _counter
    _counter += 1
    return _counter


def make_repo_create(suffix=None):
    suffix = suffix or str(_next())
    return RepoCreate(
        name=f"Integration Repo {suffix}",
        slug=f"testorg/int-{suffix}",
        source=Source(system="github", external_id=f"testorg/int-{suffix}"),
    )


def make_issue_create(repo_id):
    return IssueCreate(
        repo=Ref(kind=ObjectKind.REPO, id=repo_id),
        title=f"Integration Issue {_next()}",
        description="Test issue for integration tests",
        type=IssueType.FEATURE,
        priority=Priority.P2,
    )


def make_context_packet_create(issue_id, version="1.0"):
    return ContextPacketCreate(
        for_issue=Ref(kind=ObjectKind.ISSUE, id=issue_id),
        version=version,
        summary=f"Context packet v{version}",
        assumptions=["Assumption A"],
        instructions="Follow test patterns",
    )


def make_constraint_snapshot_create():
    return ConstraintSnapshotCreate(
        scope=ConstraintScope.RUN,
        owner=Actor(actor_kind=ActorKind.SYSTEM, actor_id="test-system"),
        constraints=Constraints(),
    )


def make_doctrine_ref_create(suffix=None):
    suffix = suffix or str(_next())
    return DoctrineRefCreate(
        namespace="test/integration",
        name=f"doctrine-{suffix}",
        version="1.0",
        type=DoctrineType.POLICY,
        priority=DoctrinePriority.MUST,
        statement="Integration test doctrine",
        rationale="For testing",
    )


def make_run_create(issue_id, repo_id, inputs=None):
    return RunCreate(
        for_issue=Ref(kind=ObjectKind.ISSUE, id=issue_id),
        repo=Ref(kind=ObjectKind.REPO, id=repo_id),
        mode=RunMode.AGENT,
        executor=Executor(
            actor=Actor(actor_kind=ActorKind.SYSTEM, actor_id="worker-test"),
            runtime="local",
            toolchain=["python"],
        ),
        inputs=inputs or RunInputs(),
    )


def make_artifact_create(run_id, issue_id):
    return ArtifactCreate(
        produced_by=Ref(kind=ObjectKind.RUN, id=run_id),
        for_issue=Ref(kind=ObjectKind.ISSUE, id=issue_id),
        type=ArtifactType.CODE_PATCH,
        title=f"Artifact {_next()}",
        uri=f"file:///tmp/test-artifact-{_next()}.patch",
    )


def make_evidence_pack(db, run_id, issue_id, verdict="pass"):
    """Create an EvidencePack directly via ORM (no service create method)."""
    now = datetime.now(timezone.utc)
    ep = CWOMEvidencePackModel(
        id=generate_ulid(),
        kind="EvidencePack",
        for_run_id=run_id,
        for_run_kind="Run",
        for_run_role=None,
        for_issue_id=issue_id,
        for_issue_kind="Issue",
        for_issue_role=None,
        verdict=verdict,
        verdict_reason="All checks passed" if verdict == "pass" else "Failed",
        evaluated_at=now,
        evaluated_by_kind="system",
        evaluated_by_id="prover-test",
        evaluated_by_display=None,
        evidence_uri=None,
        criteria_results=[],
        evidence_collected=[],
        evidence_missing=[],
        checks_passed=3 if verdict == "pass" else 0,
        checks_failed=0 if verdict == "pass" else 1,
        checks_skipped=0,
        tags=[],
        meta={},
        created_at=now,
        updated_at=now,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


def make_review_data(ep_id, run_id, issue_id, decision="approved"):
    """Build the raw dict expected by ReviewDecisionService.create()."""
    return {
        "for_evidence_pack": {"kind": "EvidencePack", "id": ep_id},
        "for_run": {"kind": "Run", "id": run_id},
        "for_issue": {"kind": "Issue", "id": issue_id},
        "reviewer": {
            "actor_kind": "human",
            "actor_id": "reviewer-1",
            "display": "Test Reviewer",
        },
        "decision": decision,
        "decision_reason": f"Review decision: {decision}",
        "criteria_overrides": [],
        "tags": [],
        "meta": {},
    }


# =============================================================================
# Class 1: Repo Round-Trip
# =============================================================================


class TestRepoRoundTrip:
    def test_create_and_get_by_id(self, db_session):
        svc = RepoService(db_session)
        repo = svc.create(make_repo_create())

        fetched = svc.get(repo.id)
        assert fetched is not None
        assert fetched.id == repo.id
        assert fetched.name == repo.name
        assert fetched.slug == repo.slug
        assert fetched.default_branch == "main"

    def test_create_and_get_by_slug(self, db_session):
        svc = RepoService(db_session)
        slug = f"testorg/slug-test-{_next()}"
        repo = svc.create(RepoCreate(
            name="Slug Repo",
            slug=slug,
            source=Source(system="github", external_id=slug),
        ))

        fetched = svc.get_by_slug(slug)
        assert fetched is not None
        assert fetched.id == repo.id

    def test_list_repos(self, db_session):
        svc = RepoService(db_session)
        ids = [svc.create(make_repo_create()).id for _ in range(3)]

        repos = svc.list()
        repo_ids = [r.id for r in repos]
        for rid in ids:
            assert rid in repo_ids

    def test_to_dict_after_round_trip(self, db_session):
        svc = RepoService(db_session)
        repo = svc.create(make_repo_create())

        fetched = svc.get(repo.id)
        d = fetched.to_dict()
        assert d["kind"] == "Repo"
        assert d["id"] == repo.id
        assert d["name"] == repo.name
        assert d["slug"] == repo.slug
        assert d["created_at"] is not None
        assert d["updated_at"] is not None


# =============================================================================
# Class 2: Issue Round-Trip
# =============================================================================


class TestIssueRoundTrip:
    def _make_repo(self, db):
        return RepoService(db).create(make_repo_create())

    def test_create_and_get(self, db_session):
        repo = self._make_repo(db_session)
        svc = IssueService(db_session)
        issue = svc.create(make_issue_create(repo.id))

        fetched = svc.get(issue.id)
        assert fetched is not None
        assert fetched.title == issue.title
        assert fetched.type == "feature"
        assert fetched.status == "planned"
        assert fetched.priority == "P2"
        assert fetched.repo_id == repo.id

    def test_list_by_repo(self, db_session):
        repo = self._make_repo(db_session)
        svc = IssueService(db_session)
        svc.create(make_issue_create(repo.id))
        svc.create(make_issue_create(repo.id))

        issues = svc.list(repo_id=repo.id)
        assert len(issues) == 2

    def test_list_by_status(self, db_session):
        repo = self._make_repo(db_session)
        svc = IssueService(db_session)
        svc.create(make_issue_create(repo.id))

        issues = svc.list(status="planned")
        assert len(issues) >= 1

    def test_to_dict_includes_empty_relations(self, db_session):
        repo = self._make_repo(db_session)
        svc = IssueService(db_session)
        issue = svc.create(make_issue_create(repo.id))

        d = issue.to_dict()
        assert d["context_packets"] == []
        assert d["doctrine_refs"] == []
        assert d["constraints"] == []

    def test_repo_relationship_loaded(self, db_session):
        repo = self._make_repo(db_session)
        svc = IssueService(db_session)
        issue = svc.create(make_issue_create(repo.id))

        fetched = svc.get(issue.id)
        assert fetched.repo_obj is not None
        assert fetched.repo_obj.id == repo.id
        assert isinstance(fetched.repo_obj, CWOMRepoModel)


# =============================================================================
# Class 3: Relationship Loading
# =============================================================================


class TestRelationshipLoading:
    def _seed(self, db):
        """Create Repo + Issue, return (repo, issue)."""
        repo = RepoService(db).create(make_repo_create())
        issue = IssueService(db).create(make_issue_create(repo.id))
        return repo, issue

    def test_issue_context_packet_link_and_load(self, db_session):
        repo, issue = self._seed(db_session)
        packet = ContextPacketService(db_session).create(
            make_context_packet_create(issue.id)
        )
        result = IssueService(db_session).link_context_packet(issue.id, packet.id)
        assert result is True

        fetched = IssueService(db_session).get(issue.id)
        db_session.refresh(fetched)
        cp_ids = [cp.id for cp in fetched.context_packets]
        assert packet.id in cp_ids

    def test_issue_doctrine_ref_link_and_load(self, db_session):
        repo, issue = self._seed(db_session)
        doctrine = DoctrineRefService(db_session).create(make_doctrine_ref_create())
        result = IssueService(db_session).link_doctrine_ref(issue.id, doctrine.id)
        assert result is True

        fetched = IssueService(db_session).get(issue.id)
        db_session.refresh(fetched)
        dr_ids = [d.id for d in fetched.doctrine_refs_rel]
        assert doctrine.id in dr_ids

    def test_issue_constraint_snapshot_link_and_load(self, db_session):
        repo, issue = self._seed(db_session)
        snapshot = ConstraintSnapshotService(db_session).create(
            make_constraint_snapshot_create()
        )
        result = IssueService(db_session).link_constraint_snapshot(
            issue.id, snapshot.id
        )
        assert result is True

        fetched = IssueService(db_session).get(issue.id)
        db_session.refresh(fetched)
        cs_ids = [cs.id for cs in fetched.constraint_snapshots]
        assert snapshot.id in cs_ids

    def test_issue_multiple_context_packets(self, db_session):
        repo, issue = self._seed(db_session)
        cp_svc = ContextPacketService(db_session)
        issue_svc = IssueService(db_session)

        packets = []
        for i in range(3):
            p = cp_svc.create(make_context_packet_create(issue.id, version=f"{i}.0"))
            issue_svc.link_context_packet(issue.id, p.id)
            packets.append(p)

        fetched = issue_svc.get(issue.id)
        db_session.refresh(fetched)
        cp_ids = {cp.id for cp in fetched.context_packets}
        for p in packets:
            assert p.id in cp_ids

    def test_context_packet_backref_to_issues(self, db_session):
        repo, issue = self._seed(db_session)
        packet = ContextPacketService(db_session).create(
            make_context_packet_create(issue.id)
        )
        IssueService(db_session).link_context_packet(issue.id, packet.id)

        fetched_packet = ContextPacketService(db_session).get(packet.id)
        db_session.refresh(fetched_packet)
        issue_ids = [i.id for i in fetched_packet.issues]
        assert issue.id in issue_ids

    def test_doctrine_ref_backref_to_issues(self, db_session):
        repo, issue = self._seed(db_session)
        doctrine = DoctrineRefService(db_session).create(make_doctrine_ref_create())
        IssueService(db_session).link_doctrine_ref(issue.id, doctrine.id)

        fetched_doc = DoctrineRefService(db_session).get(doctrine.id)
        db_session.refresh(fetched_doc)
        issue_ids = [i.id for i in fetched_doc.issues]
        assert issue.id in issue_ids

    def test_run_context_packet_auto_link(self, db_session):
        repo, issue = self._seed(db_session)
        packet = ContextPacketService(db_session).create(
            make_context_packet_create(issue.id)
        )
        run = RunService(db_session).create(
            make_run_create(
                issue.id,
                repo.id,
                inputs=RunInputs(
                    context_packets=[Ref(kind=ObjectKind.CONTEXT_PACKET, id=packet.id)]
                ),
            )
        )

        fetched = RunService(db_session).get(run.id)
        db_session.refresh(fetched)
        cp_ids = [cp.id for cp in fetched.context_packets]
        assert packet.id in cp_ids

    def test_run_doctrine_ref_auto_link(self, db_session):
        repo, issue = self._seed(db_session)
        doctrine = DoctrineRefService(db_session).create(make_doctrine_ref_create())
        run = RunService(db_session).create(
            make_run_create(
                issue.id,
                repo.id,
                inputs=RunInputs(
                    doctrine_refs=[Ref(kind=ObjectKind.DOCTRINE_REF, id=doctrine.id)]
                ),
            )
        )

        fetched = RunService(db_session).get(run.id)
        db_session.refresh(fetched)
        dr_ids = [d.id for d in fetched.doctrine_refs_rel]
        assert doctrine.id in dr_ids

    def test_run_issue_relationship(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))

        fetched = RunService(db_session).get(run.id)
        assert fetched.issue_obj is not None
        assert fetched.issue_obj.id == issue.id

    def test_run_artifacts_relationship(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))
        art_svc = ArtifactService(db_session)
        a1 = art_svc.create(make_artifact_create(run.id, issue.id))
        a2 = art_svc.create(make_artifact_create(run.id, issue.id))

        fetched = RunService(db_session).get(run.id)
        db_session.refresh(fetched)
        art_ids = {a.id for a in fetched.artifacts}
        assert a1.id in art_ids
        assert a2.id in art_ids

    def test_context_packet_doctrine_ref_auto_link(self, db_session):
        repo, issue = self._seed(db_session)
        doctrine = DoctrineRefService(db_session).create(make_doctrine_ref_create())
        packet = ContextPacketService(db_session).create(
            ContextPacketCreate(
                for_issue=Ref(kind=ObjectKind.ISSUE, id=issue.id),
                version="1.0",
                summary="Packet with doctrine",
                doctrine_refs=[Ref(kind=ObjectKind.DOCTRINE_REF, id=doctrine.id)],
            )
        )

        fetched = ContextPacketService(db_session).get(packet.id)
        db_session.refresh(fetched)
        dr_ids = [d.id for d in fetched.doctrine_refs_rel]
        assert doctrine.id in dr_ids

    def test_repo_issues_backref(self, db_session):
        repo = RepoService(db_session).create(make_repo_create())
        issue_svc = IssueService(db_session)
        i1 = issue_svc.create(make_issue_create(repo.id))
        i2 = issue_svc.create(make_issue_create(repo.id))

        fetched_repo = RepoService(db_session).get(repo.id)
        db_session.refresh(fetched_repo)
        issue_ids = {i.id for i in fetched_repo.issues}
        assert i1.id in issue_ids
        assert i2.id in issue_ids


# =============================================================================
# Class 4: Join Table Queries
# =============================================================================


class TestJoinTableQueries:
    def _seed(self, db):
        repo = RepoService(db).create(make_repo_create())
        issue = IssueService(db).create(make_issue_create(repo.id))
        return repo, issue

    def test_find_issues_by_doctrine_ref(self, db_session):
        repo, issue1 = self._seed(db_session)
        issue2 = IssueService(db_session).create(make_issue_create(repo.id))
        doctrine = DoctrineRefService(db_session).create(make_doctrine_ref_create())

        # Link only to issue1
        IssueService(db_session).link_doctrine_ref(issue1.id, doctrine.id)

        fetched_doc = DoctrineRefService(db_session).get(doctrine.id)
        db_session.refresh(fetched_doc)
        linked_ids = {i.id for i in fetched_doc.issues}
        assert issue1.id in linked_ids
        assert issue2.id not in linked_ids

    def test_find_issues_by_constraint_snapshot(self, db_session):
        repo, issue1 = self._seed(db_session)
        issue2 = IssueService(db_session).create(make_issue_create(repo.id))
        snapshot = ConstraintSnapshotService(db_session).create(
            make_constraint_snapshot_create()
        )

        IssueService(db_session).link_constraint_snapshot(issue1.id, snapshot.id)

        fetched = ConstraintSnapshotService(db_session).get(snapshot.id)
        db_session.refresh(fetched)
        linked_ids = {i.id for i in fetched.issues}
        assert issue1.id in linked_ids
        assert issue2.id not in linked_ids

    def test_find_runs_by_context_packet(self, db_session):
        repo, issue = self._seed(db_session)
        packet = ContextPacketService(db_session).create(
            make_context_packet_create(issue.id)
        )
        run = RunService(db_session).create(
            make_run_create(
                issue.id,
                repo.id,
                inputs=RunInputs(
                    context_packets=[Ref(kind=ObjectKind.CONTEXT_PACKET, id=packet.id)]
                ),
            )
        )

        fetched_packet = ContextPacketService(db_session).get(packet.id)
        db_session.refresh(fetched_packet)
        run_ids = [r.id for r in fetched_packet.runs]
        assert run.id in run_ids

    def test_find_context_packets_by_doctrine_ref(self, db_session):
        repo, issue = self._seed(db_session)
        doctrine = DoctrineRefService(db_session).create(make_doctrine_ref_create())
        packet = ContextPacketService(db_session).create(
            ContextPacketCreate(
                for_issue=Ref(kind=ObjectKind.ISSUE, id=issue.id),
                version="1.0",
                summary="Packet with doctrine",
                doctrine_refs=[Ref(kind=ObjectKind.DOCTRINE_REF, id=doctrine.id)],
            )
        )

        fetched_doc = DoctrineRefService(db_session).get(doctrine.id)
        db_session.refresh(fetched_doc)
        cp_ids = [cp.id for cp in fetched_doc.context_packets]
        assert packet.id in cp_ids

    def test_context_packets_for_issue_service(self, db_session):
        repo, issue = self._seed(db_session)
        cp_svc = ContextPacketService(db_session)
        p1 = cp_svc.create(make_context_packet_create(issue.id, version="1.0"))
        p2 = cp_svc.create(make_context_packet_create(issue.id, version="2.0"))

        result = cp_svc.list_for_issue(issue.id)
        ids = [r.id for r in result]
        assert p1.id in ids
        assert p2.id in ids

    def test_latest_context_packet_for_issue(self, db_session):
        repo, issue = self._seed(db_session)
        cp_svc = ContextPacketService(db_session)
        cp_svc.create(make_context_packet_create(issue.id, version="1.0"))
        # Small sleep so created_at differs
        time.sleep(0.01)
        p2 = cp_svc.create(make_context_packet_create(issue.id, version="2.0"))

        latest = cp_svc.get_latest_for_issue(issue.id)
        assert latest is not None
        assert latest.id == p2.id
        assert latest.version == "2.0"

    def test_artifacts_for_run_service(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))
        art_svc = ArtifactService(db_session)
        a1 = art_svc.create(make_artifact_create(run.id, issue.id))
        a2 = art_svc.create(make_artifact_create(run.id, issue.id))

        result = art_svc.list_for_run(run.id)
        ids = {a.id for a in result}
        assert a1.id in ids
        assert a2.id in ids


# =============================================================================
# Class 5: Full Causality Chain
# =============================================================================


class TestFullCausalityChain:
    def _build_full_chain(self, db):
        """Build: Repo -> Issue -> CP + CS + DR -> Run -> Artifact -> EP -> Review."""
        repo = RepoService(db).create(make_repo_create())
        issue = IssueService(db).create(make_issue_create(repo.id))

        doctrine = DoctrineRefService(db).create(make_doctrine_ref_create())
        snapshot = ConstraintSnapshotService(db).create(
            make_constraint_snapshot_create()
        )
        packet = ContextPacketService(db).create(
            make_context_packet_create(issue.id)
        )

        # Link to issue
        IssueService(db).link_context_packet(issue.id, packet.id)
        IssueService(db).link_doctrine_ref(issue.id, doctrine.id)
        IssueService(db).link_constraint_snapshot(issue.id, snapshot.id)

        # Create run with auto-linked context packet
        run = RunService(db).create(
            make_run_create(
                issue.id,
                repo.id,
                inputs=RunInputs(
                    context_packets=[Ref(kind=ObjectKind.CONTEXT_PACKET, id=packet.id)],
                    doctrine_refs=[Ref(kind=ObjectKind.DOCTRINE_REF, id=doctrine.id)],
                ),
            )
        )

        # Progress run to done
        RunService(db).update(run.id, RunUpdate(status=Status.RUNNING))
        RunService(db).update(run.id, RunUpdate(status=Status.DONE))

        artifact = ArtifactService(db).create(make_artifact_create(run.id, issue.id))

        # Set issue to under_review for review flow
        IssueService(db).update_status(issue.id, "under_review")

        ep = make_evidence_pack(db, run.id, issue.id, verdict="pass")

        review = ReviewDecisionService(db).create(
            make_review_data(ep.id, run.id, issue.id, decision="approved")
        )

        return {
            "repo": repo,
            "issue": issue,
            "packet": packet,
            "snapshot": snapshot,
            "doctrine": doctrine,
            "run": run,
            "artifact": artifact,
            "evidence_pack": ep,
            "review": review,
        }

    def test_create_full_chain(self, db_session):
        chain = self._build_full_chain(db_session)
        for key, obj in chain.items():
            assert obj is not None, f"{key} should not be None"
            assert obj.id is not None, f"{key}.id should not be None"

    def test_traverse_chain_forward(self, db_session):
        chain = self._build_full_chain(db_session)

        # Repo -> Issues
        repo = RepoService(db_session).get(chain["repo"].id)
        db_session.refresh(repo)
        assert len(repo.issues) >= 1
        issue = repo.issues[0]

        # Issue -> Runs
        db_session.refresh(issue)
        assert len(issue.runs_rel) >= 1
        run = issue.runs_rel[0]

        # Run -> Artifacts
        db_session.refresh(run)
        assert len(run.artifacts) >= 1

    def test_traverse_chain_backward(self, db_session):
        chain = self._build_full_chain(db_session)

        # ReviewDecision -> EvidencePack
        review = ReviewDecisionService(db_session).get(chain["review"].id)
        assert review.for_evidence_pack_id == chain["evidence_pack"].id

        # EvidencePack -> Run
        ep = EvidencePackService(db_session).get(chain["evidence_pack"].id)
        assert ep.for_run_id == chain["run"].id

        # Run -> Issue
        run = RunService(db_session).get(chain["run"].id)
        assert run.for_issue_id == chain["issue"].id

        # Issue -> Repo
        issue = IssueService(db_session).get(chain["issue"].id)
        assert issue.repo_id == chain["repo"].id

    def test_to_dict_causality_refs(self, db_session):
        chain = self._build_full_chain(db_session)

        # Issue to_dict has repo ref
        issue_d = IssueService(db_session).get(chain["issue"].id).to_dict()
        assert issue_d["repo"]["id"] == chain["repo"].id

        # Run to_dict has issue ref
        run_d = RunService(db_session).get(chain["run"].id).to_dict()
        assert run_d["for_issue"]["id"] == chain["issue"].id
        assert run_d["repo"]["id"] == chain["repo"].id

        # Artifact to_dict has run + issue refs
        artifact_d = ArtifactService(db_session).get(chain["artifact"].id).to_dict()
        assert artifact_d["produced_by"]["id"] == chain["run"].id
        assert artifact_d["for_issue"]["id"] == chain["issue"].id

        # EvidencePack to_dict has run + issue refs
        ep_d = EvidencePackService(db_session).get(chain["evidence_pack"].id).to_dict()
        assert ep_d["for_run"]["id"] == chain["run"].id
        assert ep_d["for_issue"]["id"] == chain["issue"].id

        # Review to_dict has ep + run + issue refs
        review_d = ReviewDecisionService(db_session).get(chain["review"].id).to_dict()
        assert review_d["for_evidence_pack"]["id"] == chain["evidence_pack"].id
        assert review_d["for_run"]["id"] == chain["run"].id
        assert review_d["for_issue"]["id"] == chain["issue"].id

    def test_chain_with_multiple_runs(self, db_session):
        repo = RepoService(db_session).create(make_repo_create())
        issue = IssueService(db_session).create(make_issue_create(repo.id))

        run_svc = RunService(db_session)
        run1 = run_svc.create(make_run_create(issue.id, repo.id))
        run2 = run_svc.create(make_run_create(issue.id, repo.id))

        art_svc = ArtifactService(db_session)
        a1 = art_svc.create(make_artifact_create(run1.id, issue.id))
        a2 = art_svc.create(make_artifact_create(run2.id, issue.id))

        ep1 = make_evidence_pack(db_session, run1.id, issue.id)
        ep2 = make_evidence_pack(db_session, run2.id, issue.id)

        # Issue should have 2 runs
        fetched = IssueService(db_session).get(issue.id)
        db_session.refresh(fetched)
        assert len(fetched.runs_rel) == 2

        # Each run should have its own artifact
        r1 = run_svc.get(run1.id)
        db_session.refresh(r1)
        assert len(r1.artifacts) == 1
        assert r1.artifacts[0].id == a1.id

        r2 = run_svc.get(run2.id)
        db_session.refresh(r2)
        assert len(r2.artifacts) == 1
        assert r2.artifacts[0].id == a2.id

        # Evidence packs via service
        ep_svc = EvidencePackService(db_session)
        eps = ep_svc.list(issue_id=issue.id)
        ep_ids = {e.id for e in eps}
        assert ep1.id in ep_ids
        assert ep2.id in ep_ids


# =============================================================================
# Class 6: Immutability
# =============================================================================


class TestImmutability:
    def test_context_packet_service_has_no_update(self, db_session):
        svc = ContextPacketService(db_session)
        assert not hasattr(svc, "update"), "ContextPacketService should not have update()"
        assert not hasattr(svc, "update_status"), "ContextPacketService should not have update_status()"

    def test_constraint_snapshot_service_has_no_update(self, db_session):
        svc = ConstraintSnapshotService(db_session)
        assert not hasattr(svc, "update"), "ConstraintSnapshotService should not have update()"
        assert not hasattr(svc, "update_status"), "ConstraintSnapshotService should not have update_status()"

    def test_context_packet_versioning(self, db_session):
        repo = RepoService(db_session).create(make_repo_create())
        issue = IssueService(db_session).create(make_issue_create(repo.id))
        cp_svc = ContextPacketService(db_session)

        cp_svc.create(make_context_packet_create(issue.id, version="1.0"))
        time.sleep(0.01)
        p2 = cp_svc.create(make_context_packet_create(issue.id, version="2.0"))

        latest = cp_svc.get_latest_for_issue(issue.id)
        assert latest.id == p2.id
        assert latest.version == "2.0"

        all_packets = cp_svc.list_for_issue(issue.id)
        assert len(all_packets) == 2

    def test_data_unchanged_after_reread(self, db_session):
        repo = RepoService(db_session).create(make_repo_create())
        issue = IssueService(db_session).create(make_issue_create(repo.id))

        # ContextPacket
        cp_svc = ContextPacketService(db_session)
        cp = cp_svc.create(make_context_packet_create(issue.id))
        cp_dict_before = cp.to_dict()
        cp_reread = cp_svc.get(cp.id)
        cp_dict_after = cp_reread.to_dict()
        assert cp_dict_before["version"] == cp_dict_after["version"]
        assert cp_dict_before["summary"] == cp_dict_after["summary"]
        assert cp_dict_before["assumptions"] == cp_dict_after["assumptions"]

        # ConstraintSnapshot
        cs_svc = ConstraintSnapshotService(db_session)
        cs = cs_svc.create(make_constraint_snapshot_create())
        cs_dict_before = cs.to_dict()
        cs_reread = cs_svc.get(cs.id)
        cs_dict_after = cs_reread.to_dict()
        assert cs_dict_before["scope"] == cs_dict_after["scope"]
        assert cs_dict_before["owner"] == cs_dict_after["owner"]
        assert cs_dict_before["constraints"] == cs_dict_after["constraints"]


# =============================================================================
# Class 7: Status Transitions
# =============================================================================


class TestStatusTransitions:
    def _seed(self, db):
        repo = RepoService(db).create(make_repo_create())
        issue = IssueService(db).create(make_issue_create(repo.id))
        return repo, issue

    def test_issue_planned_to_running(self, db_session):
        repo, issue = self._seed(db_session)
        svc = IssueService(db_session)
        result = svc.update_status(issue.id, "running")
        assert result is not None
        assert result.status == "running"

        fetched = svc.get(issue.id)
        assert fetched.status == "running"

    def test_issue_running_to_done(self, db_session):
        repo, issue = self._seed(db_session)
        svc = IssueService(db_session)
        svc.update_status(issue.id, "running")
        result = svc.update_status(issue.id, "done")
        assert result.status == "done"

    def test_issue_to_under_review(self, db_session):
        repo, issue = self._seed(db_session)
        svc = IssueService(db_session)
        result = svc.update_status(issue.id, "under_review")
        assert result.status == "under_review"

    def test_run_planned_to_running_to_done(self, db_session):
        repo, issue = self._seed(db_session)
        run_svc = RunService(db_session)
        run = run_svc.create(make_run_create(issue.id, repo.id))
        assert run.status == "planned"

        run_svc.update(run.id, RunUpdate(status=Status.RUNNING))
        fetched = run_svc.get(run.id)
        assert fetched.status == "running"

        run_svc.update(run.id, RunUpdate(status=Status.DONE))
        fetched = run_svc.get(run.id)
        assert fetched.status == "done"

    def test_run_update_with_telemetry(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))

        now = datetime.now(timezone.utc)
        telemetry = Telemetry(
            started_at=now,
            ended_at=now,
            duration_s=42.5,
        )
        RunService(db_session).update(run.id, RunUpdate(telemetry=telemetry))

        fetched = RunService(db_session).get(run.id)
        assert fetched.telemetry is not None
        assert fetched.telemetry["duration_s"] == 42.5

    def test_review_approved_transitions_to_done(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))
        RunService(db_session).update(run.id, RunUpdate(status=Status.DONE))
        IssueService(db_session).update_status(issue.id, "under_review")

        ep = make_evidence_pack(db_session, run.id, issue.id, verdict="pass")
        ReviewDecisionService(db_session).create(
            make_review_data(ep.id, run.id, issue.id, decision="approved")
        )

        fetched_issue = IssueService(db_session).get(issue.id)
        fetched_run = RunService(db_session).get(run.id)
        assert fetched_issue.status == "done"
        assert fetched_run.status == "done"

    def test_review_rejected_transitions_to_failed(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))
        RunService(db_session).update(run.id, RunUpdate(status=Status.DONE))
        IssueService(db_session).update_status(issue.id, "under_review")

        ep = make_evidence_pack(db_session, run.id, issue.id, verdict="fail")
        ReviewDecisionService(db_session).create(
            make_review_data(ep.id, run.id, issue.id, decision="rejected")
        )

        fetched_issue = IssueService(db_session).get(issue.id)
        fetched_run = RunService(db_session).get(run.id)
        assert fetched_issue.status == "failed"
        assert fetched_run.status == "failed"


# =============================================================================
# Class 8: Audit Trail and Edge Cases
# =============================================================================


class TestAuditTrailAndEdgeCases:
    def _seed(self, db):
        repo = RepoService(db).create(make_repo_create())
        issue = IssueService(db).create(make_issue_create(repo.id))
        return repo, issue

    def test_repo_create_audit_log(self, db_session):
        repo = RepoService(db_session).create(
            make_repo_create(), actor_kind="human", actor_id="user-1"
        )
        audit = AuditService(db_session)
        entries = audit.query_by_entity("Repo", repo.id)
        assert len(entries) >= 1
        assert entries[0].action == "created"
        assert entries[0].actor_kind == "human"
        assert entries[0].actor_id == "user-1"

    def test_issue_status_change_audit_log(self, db_session):
        repo, issue = self._seed(db_session)
        IssueService(db_session).update_status(
            issue.id, "running", actor_kind="agent", actor_id="worker-1"
        )

        audit = AuditService(db_session)
        entries = audit.query_by_entity("Issue", issue.id)
        status_changes = [e for e in entries if e.action == "status_changed"]
        assert len(status_changes) >= 1
        latest = status_changes[-1]
        assert latest.actor_id == "worker-1"

    def test_link_audit_log(self, db_session):
        repo, issue = self._seed(db_session)
        doctrine = DoctrineRefService(db_session).create(make_doctrine_ref_create())
        IssueService(db_session).link_doctrine_ref(
            issue.id, doctrine.id, actor_kind="agent", actor_id="linker-1"
        )

        audit = AuditService(db_session)
        entries = audit.query_by_entity("Issue", issue.id)
        link_entries = [e for e in entries if e.action == "linked"]
        assert len(link_entries) >= 1

    def test_review_decision_creates_multiple_audit_entries(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))
        RunService(db_session).update(run.id, RunUpdate(status=Status.DONE))
        IssueService(db_session).update_status(issue.id, "under_review")

        ep = make_evidence_pack(db_session, run.id, issue.id)
        review = ReviewDecisionService(db_session).create(
            make_review_data(ep.id, run.id, issue.id, decision="approved")
        )

        audit = AuditService(db_session)

        # ReviewDecision should have a "created" entry
        rd_entries = audit.query_by_entity("ReviewDecision", review.id)
        assert any(e.action == "created" for e in rd_entries)

        # Issue should have a status_changed from the review
        issue_entries = audit.query_by_entity("Issue", issue.id)
        review_status_changes = [
            e
            for e in issue_entries
            if e.action == "status_changed" and "Review decision" in (e.note or "")
        ]
        assert len(review_status_changes) >= 1

    def test_duplicate_link_returns_false(self, db_session):
        repo, issue = self._seed(db_session)
        packet = ContextPacketService(db_session).create(
            make_context_packet_create(issue.id)
        )
        svc = IssueService(db_session)
        first = svc.link_context_packet(issue.id, packet.id)
        assert first is True

        second = svc.link_context_packet(issue.id, packet.id)
        assert second is False

    def test_get_nonexistent_repo_returns_none(self, db_session):
        svc = RepoService(db_session)
        assert svc.get("nonexistent-id") is None

    def test_get_nonexistent_issue_returns_none(self, db_session):
        svc = IssueService(db_session)
        assert svc.get("nonexistent-id") is None

    def test_update_status_nonexistent_issue(self, db_session):
        svc = IssueService(db_session)
        result = svc.update_status("nonexistent-id", "done")
        assert result is None

    def test_review_non_under_review_issue_raises(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))
        ep = make_evidence_pack(db_session, run.id, issue.id)

        # Issue is "planned", not "under_review"
        with pytest.raises(ValueError, match="not under review"):
            ReviewDecisionService(db_session).create(
                make_review_data(ep.id, run.id, issue.id)
            )

    def test_review_nonexistent_evidence_pack_raises(self, db_session):
        repo, issue = self._seed(db_session)
        run = RunService(db_session).create(make_run_create(issue.id, repo.id))

        with pytest.raises(ValueError, match="not found"):
            ReviewDecisionService(db_session).create(
                make_review_data("fake-ep-id", run.id, issue.id)
            )

    def test_doctrine_ref_unique_constraint(self, db_session):
        svc = DoctrineRefService(db_session)
        suffix = str(_next())
        create = DoctrineRefCreate(
            namespace="test/unique",
            name=f"unique-doctrine-{suffix}",
            version="1.0",
            type=DoctrineType.POLICY,
            priority=DoctrinePriority.MUST,
            statement="Test uniqueness",
        )
        svc.create(create)

        # Same namespace/name/version should fail
        with pytest.raises(Exception):
            svc.create(create)
