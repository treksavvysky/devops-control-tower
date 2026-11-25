"""
Real-path regression tests for lease expiry, held tasks and fencing
(DEVOPS-CON-10, DEVOPS-CON-11; George's decisions of 2026-11-25).

Unlike the unit tests in test_mcp_server.py, these use the production claim
paths unchanged: MCP ``jct_claim_task`` (raw-SQL UPDATE) and
``WorkerLoop._claim_task``, each with real per-call sessions against a
file-backed SQLite database and, when ``DCT_TEST_POSTGRES_URL`` is set,
PostgreSQL. Lease expiry is simulated by advancing the *reaper's clock*, never
by rewriting stored lease values, because rewriting them is what hid
DEVOPS-CON-10.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import devops_control_tower.mcp as mcp_module
import devops_control_tower.worker.leases as leases_module
import devops_control_tower.worker.loop as loop_module
from devops_control_tower import config as cfg_mod
from devops_control_tower.db import audit_models, cwom_models, models  # noqa: F401
from devops_control_tower.db.audit_models import AuditLogModel
from devops_control_tower.db.base import Base
from devops_control_tower.db.cwom_models import (
    CWOMArtifactModel,
    CWOMEvidencePackModel,
    CWOMRunModel,
)
from devops_control_tower.db.models import TaskModel
from devops_control_tower.worker.leases import (
    HeldTaskError,
    process_expired_leases,
    resolve_held_task,
)

BACKENDS = ["sqlite"] + (
    ["postgres"] if os.environ.get("DCT_TEST_POSTGRES_URL") else []
)


@pytest.fixture(params=BACKENDS)
def backend(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path}/dct.db",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
    else:
        engine = create_engine(os.environ["DCT_TEST_POSTGRES_URL"], pool_size=20)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    state = {"engine": engine, "SM": sessionmaker(bind=engine, autoflush=False)}

    def _get_db():
        return state["SM"]()

    monkeypatch.setattr(mcp_module, "_get_db", _get_db)
    monkeypatch.setattr(loop_module, "SessionLocal", lambda: state["SM"]())
    s = cfg_mod.settings
    monkeypatch.setattr(s, "jct_actor_id", "exec-A@test")
    monkeypatch.setattr(s, "jct_trace_root", f"file://{tmp_path}/traces")
    monkeypatch.setattr(s, "jct_lease_grace_seconds", 0)
    monkeypatch.setattr(s, "jct_allowed_repo_prefixes", "testorg/")
    monkeypatch.setattr(s, "jct_authorized_experiments", "EXP-TEST")
    monkeypatch.setattr(s, "jct_review_auto_approve", True)
    monkeypatch.setattr(s, "jct_review_auto_approve_verdicts", "pass")
    mcp_module._active_claims.clear()
    state["name"] = request.param

    def restart():
        """Simulate a process restart: drop in-memory claims and the connection pool."""
        mcp_module._active_claims.clear()
        state["engine"].dispose()
        url = state["engine"].url
        kw = (
            {"connect_args": {"check_same_thread": False, "timeout": 30}}
            if state["name"] == "sqlite"
            else {"pool_size": 20}
        )
        state["engine"] = create_engine(url, **kw)
        state["SM"] = sessionmaker(bind=state["engine"], autoflush=False)

    state["restart"] = restart
    yield state
    mcp_module._active_claims.clear()
    Base.metadata.drop_all(bind=state["engine"])
    state["engine"].dispose()


@pytest.fixture
def clock(monkeypatch):
    """Advance the reaper's clock without touching stored lease values."""
    offset = {"s": 0}
    real = datetime

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return real.now(tz) + timedelta(seconds=offset["s"])

    monkeypatch.setattr(leases_module, "datetime", _Clock)

    def advance(seconds):
        offset["s"] += seconds

    return advance


def _enqueue(budget=30, metadata=None, objective="lease test"):
    kw = {"metadata": metadata} if metadata is not None else {}
    r = json.loads(
        mcp_module.jct_enqueue_task(
            objective=objective,
            operation="analysis",
            target_repo="testorg/repo",
            time_budget_seconds=budget,
            acceptance_criteria=["report exists"],
            **kw,
        )
    )
    assert r["success"], r
    return r["task_id"]


def _as(actor, fn, *a, **kw):
    old = cfg_mod.settings.jct_actor_id
    cfg_mod.settings.jct_actor_id = actor
    try:
        return json.loads(fn(*a, **kw))
    finally:
        cfg_mod.settings.jct_actor_id = old


def _mcp_claim(task_id, actor="exec-A@test"):
    return _as(actor, mcp_module.jct_claim_task, task_id)


def _worker_claim(state):
    db = state["SM"]()
    try:
        t = loop_module.WorkerLoop(executor_type="stub")._claim_task(db)
        return (str(t.id), t.assigned_to) if t else None
    finally:
        db.close()


