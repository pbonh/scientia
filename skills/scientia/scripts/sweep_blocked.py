#!/usr/bin/env python3
"""sweep_blocked.py — find blocked kanban tasks whose blockers are resolved.

Hermes does not auto-promote `blocked → ready` when a task's dependencies
complete: even after a respawn child lands on trunk, the parent
integrator stays `blocked` until a human runs `hermes kanban unblock`.
This sweep automates the safe subset of that recovery.

This sweep:

1. Lists every `blocked` task via `hermes kanban list --json`.
2. For each, runs the `unblock_gate.py` gates (task-status,
   branch-head-advanced, parents-done, no-fresh-request-changes).
3. Prints the safe `hermes kanban unblock <id>` commands that pass the
   gate. By default does NOT execute them. Pass `--apply` to execute
   after a y/n confirmation.
4. Detects parent-child deadlock cycles (a blocked parent whose only
   child is `todo` and parented to the same blocked parent) and prints
   the `hermes kanban unlink <parent> <child>` recipe. This pattern
   arises when a blocked worker creates a respawn task as its own
   child instead of as a sibling — neither end can ever dispatch.

Usage:

    python3 sweep_blocked.py [--repo <path>] [--tenant <tenant>]
                              [--json] [--apply]

Stdlib-only. Imports `unblock_gate` as a library.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import unblock_gate  # noqa: E402  (after sys.path edit)


@dataclass
class SweepResult:
    safe_unblocks: list[str] = field(default_factory=list)  # task ids that pass the gate
    refused: list[tuple[str, str]] = field(default_factory=list)  # (task_id, worst reason)
    deadlocks: list[tuple[str, str]] = field(default_factory=list)  # (parent, child)


def hermes_list_blocked(tenant: str | None) -> list[dict]:
    """Return the list of blocked tasks, optionally filtered by tenant."""
    if shutil.which("hermes") is None:
        return []
    cmd = ["hermes", "kanban", "list", "--json"]
    if tenant:
        cmd += ["--tenant", tenant]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    except Exception:
        return []
    if r.returncode != 0:
        return []
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and "tasks" in data:
        data = data["tasks"]
    return [t for t in data if isinstance(t, dict) and t.get("status") == "blocked"]


def find_deadlocks(blocked: list[dict]) -> list[tuple[str, str]]:
    """Return (parent_id, child_id) pairs where:

    - parent is `blocked`,
    - child is `todo` AND child's parents include parent,
    - parent's blocked handoff names child as its unblocker
      (heuristic: child id appears in parent's handoff text), OR child's
      only outstanding parent is `parent`.

    This is the parent-child deadlock cascade pattern: a worker
    blocked and (mistakenly) created its respawn task with itself as
    `--parent`, so neither end can dispatch.
    """
    deadlocks: list[tuple[str, str]] = []
    by_id = {t["id"]: t for t in blocked}
    for parent in blocked:
        parent_id = parent.get("id")
        if not parent_id:
            continue
        handoff = unblock_gate.latest_handoff(parent)
        children = parent.get("children") or parent.get("child_ids") or []
        for cid in children:
            child = unblock_gate.hermes_show(cid)
            if child is None:
                continue
            if child.get("status") != "todo":
                continue
            parent_ids = child.get("parent_ids") or child.get("parents") or []
            if parent_id not in parent_ids:
                continue
            # Heuristic: child references the same conflict the parent
            # blocked on, OR the parent is the child's only blocking parent.
            other_parents = [p for p in parent_ids if p != parent_id]
            all_other_done = True
            for op in other_parents:
                ot = unblock_gate.hermes_show(op)
                if ot is None or ot.get("status") != "done":
                    all_other_done = False
                    break
            if all_other_done:
                deadlocks.append((parent_id, cid))
                continue
            if cid in handoff:
                deadlocks.append((parent_id, cid))
    return deadlocks


def run_sweep(repo: Path, tenant: str | None, allow_stale_head: bool) -> SweepResult:
    result = SweepResult()
    blocked = hermes_list_blocked(tenant)
    if not blocked:
        return result
    for task in blocked:
        tid = task.get("id")
        if not tid:
            continue
        gate_report = unblock_gate.run_gates(tid, repo, allow_stale_head)
        if gate_report.passed():
            result.safe_unblocks.append(tid)
        else:
            worst = next(
                (r.message for r in gate_report.results if r.severity == "critical"),
                gate_report.results[0].message if gate_report.results else "(unknown)",
            )
            result.refused.append((tid, worst))
    result.deadlocks = find_deadlocks(blocked)
    return result


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return input(f"{prompt} [y/N] ").strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--tenant", default=None,
                    help="restrict to one tenant; default is every tenant on the board")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON")
    ap.add_argument("--apply", action="store_true",
                    help="after confirmation, run the unblock + unlink commands")
    ap.add_argument("--allow-stale-head", action="store_true",
                    help="downgrade the branch_head gate from critical to warning")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    result = run_sweep(repo, args.tenant, args.allow_stale_head)

    if args.json:
        print(json.dumps({
            "safe_unblocks": result.safe_unblocks,
            "refused": [{"task_id": tid, "reason": r} for tid, r in result.refused],
            "deadlocks": [{"parent": p, "child": c} for p, c in result.deadlocks],
        }, indent=2))
    else:
        print(f"# sweep_blocked: {len(result.safe_unblocks)} safe, "
              f"{len(result.refused)} refused, {len(result.deadlocks)} deadlock(s)")
        if result.deadlocks:
            print()
            print("## Deadlocks (blocked parent ↔ todo child)")
            for parent, child in result.deadlocks:
                print(f"hermes kanban unlink {parent} {child}")
        if result.safe_unblocks:
            print()
            print("## Safe to unblock")
            for tid in result.safe_unblocks:
                print(f"hermes kanban unblock {tid}")
        if result.refused:
            print()
            print("## Refused (resolve the underlying block first)")
            for tid, reason in result.refused:
                print(f"# {tid}: {reason}")

    if args.apply:
        if not (result.safe_unblocks or result.deadlocks):
            return 0
        if not _confirm("apply the printed commands?"):
            print("aborted", file=sys.stderr)
            return 0
        for parent, child in result.deadlocks:
            subprocess.run(["hermes", "kanban", "unlink", parent, child], check=False)
        for tid in result.safe_unblocks:
            subprocess.run(["hermes", "kanban", "unblock", tid], check=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
