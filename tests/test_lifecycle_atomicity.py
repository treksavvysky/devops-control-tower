"""
Regression tests for the second PR #12 review (Codex, 2026-11-25, findings
C1–C6 and N1), on file-backed SQLite and PostgreSQL.

Each test inverts one of Codex's reproduction probes
(hub ``reports/evidence/dct-pr12-codex/test_codex_adversarial.py``): the probe
asserted the defect; these assert the safe behaviour, through the real
lifecycle, MCP, worker and review code.

Interleavings are made deterministic with hooks around the real functions.
Where the competing operation must wait for a lock held by the code under
test, it runs in a thread and the test checks that it could not take effect
before the protected transaction committed.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import devops_control_tower.worker.loop as loop_module
import devops_control_tower.worker.pipeline as pipeline_module
from devops_control_tower import lifecycle as lc
from devops_control_tower import mcp as mcp_module
from devops_control_tower.db.audit_service import AuditService
from devops_control_tower.db.cwom_models import (
    CWOMArtifactModel,
    CWOMEvidencePackModel,
    CWOMIssueModel,
    CWOMRunModel,
)
from devops_control_tower.db.models import ArtifactModel, JobModel, TaskModel
from devops_control_tower.lifecycle import LifecycleError
from devops_control_tower.worker.leases import process_expired_leases, resolve_held_task
from tests.test_lease_fencing import (  # noqa: F401  (fixtures)
    _as,
    _enqueue,
    _mcp_claim,
    _task,
    backend,
    clock,
)

LATER = timedelta(hours=1)


def _hold(b, tid):
    """Hold the task as a reaper whose clock is an hour ahead (stored leases
    untouched). Runs in its own session."""
    with b["SM"]() as s:
        process_expired_leases(s, now=datetime.now(timezone.utc) + LATER)


def _requeue(b, tid):
    with b["SM"]() as s:
        resolve_held_task(s, tid, "requeue", "operator", "scratch: no process", True)


def _complete(tid, gen, actor="exec-A@test", success=True, summary="ok"):
    return _as(
        actor,
        mcp_module.jct_complete_task,
        task_id=tid,
        success=success,
        summary=summary,
        claim_generation=gen,
    )


def _report(tid, gen, title="report", content="ok"):
    return _as(
        "exec-A@test",
        mcp_module.jct_report_artifact,
        task_id=tid,
        title=title,
        artifact_type="doc",
        content=content,
        claim_generation=gen,
    )


def _row(b, model, ident):
    with b["SM"]() as s:
        obj = s.get(model, ident)
        return SimpleNamespace(**obj.to_dict()) if obj is not None else None


class _Concurrent:
    """Run ``fn`` in a thread; it may block on a lock the caller holds."""

    def __init__(self, fn):
        self.error = None
        self.thread = threading.Thread(target=self._run, args=(fn,), daemon=True)
        self.thread.start()

    def _run(self, fn):
        try:
            fn()
        except Exception as exc:  # e.g. SQLite "database is locked"
            self.error = exc

    def join(self):
        self.thread.join(timeout=60)
        assert not self.thread.is_alive(), "concurrent operation never finished"


def _status_now(b, tid):
    with b["SM"]() as s:
        return s.query(TaskModel.status).filter(TaskModel.id == tid).scalar()


# ============================================================== C1 atomicity
def test_c1_finish_does_not_commit(backend):
    """Codex P: finish + rollback left the task completed. Now nothing persists."""
    tid = _enqueue(budget=300)
    c = _mcp_claim(tid)
    with backend["SM"]() as s:
        lc.finish(s, lc.ClaimToken(tid, "exec-A@test", c["claim_generation"]), True)
        s.rollback()  # caller fails before its run/issue writes
    assert _task(backend, tid).status == "running"
    assert _row(backend, CWOMRunModel, c["run_id"]).status == "running"


def test_c1_mcp_completion_is_all_or_nothing(backend, monkeypatch):
    """A failure after the task transition rolls back the task too; retry works."""
    tid = _enqueue(budget=300)
    c = _mcp_claim(tid)
    real = lc.attempt_runs
    monkeypatch.setattr(
        lc, "attempt_runs", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    out = _complete(tid, c["claim_generation"])
    assert out["success"] is False and out["error"]["code"] == "COMPLETE_TASK_ERROR"
    assert _task(backend, tid).status == "running"
    assert _row(backend, CWOMRunModel, c["run_id"]).status == "running"
    monkeypatch.setattr(lc, "attempt_runs", real)
    assert _complete(tid, c["claim_generation"])["success"]
    assert _task(backend, tid).status == "completed"
    assert _row(backend, CWOMRunModel, c["run_id"]).status in ("done", "under_review")


def test_c1_worker_accept_is_atomic(backend, monkeypatch):
    """A failure while recording the worker's run rolls back the task transition;
    the failure path then records a consistent failed task and run."""
    tid = _enqueue(budget=300)
    real = AuditService.log_status_change
    fired = {"n": 0}

    def fail_once(self, **kw):
        if kw.get("entity_kind") == "Run" and not fired["n"]:
            fired["n"] += 1
            raise RuntimeError("ledger write failed")
        return real(self, **kw)

    monkeypatch.setattr(AuditService, "log_status_change", fail_once)
    w = loop_module.WorkerLoop(executor_type="stub")
    with backend["SM"]() as s:
        task = w._claim_task(s)
        w._process_task(s, task)
    t = _task(backend, tid)
    with backend["SM"]() as s:
        runs = s.query(CWOMRunModel).filter(CWOMRunModel.task_id == tid).all()
        statuses = [r.status for r in runs]
    assert fired["n"] == 1
    assert t.status == "failed" and statuses == ["failed"]  # never completed/running


def test_c1_old_reaper_cannot_fail_new_claims_run(backend, monkeypatch):
    """Codex P: the reaper's requeue committed early (audit) and then failed the
    NEW claim's run. Now the requeue is invisible until its transaction commits,
    and runs are selected by (task, generation)."""
    tid = _enqueue(budget=300)
    old = _mcp_claim(tid)
    real = AuditService.log_status_change
    during = {}

    def interleave(self, **kw):
        result = real(self, **kw)
        if (
            not during
            and kw.get("entity_kind") == "Task"
            and kw.get("new_status") == "queued"
        ):
            during["claim"] = _mcp_claim(tid)  # another executor, mid-requeue
        return result

    monkeypatch.setattr(AuditService, "log_status_change", interleave)
    with backend["SM"]() as s:
        process_expired_leases(
            s,
            now=datetime.now(timezone.utc) + LATER,
            confirm_termination=lambda t: True,
        )
    monkeypatch.setattr(AuditService, "log_status_change", real)
    assert during["claim"]["success"] is False  # requeue not visible yet
    new = _mcp_claim(tid)
    assert new["success"] and new["claim_generation"] == old["claim_generation"] + 1
    assert _row(backend, CWOMRunModel, new["run_id"]).status == "running"
    assert _row(backend, CWOMRunModel, old["run_id"]).status == "failed"
    assert _task(backend, tid).status == "running"


def test_c1_attempt_runs_are_scoped_to_generation(backend):
    """Runs of an older generation on the same issue are never selected."""
    tid = _enqueue(budget=300)
    first = _mcp_claim(tid)
    _hold(backend, tid)
    _requeue(backend, tid)
    second = _mcp_claim(tid)
    with backend["SM"]() as s:
        g1 = lc.attempt_runs(s, tid, first["claim_generation"])
        g2 = lc.attempt_runs(s, tid, second["claim_generation"], ["running"])
    assert [r.id for r in g1] == [first["run_id"]]
    assert [r.id for r in g2] == [second["run_id"]]


def test_c1_proof_stage_is_recoverable(backend, monkeypatch):
    """If proof fails, the accepted result stays; the run is marked pending and
    recover_pending_proofs completes it idempotently."""
    tid = _enqueue(budget=300)
    c = _mcp_claim(tid)
    assert _report(tid, c["claim_generation"])["success"]
    real = pipeline_module.run_prove
    monkeypatch.setattr(
        pipeline_module,
        "run_prove",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("prover crashed")),
    )
    out = _complete(tid, c["claim_generation"])
    assert out["success"] and out["proof_status"] == "pending"
    assert _task(backend, tid).status == "completed"
    run = _row(backend, CWOMRunModel, c["run_id"])
    assert run.status == "done" and run.proof_status == "pending"
    monkeypatch.setattr(pipeline_module, "run_prove", real)
    with backend["SM"]() as s:
        assert pipeline_module.recover_pending_proofs(s) == [c["run_id"]]
        assert pipeline_module.recover_pending_proofs(s) == []
        packs = (
            s.query(CWOMEvidencePackModel)
            .filter(CWOMEvidencePackModel.for_run_id == c["run_id"])
            .count()
        )
    assert packs == 1
    assert _row(backend, CWOMRunModel, c["run_id"]).proof_status == "done"


# ============================================================== C2 token issuance
def test_c2_claim_returns_its_own_generation(backend):
    """Codex P: a paused claimant was handed the NEXT claim's generation. The
    generation now comes from the claiming UPDATE (RETURNING)."""
    tid = _enqueue(budget=300)
    s = backend["SM"]()
    try:
        old = lc.claim(
            s, tid, "same-actor", datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        s.commit()
        _hold(backend, tid)
        _requeue(backend, tid)
        with backend["SM"]() as other:
            new = lc.claim(
                other,
                tid,
                "same-actor",
                datetime.now(timezone.utc) + timedelta(hours=2),
            )
            other.commit()
        assert (old.generation, new.generation) == (1, 2)
        with pytest.raises(LifecycleError) as exc:
            lc.finish(s, old, True)
        assert exc.value.code == "CLAIM_LOST"
        s.rollback()
    finally:
        s.close()
    assert _task(backend, tid).status == "running"


def test_c2_claim_does_not_commit(backend):
    tid = _enqueue(budget=300)
    with backend["SM"]() as s:
        assert lc.claim(s, tid, "x", datetime.now(timezone.utc) + LATER) is not None
        s.rollback()
    assert _task(backend, tid).status == "queued"


# ============================================================== C3 token required
def test_c3_omitted_token_never_adopts_newest_claim(backend):
    """Codex P: a tokenless delayed call from attempt 1 completed attempt 2."""
    tid = _enqueue(budget=300)
    old = _mcp_claim(tid)
    _hold(backend, tid)
    _requeue(backend, tid)
    new = _mcp_claim(tid)  # same process, same actor
    for call in (
        lambda: _as(
            "exec-A@test",
            mcp_module.jct_complete_task,
            task_id=tid,
            success=True,
            summary="delayed",
        ),
        lambda: _as(
            "exec-A@test",
            mcp_module.jct_report_artifact,
            task_id=tid,
            title="delayed",
            artifact_type="doc",
            content="x",
        ),
    ):
        out = call()
        assert out["success"] is False
        assert out["error"]["code"] == "CLAIM_TOKEN_REQUIRED"
    stale = _complete(tid, old["claim_generation"])
    assert stale["success"] is False and stale["error"]["code"] == "CLAIM_LOST"
    assert _task(backend, tid).status == "running"
    assert _row(backend, CWOMRunModel, new["run_id"]).status == "running"


# ============================================================== C4 write fences
def test_c4_artifact_and_concurrent_hold_serialize(backend, monkeypatch):
    """Codex P: an artifact was accepted after a hold that landed between the
    check and the write. Now the fence write-locks the claim: the hold can't
    take effect until the artifact's transaction commits."""
    tid = _enqueue(budget=300)
    c = _mcp_claim(tid)
    real = lc.fence
    seen = {}

    def interleave(db, token, *a, **kw):
        real(db, token, *a, **kw)
        seen["hold"] = _Concurrent(lambda: _hold(backend, tid))
        time.sleep(0.5)  # give the hold every chance to jump the queue
        seen["status_during"] = _status_now(backend, tid)

    monkeypatch.setattr(lc, "fence", interleave)
    out = _report(tid, c["claim_generation"], title="raced", content="RACED")
    seen["hold"].join()
    monkeypatch.setattr(lc, "fence", real)
    assert out["success"], out
    assert seen["status_during"] == "running"  # the hold could not take effect
    _hold(backend, tid)  # on SQLite the blocked reaper may have given up: retry
    assert _task(backend, tid).status == "held"
    with backend["SM"]() as s:
        art = s.get(CWOMArtifactModel, out["artifact_id"])
        assert art is not None and art.produced_by_id == c["run_id"]


