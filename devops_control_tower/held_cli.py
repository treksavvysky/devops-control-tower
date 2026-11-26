"""
Operator commands for held tasks (DEVOPS-CON-11).

A task is *held* when its claim lease expired and the previous holder's
termination couldn't be confirmed. An operator resolves it here; there is no
MCP or REST surface for resolution.

What this does NOT guarantee: ``--operator`` is recorded in the audit log but
not verified. Anyone who can run this command against the DCT database,
including an executor agent with a shell on the same host, can resolve a
hold and assert termination. Restricting who can resolve holds needs operator
authentication (DEVOPS-CON-5).

    dct-held list
    dct-held resolve TASK_ID --action requeue --confirmed-terminated \\
        --operator george --note "container confirmed gone via docker ps"
    dct-held resolve TASK_ID --action fail --operator george --note "abandon"

Uses argparse rather than typer: the pinned typer 0.9 is incompatible with
current click releases (usage rendering raises TypeError), and this command
must work.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional


def _session():
    from .db.base import get_session_local

    return get_session_local()()


def _list(_args) -> int:
    from .worker.leases import list_held_tasks

    db = _session()
    try:
        tasks = list_held_tasks(db)
        if not tasks:
            print("No held tasks.")
            return 0
        for t in tasks:
            print(f"{t.id}  held_at={t.held_at}  holder={t.assigned_to}")
            print(f"    objective: {t.objective[:60]}")
            print(f"    reason: {t.held_reason}")
        return 0
    finally:
        db.close()


def _resolve(args) -> int:
    from .worker.leases import HeldTaskError, resolve_held_task

    db = _session()
    try:
        task = resolve_held_task(
            db,
            args.task_id,
            args.action,
            args.operator,
            args.note,
            termination_confirmed=args.confirmed_terminated,
        )
        print(f"{task.id} -> {task.status}")
        return 0
    except HeldTaskError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dct-held",
        description=(
            "Inspect and resolve held tasks "
            "(expired leases, termination unconfirmed)."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List held tasks, oldest first").set_defaults(
        func=_list
    )
    r = sub.add_parser("resolve", help="Resolve a held task: requeue or fail")
    r.add_argument("task_id")
    r.add_argument("--action", required=True, choices=["requeue", "fail"])
    r.add_argument("--operator", required=True, help="Your identity (audited)")
    r.add_argument("--note", required=True, help="Why; what you checked")
    r.add_argument(
        "--confirmed-terminated",
        action="store_true",
        help="Assert the previous holder is no longer running (required to requeue)",
    )
    r.set_defaults(func=_resolve)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