def _task(state, task_id):
    db = state["SM"]()
    try:
        return db.query(TaskModel).filter(TaskModel.id == task_id).one()
    finally:
        db.close()


# --------------------------------------------------------------- DEVOPS-CON-10
@pytest.mark.parametrize("path", ["mcp", "worker"])
def test_claim_paths_store_orm_comparable_lease(backend, path):
    """Regression: the raw-SQL claim write must be comparable through the ORM."""
    task_id = _enqueue()
    if path == "mcp":
        assert _mcp_claim(task_id)["success"]
    else:
        assert _worker_claim(backend)[0] == task_id
    db = backend["SM"]()
    try:
        t = db.query(TaskModel).filter(TaskModel.id == task_id).one()
        assert t.lease_expires_at is not None
        same = (
            db.query(TaskModel)
            .filter(
                TaskModel.id == task_id,
                TaskModel.lease_expires_at == t.lease_expires_at,
            )
            .count()
        )
        assert same == 1, "stored lease must equal its own ORM-bound value"
    finally:
        db.close()


@pytest.mark.parametrize("path", ["mcp", "worker"])
def test_expired_lease_is_held_through_real_paths(backend, clock, path):
    task_id = _enqueue(budget=30)
    if path == "mcp":
        claim = _mcp_claim(task_id)
        assert claim["success"]
    else:
        assert _worker_claim(backend)[0] == task_id
    clock(31)
    if path == "mcp":
        listed = json.loads(mcp_module.jct_list_tasks())  # tool path runs the reaper
        assert task_id not in [t["task_id"] for t in listed["tasks"]]
    else:
        worker = loop_module.WorkerLoop(executor_type="stub")
        assert worker._poll_and_process() == 0  # reaper runs; nothing queued to claim
    t = _task(backend, task_id)
    assert t.status == "held"
    assert t.held_at is not None and "not confirmed" in t.held_reason
    if path == "mcp":
        db = backend["SM"]()
        run = db.query(CWOMRunModel).filter(CWOMRunModel.id == claim["run_id"]).one()
        assert run.status == "blocked" and run.failure["termination"] == "unconfirmed"
        db.close()


# --------------------------------------------------------------- concurrency
def test_concurrent_mcp_claims_single_winner(backend):
    task_id = _enqueue()
    barrier = threading.Barrier(8)
    results, errors = [], []

    def go():
        barrier.wait()
        try:
            results.append(json.loads(mcp_module.jct_claim_task(task_id)))
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(repr(exc))

    threads = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    winners = [r for r in results if r.get("success")]
    assert len(winners) == 1, results
    db = backend["SM"]()
    try:
        t = db.query(TaskModel).filter(TaskModel.id == task_id).one()
        runs = (
            db.query(CWOMRunModel)
            .filter(CWOMRunModel.for_issue_id == t.cwom_issue_id)
            .all()
        )
        assert len(runs) == 1
    finally:
        db.close()


def test_concurrent_worker_claims_single_winner(backend):
    task_id = _enqueue()
    barrier = threading.Barrier(6)
    results, errors = [], []

    def go():
        barrier.wait()
        try:
            results.append(_worker_claim(backend))
        except Exception as exc:  # pragma: no cover
            errors.append(repr(exc))

    threads = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    assert [r for r in results if r] == [r for r in results if r][:1]
    assert len([r for r in results if r]) == 1
    assert _task(backend, task_id).status == "running"