def test_c4_artifact_after_hold_refused(backend):
    tid = _enqueue(budget=300)
    c = _mcp_claim(tid)
    _hold(backend, tid)
    out = _report(tid, c["claim_generation"], title="late", content="LATE")
    assert out["success"] is False and out["error"]["code"] == "TASK_NOT_RUNNING"
    with backend["SM"]() as s:
        n = (
            s.query(CWOMArtifactModel)
            .filter(CWOMArtifactModel.produced_by_id == c["run_id"])
            .count()
        )
    assert n == 0


def test_c4_mcp_claim_and_run_registration_are_atomic(backend, monkeypatch):
    """Codex P: a hold right after the claim produced held task + running run +
    running issue. Now the claim, run and issue commit together, and a
    concurrent hold applies to the registered attempt (run and issue blocked)."""
    tid = _enqueue(budget=300)
    real = lc.claim
    seen = {}

    def interleave(db, *a, **kw):
        token = real(db, *a, **kw)
        seen["hold"] = _Concurrent(lambda: _hold(backend, tid))
        time.sleep(0.5)
        seen["status_during"] = _status_now(backend, tid)
        return token

    monkeypatch.setattr(lc, "claim", interleave)
    out = _mcp_claim(tid)
    seen["hold"].join()
    monkeypatch.setattr(lc, "claim", real)
    assert out["success"], out
    assert seen["status_during"] == "queued"  # claim not visible, hold impossible
    _hold(backend, tid)
    run = _row(backend, CWOMRunModel, out["run_id"])
    issue = _row(backend, CWOMIssueModel, run.for_issue["id"])
    assert (_task(backend, tid).status, run.status, issue.status) == (
        "held",
        "blocked",
        "blocked",
    )


def test_c4_worker_never_launches_after_hold(backend, monkeypatch):
    """A hold before the launch fence: no run is created and nothing executes."""
    tid = _enqueue(budget=300)
    w = loop_module.WorkerLoop(executor_type="stub")
    executed = []
    real_execute = w.executor.execute
    monkeypatch.setattr(
        w.executor,
        "execute",
        lambda *a, **k: executed.append(1) or real_execute(*a, **k),
    )
    with backend["SM"]() as s:
        task = w._claim_task(s)
        _hold(backend, tid)
        w._process_task(s, task)
    assert executed == []
    with backend["SM"]() as s:
        assert s.query(CWOMRunModel).filter(CWOMRunModel.task_id == tid).count() == 0
    assert _task(backend, tid).status == "held"


def test_c4_worker_launch_and_concurrent_hold_serialize(backend, monkeypatch):
    """Codex P: the worker created its run after a hold. Now the launch (fence +
    run registration) commits as one transaction; a concurrent hold waits for it
    and then holds the registered attempt. Its result is discarded and no
    evidence is produced. (Stopping an attempt that is already launched is the
    substrate's job: contract stage 5.)"""
    tid = _enqueue(budget=300)
    w = loop_module.WorkerLoop(executor_type="stub")
    real = loop_module.lifecycle_fence
    seen = {}

    def interleave(db, token, *a, **kw):
        real(db, token, *a, **kw)
        if "hold" not in seen:
            seen["hold"] = _Concurrent(lambda: _hold(backend, tid))
            time.sleep(0.5)
            seen["status_during"] = _status_now(backend, tid)

    monkeypatch.setattr(loop_module, "lifecycle_fence", interleave)

    def execute_after_hold(context, store):  # make sure the hold has landed
        seen["hold"].join()
        _hold(backend, tid)
        return real_execute(context, store)

    real_execute = w.executor.execute
    monkeypatch.setattr(w.executor, "execute", execute_after_hold)
    with backend["SM"]() as s:
        task = w._claim_task(s)
        w._process_task(s, task)
    assert seen["status_during"] == "running"  # the hold waited for the launch
    assert _task(backend, tid).status == "held"
    with backend["SM"]() as s:
        runs = s.query(CWOMRunModel).filter(CWOMRunModel.task_id == tid).all()
        assert [r.status for r in runs] == ["blocked"]
        assert (
            s.query(CWOMEvidencePackModel)
            .filter(CWOMEvidencePackModel.for_run_id == runs[0].id)
            .count()
            == 0
        )