def test_concurrent_reapers_single_transition(backend, clock):
    task_id = _enqueue(budget=30)
    assert _mcp_claim(task_id)["success"]
    clock(31)
    barrier = threading.Barrier(5)
    outs, errors = [], []

    def go():
        barrier.wait()
        db = backend["SM"]()
        try:
            outs.append(process_expired_leases(db, actor_id="reaper-test"))
        except Exception as exc:  # pragma: no cover
            errors.append(repr(exc))
        finally:
            db.close()

    threads = [threading.Thread(target=go) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    assert sum(len(o["held"]) for o in outs) == 1
    assert sum(len(o["requeued"]) for o in outs) == 0
    db = backend["SM"]()
    try:
        holds = (
            db.query(AuditLogModel)
            .filter(
                AuditLogModel.entity_id == task_id, AuditLogModel.entity_kind == "Task"
            )
            .all()
        )
        assert (
            len(
                [
                    a
                    for a in holds
                    if (a.after or {}).get("status") == "held"
                    or "held" in (a.note or "")
                ]
            )
            == 1
        )
    finally:
        db.close()


# --------------------------------------------------------------- stale writes
def test_stale_holder_writes_refused_after_hold(backend, clock):
    task_id = _enqueue(budget=30)
    claim = _mcp_claim(task_id)
    ok = json.loads(
        mcp_module.jct_report_artifact(
            task_id=task_id, title="early", artifact_type="doc", content="before expiry"
        )
    )
    assert ok["success"]
    clock(31)
    json.loads(mcp_module.jct_list_tasks())  # hold
    late_art = json.loads(
        mcp_module.jct_report_artifact(
            task_id=task_id, title="late", artifact_type="doc", content="after expiry"
        )
    )
    late_done = json.loads(
        mcp_module.jct_complete_task(task_id=task_id, success=True, summary="late")
    )
    assert late_art["success"] is False and late_done["success"] is False
    assert late_art["error"]["code"] in ("TASK_NOT_RUNNING", "CLAIM_LOST")
    assert late_done["error"]["code"] in ("TASK_NOT_RUNNING", "CLAIM_LOST")
    db = backend["SM"]()
    try:
        arts = (
            db.query(CWOMArtifactModel)
            .filter(CWOMArtifactModel.produced_by_id == claim["run_id"])
            .all()
        )
        assert [a.title for a in arts] == ["early"]
        assert (
            db.query(CWOMEvidencePackModel)
            .filter(CWOMEvidencePackModel.for_run_id == claim["run_id"])
            .count()
            == 0
        )
    finally:
        db.close()


# ---------------------------------------------------------- unconfirmed termination
def test_unconfirmed_termination_never_requeues(backend, clock):
    task_id = _enqueue(budget=30)
    assert _mcp_claim(task_id)["success"]
    clock(31)
    for _ in range(3):
        clock(600)
        json.loads(mcp_module.jct_list_tasks())
        db = backend["SM"]()
        process_expired_leases(db)
        db.close()
        assert _task(backend, task_id).status == "held"
    second = _mcp_claim(task_id, actor="exec-B@test")
    assert second["success"] is False
    assert _worker_claim(backend) is None


@pytest.mark.parametrize(
    "confirmer,expected",
    [
        (None, "held"),
        (lambda t: False, "held"),
        (
            lambda t: (_ for _ in ()).throw(RuntimeError("substrate unreachable")),
            "held",
        ),
        (lambda t: True, "queued"),
    ],
)
def test_termination_confirmer_fails_closed(backend, clock, confirmer, expected):
    task_id = _enqueue(budget=30)
    assert _mcp_claim(task_id)["success"]
    clock(31)
    db = backend["SM"]()
    try:
        process_expired_leases(db, confirm_termination=confirmer)
    finally:
        db.close()
    assert _task(backend, task_id).status == expected


# --------------------------------------------------------------- operator resolution
def test_operator_resolution_rules(backend, clock):
    task_id = _enqueue(budget=30)
    assert _mcp_claim(task_id)["success"]
    clock(31)
    json.loads(mcp_module.jct_list_tasks())
    db = backend["SM"]()
    try:
        with pytest.raises(HeldTaskError, match="confirmed termination"):
            resolve_held_task(db, task_id, "requeue", "george", "looks fine")
        with pytest.raises(HeldTaskError, match="note"):
            resolve_held_task(
                db, task_id, "requeue", "george", " ", termination_confirmed=True
            )
        t = resolve_held_task(
            db,
            task_id,
            "requeue",
            "george",
            "container gone (docker ps)",
            termination_confirmed=True,
        )
        assert t.status == "queued" and t.held_at is None
        with pytest.raises(HeldTaskError, match="not held"):
            resolve_held_task(db, task_id, "fail", "george", "again")
        audit = (
            db.query(AuditLogModel)
            .filter(
                AuditLogModel.entity_id == task_id, AuditLogModel.actor_id == "george"
            )
            .all()
        )
        assert audit and all(a.actor_kind == "human" for a in audit)
    finally:
        db.close()
    claim2 = _mcp_claim(task_id, actor="exec-B@test")
    assert claim2["success"], claim2


def test_operator_fail_resolution_and_cli(backend, clock, monkeypatch, capsys):
    from devops_control_tower import held_cli
    from devops_control_tower.db import base as db_base

    task_id = _enqueue(budget=30)
    assert _mcp_claim(task_id)["success"]
    clock(31)
    json.loads(mcp_module.jct_list_tasks())
    monkeypatch.setattr(db_base, "get_session_local", lambda: backend["SM"])
    assert held_cli.main(["list"]) == 0
    assert task_id in capsys.readouterr().out
    # requeue without --confirmed-terminated is refused
    assert (
        held_cli.main(
            [
                "resolve",
                task_id,
                "--action",
                "requeue",
                "--operator",
                "george",
                "--note",
                "x",
            ]
        )
        == 2
    )
    assert _task(backend, task_id).status == "held"
    assert (
        held_cli.main(
            [
                "resolve",
                task_id,
                "--action",
                "fail",
                "--operator",
                "george",
                "--note",
                "abandon",
            ]
        )
        == 0
    )
    assert _task(backend, task_id).status == "failed"
    with pytest.raises(SystemExit):  # --operator and --note are mandatory
        held_cli.main(["resolve", task_id, "--action", "fail"])


# --------------------------------------------------------------- restart recovery
def test_restart_recovery(backend, clock):
    """After a restart: valid claims continue, expired ones held, holds persist."""
    a = _enqueue(budget=600, objective="A long")
    b = _enqueue(budget=30, objective="B short")
    claim_a = _mcp_claim(a)
    assert claim_a["success"]
    assert _worker_claim(backend)[0] == b

    backend["restart"]()  # process restart: in-memory claims and pool gone
    clock(31)  # B's lease has expired, A's hasn't
    assert loop_module.WorkerLoop(executor_type="stub")._poll_and_process() == 0
    assert _task(backend, b).status == "held"
    assert _task(backend, a).status == "running"

    # The valid holder of A completes after the restart (DB fallback for the claim)
    done = json.loads(
        mcp_module.jct_complete_task(task_id=a, success=True, summary="ok")
    )
    assert done["success"], done
    assert _task(backend, a).status == "completed"

    backend["restart"]()  # holds survive another restart; nothing requeued
    clock(3600)
    json.loads(mcp_module.jct_list_tasks())
    assert _task(backend, b).status == "held"


# --------------------------------------------------------------- experimental runs
def test_unauthorized_experiment_refused_at_intake(backend):
    r = json.loads(
        mcp_module.jct_enqueue_task(
            objective="unauthorized experiment probe",
            operation="analysis",
            target_repo="testorg/repo",
            time_budget_seconds=60,
            metadata={"experiment": {"id": "NOT-AUTHORIZED"}},
        )
    )
    assert r["success"] is False
    assert r["error"]["code"] == "EXPERIMENT_NOT_AUTHORIZED"


def _run_to_evidence(backend, metadata=None):
    task_id = _enqueue(budget=300, metadata=metadata)
    claim = _mcp_claim(task_id)
    assert claim["success"]
    json.loads(
        mcp_module.jct_report_artifact(
            task_id=task_id, title="report", artifact_type="report", content="ok"
        )
    )
    done = json.loads(
        mcp_module.jct_complete_task(task_id=task_id, success=True, summary="ok")
    )
    assert done["success"], done
    return task_id, claim["run_id"], done


def test_experimental_run_never_production_eligible(backend):
    from devops_control_tower.worker.eligibility import production_eligibility

    _, run_id, done = _run_to_evidence(
        backend, metadata={"experiment": {"id": "EXP-TEST"}}
    )
    # auto-approve is ON in this fixture, yet experimental evidence is not auto-approved
    assert done.get("review", {}).get("status") != "auto_approved"
    ep_id = done["evidence_pack"]["id"]
    approved = _as(
        "reviewer@test", mcp_module.jct_submit_review, ep_id, "approved", "fine"
    )
    assert approved["success"], approved
    db = backend["SM"]()
    try:
        ep = (
            db.query(CWOMEvidencePackModel)
            .filter(CWOMEvidencePackModel.id == ep_id)
            .one()
        )
        assert "experimental" in ep.tags and ep.verdict_reason.startswith(
            "[EXPERIMENTAL"
        )
        elig = production_eligibility(db, ep)
        assert elig["eligible"] is False
        assert any("experimental" in r for r in elig["reasons"])
    finally:
        db.close()
    read = _as("reviewer@test", mcp_module.jct_get_evidence, ep_id)
    assert read["production_eligibility"]["eligible"] is False


def test_production_run_eligible_only_with_independent_approval(backend, monkeypatch):
    from devops_control_tower.cwom.routes import get_evidence_pack

    monkeypatch.setattr(cfg_mod.settings, "jct_review_auto_approve", False)
    _, run_id, done = _run_to_evidence(backend)
    ep_id = done["evidence_pack"]["id"]
    before = _as("reviewer@test", mcp_module.jct_get_evidence, ep_id)
    assert before["production_eligibility"]["eligible"] is False  # not reviewed yet
    self_review = _as(
        "exec-A@test", mcp_module.jct_submit_review, ep_id, "approved", "me"
    )
    assert self_review["success"] is False
    ok = _as(
        "reviewer@test", mcp_module.jct_submit_review, ep_id, "approved", "checked"
    )
    assert ok["success"], ok
    import asyncio

    db = backend["SM"]()
    try:
        body = asyncio.run(get_evidence_pack(ep_id, db=db))
        assert body["production_eligibility"] == {"eligible": True, "reasons": []}
    finally:
        db.close()