# ============================================================== C5 legacy worker
@pytest.mark.parametrize("outcome", ["returns", "raises"])
def test_c5_legacy_worker_accepts_nothing_after_hold(backend, outcome):
    """Codex P: the legacy worker committed a stale output artifact and then an
    error artifact after the hold. Now nothing is accepted for the task; only
    the worker's own job records that its result was discarded."""
    from devops_control_tower.worker.worker import Worker

    tid = _enqueue(budget=300)

    class Runner:
        def __init__(self, **kw):
            pass

        def execute(self, **kw):
            _hold(backend, tid)
            if outcome == "raises":
                raise RuntimeError("runner crashed after the hold")
            return SimpleNamespace(
                success=True,
                result={},
                error=None,
                artifacts=[{"kind": "log", "content": "STALE"}],
            )

    w = Worker(worker_id="legacy")
    w.action_runner_class = Runner
    with backend["SM"]() as s:
        out = w.process_task(s, s.get(TaskModel, tid))
    assert out["status"] == "discarded"
    with backend["SM"]() as s:
        assert s.query(ArtifactModel).filter(ArtifactModel.task_id == tid).count() == 0
        job = s.query(JobModel).filter(JobModel.task_id == tid).one()
        assert job.status == "failed" and "discarded" in job.error
    assert _task(backend, tid).status == "held"


def test_c5_legacy_worker_result_is_atomic(backend):
    """A live legacy claim: artifacts, task and job commit together."""
    from devops_control_tower.worker.worker import Worker

    tid = _enqueue(budget=300)

    class Runner:
        def __init__(self, **kw):
            pass

        def execute(self, **kw):
            return SimpleNamespace(
                success=True,
                result={"ok": True},
                error=None,
                artifacts=[{"kind": "log", "content": "fine"}],
            )

    w = Worker(worker_id="legacy")
    w.action_runner_class = Runner
    with backend["SM"]() as s:
        out = w.process_task(s, s.get(TaskModel, tid))
    assert out["status"] == "completed"
    with backend["SM"]() as s:
        assert s.query(ArtifactModel).filter(ArtifactModel.task_id == tid).count() == 1
        assert s.query(JobModel).filter(JobModel.task_id == tid).one().status == (
            "completed"
        )
    assert _task(backend, tid).status == "completed"


# ============================================================== C6 review relations
def _manual_review(monkeypatch, metadata=None):
    from devops_control_tower import config as cfg_mod

    monkeypatch.setattr(cfg_mod.settings, "jct_review_auto_approve", False)
    tid = _enqueue(budget=300, metadata=metadata)
    c = _mcp_claim(tid)
    assert _report(tid, c["claim_generation"])["success"]
    done = _complete(tid, c["claim_generation"])
    assert done["success"], done
    return tid, c["run_id"], done["evidence_pack"]["id"]


def _review_body(ep_id, run_id, issue_id):
    return {
        "for_evidence_pack": {"id": ep_id},
        "for_run": {"id": run_id},
        "for_issue": {"id": issue_id},
        "reviewer": {"actor_kind": "human", "actor_id": "independent-reviewer"},
        "decision": "approved",
        "decision_reason": "cross-issue probe",
    }


def test_c6_experimental_evidence_cannot_approve_other_issue(backend, monkeypatch):
    """Codex P: experimental evidence + its own run + a production issue marked
    the production issue done. Now any cross-issue review is refused."""
    from devops_control_tower.cwom.services import ReviewDecisionService

    _, exp_run, exp_ep = _manual_review(
        monkeypatch, metadata={"experiment": {"id": "EXP-TEST"}}
    )
    prod_tid, _, _ = _manual_review(monkeypatch)
    with backend["SM"]() as s:
        prod_issue = s.get(TaskModel, prod_tid).cwom_issue_id
        assert s.get(CWOMIssueModel, prod_issue).status == "under_review"
        with pytest.raises(ValueError, match="not '"):
            ReviewDecisionService(s).create(_review_body(exp_ep, exp_run, prod_issue))
        s.rollback()
    with backend["SM"]() as s:
        assert s.get(CWOMIssueModel, prod_issue).status == "under_review"


def test_c6_rest_review_refuses_cross_issue(backend, monkeypatch):
    from fastapi.testclient import TestClient

    from devops_control_tower.api import app
    from devops_control_tower.db.base import get_db

    _, exp_run, exp_ep = _manual_review(
        monkeypatch, metadata={"experiment": {"id": "EXP-TEST"}}
    )
    prod_tid, _, _ = _manual_review(monkeypatch)
    with backend["SM"]() as s:
        prod_issue = s.get(TaskModel, prod_tid).cwom_issue_id

    def _db():
        session = backend["SM"]()
        try:
            yield session
        finally:
            session.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _db
    try:
        with TestClient(app) as c:
            r = c.post(
                "/cwom/reviews",
                json={
                    **_review_body(exp_ep, exp_run, prod_issue),
                    "for_evidence_pack": {"kind": "EvidencePack", "id": exp_ep},
                    "for_run": {"kind": "Run", "id": exp_run},
                    "for_issue": {"kind": "Issue", "id": prod_issue},
                },
            )
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
    assert r.status_code == 400, r.text
    with backend["SM"]() as s:
        assert s.get(CWOMIssueModel, prod_issue).status == "under_review"


def test_c6_matching_review_still_works(backend, monkeypatch):
    from devops_control_tower.cwom.services import ReviewDecisionService

    tid, run_id, ep_id = _manual_review(monkeypatch)
    with backend["SM"]() as s:
        issue_id = s.get(TaskModel, tid).cwom_issue_id
        ReviewDecisionService(s).create(_review_body(ep_id, run_id, issue_id))
    with backend["SM"]() as s:
        assert s.get(CWOMIssueModel, issue_id).status == "done"


# ============================================================== N1 confirmation
@pytest.mark.parametrize("answer", [1, "yes", [True], object()])
def test_n1_only_literal_true_confirms_termination(backend, answer):
    tid = _enqueue(budget=300)
    _mcp_claim(tid)
    with backend["SM"]() as s:
        out = process_expired_leases(
            s,
            now=datetime.now(timezone.utc) + LATER,
            confirm_termination=lambda t: answer,
        )
    assert out["held"] == [tid] and out["requeued"] == []


def test_n1_requeue_primitives_require_literal_true(backend):
    tid = _enqueue(budget=300)
    _mcp_claim(tid)
    with backend["SM"]() as s:
        task = s.get(TaskModel, tid)
        with pytest.raises(LifecycleError) as exc:
            lc.requeue_after_confirmed_termination(
                s, task, "true", datetime.now(timezone.utc) + LATER
            )
        assert exc.value.code == "TERMINATION_NOT_CONFIRMED"
    _hold(backend, tid)
    with backend["SM"]() as s:
        task = s.get(TaskModel, tid)
        with pytest.raises(LifecycleError):
            lc.resolve_held(s, task, "requeue", termination_confirmed=1)
    assert _task(backend, tid).status == "held"
