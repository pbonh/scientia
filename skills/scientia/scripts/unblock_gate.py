#!/usr/bin/env python3
"""unblock_gate.py — gate `hermes kanban unblock` so the orchestrator never
re-promotes a task whose blocker hasn't actually been resolved.

Without a gate, the common failure mode is: an orchestrator unblocks
an integrator whose worker branch head hasn't moved since the block,
the integrator immediately re-blocks on the same rebase conflict, and
the cycle repeats. The gate also surfaces premature unblocks where a
reviewer's REQUEST CHANGES is still outstanding or a parent task is
not yet `done`.

Usage
-----

    python3 unblock_gate.py <task-id> [--repo <path>]
                                      [--json]
                                      [--allow-stale-head]

Behavior:

  * Exits 0 and prints the safe `hermes kanban unblock <id>` command if
    every gate passes.
  * Exits 1 with one line per failing gate (severity-prefixed) if any
    gate fails. The caller MUST NOT execute the unblock — fix the
    underlying problem and re-run.

Gates evaluated (v0.1):

  1. Task exists, is `blocked`, and its assignee is a scientia profile.
  2. For integrator tasks: the worker branch's current HEAD has advanced
     past the `branch_head` recorded in the blocking handoff. If the SHA
     is unchanged, the block has not been resolved; unblocking would just
     re-block on the same conflict.
  3. For any task: every `--parent` (Hermes dependency edge) is in status
     `done`. Hermes itself enforces this for dispatch, but checking
     surfaces the missing parent in the diagnostic.
  4. Comment thread does not contain a fresh REQUEST CHANGES from a
     reviewer past the most recent block event.

This is the script form of the rule in `scientia/SKILL.md` →
"Boundaries (never do)": "Never call `hermes kanban unblock` on an
integrator without the gate check below."

Sibling: `sweep_blocked.py` iterates every `blocked` row in the kanban
and runs this gate on each.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SEVERITIES = ["suggestion", "warning", "critical"]
SCIENTIA_PROFILES = {
    "scientia-implementer",
    "scientia-reviewer",
    "scientia-integrator",
    "scientia-aggregator",
}


@dataclass
class GateResult:
    gate: str
    severity: str
    message: str


@dataclass
class GateReport:
    task_id: str
    results: list[GateResult] = field(default_factory=list)

    def add(self, gate: str, severity: str, message: str) -> None:
        assert severity in SEVERITIES, severity
        self.results.append(GateResult(gate, severity, message))

    def worst(self) -> str:
        worst = -1
        for r in self.results:
            worst = max(worst, SEVERITIES.index(r.severity))
        return SEVERITIES[worst] if worst >= 0 else "clean"

    def passed(self, threshold: str = "warning") -> bool:
        if not self.results:
            return True
        return SEVERITIES.index(self.worst()) < SEVERITIES.index(threshold)


# --- Hermes CLI shims --------------------------------------------------------

def hermes_show(task_id: str) -> dict | None:
    """Return `hermes kanban show <task_id> --json` parsed, or None on failure."""
    if shutil.which("hermes") is None:
        return None
    try:
        r = subprocess.run(
            ["hermes", "kanban", "show", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=20,
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def hermes_show_many(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for tid in ids:
        d = hermes_show(tid)
        if d is not None:
            out[tid] = d
    return out


# --- Handoff parsing ---------------------------------------------------------

BRANCH_HEAD_RE = re.compile(
    r"^\s*-?\s*\*?\*?branch[_ ]head\*?\*?\s*[:=]\s*`?([0-9a-f]{7,40})`?",
    re.IGNORECASE | re.MULTILINE,
)
BRANCH_NAME_RE = re.compile(
    r"^\s*-?\s*\*?\*?branch[_ ]name\*?\*?\s*[:=]\s*`?([^\s`]+)`?",
    re.IGNORECASE | re.MULTILINE,
)


def extract_branch_head(handoff_text: str) -> str | None:
    m = BRANCH_HEAD_RE.search(handoff_text or "")
    return m.group(1) if m else None


def extract_branch_name(handoff_text: str) -> str | None:
    m = BRANCH_NAME_RE.search(handoff_text or "")
    return m.group(1) if m else None


def latest_handoff(task: dict) -> str:
    """The blocking handoff lives in `result` (set by `kanban block --result-file`)
    or in the most recent comment whose body contains `## Required Handoff`.
    Prefer `result`; fall back to the latest matching comment.
    """
    if isinstance(task.get("result"), str) and "branch_head" in task["result"].lower():
        return task["result"]
    for c in reversed(task.get("comments") or []):
        body = c.get("body") if isinstance(c, dict) else None
        if isinstance(body, str) and "Required Handoff" in body:
            return body
    return ""


# --- Git probes --------------------------------------------------------------

def git_branch_head(repo: Path, branch: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=repo, capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool | None:
    """True if `ancestor` is reachable from `descendant`. None on unknown SHA."""
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo, capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return None
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    return None


# --- Gates -------------------------------------------------------------------

def gate_task_blocked(task: dict, report: GateReport) -> None:
    status = task.get("status")
    if status != "blocked":
        report.add(
            "task-status",
            "critical",
            f"task is not `blocked` (status={status!r}); unblock would be a no-op or a regression",
        )


def gate_scientia_profile(task: dict, report: GateReport) -> None:
    assignee = task.get("assignee") or ""
    if assignee not in SCIENTIA_PROFILES:
        report.add(
            "scientia-profile",
            "warning",
            f"assignee {assignee!r} is not a known scientia profile; gate cannot reason about its role",
        )


def gate_branch_head_advanced(
    task: dict,
    repo: Path,
    report: GateReport,
    allow_stale_head: bool,
) -> None:
    if task.get("assignee") != "scientia-integrator":
        return
    handoff = latest_handoff(task)
    if not handoff:
        report.add(
            "branch-head",
            "warning",
            "no handoff with a branch_head field on this blocked integrator; cannot verify resolution",
        )
        return
    blocked_head = extract_branch_head(handoff)
    branch = extract_branch_name(handoff)
    if not blocked_head:
        report.add(
            "branch-head",
            "warning",
            "handoff is present but its branch_head is unparseable",
        )
        return
    if not branch:
        report.add(
            "branch-head",
            "warning",
            "handoff is present but its branch_name is unparseable; cannot resolve current HEAD",
        )
        return
    current = git_branch_head(repo, branch)
    if current is None:
        report.add(
            "branch-head",
            "warning",
            f"cannot resolve current head of branch {branch!r} (not fetched locally?)",
        )
        return
    if current == blocked_head:
        sev = "warning" if allow_stale_head else "critical"
        report.add(
            "branch-head",
            sev,
            f"branch {branch} HEAD is still {blocked_head[:12]} — unchanged since block. "
            "Conflict has not been resolved; unblocking will just re-block.",
        )


def gate_parents_done(task: dict, report: GateReport) -> None:
    parent_ids = task.get("parent_ids") or task.get("parents") or []
    if not parent_ids:
        return
    parents = hermes_show_many(list(parent_ids))
    for pid in parent_ids:
        p = parents.get(pid)
        if p is None:
            report.add("parents-done", "warning",
                       f"parent {pid} not resolvable via `hermes kanban show`")
            continue
        if p.get("status") != "done":
            report.add(
                "parents-done",
                "critical",
                f"parent {pid} is in status {p.get('status')!r}, not `done`; "
                "Hermes will refuse to dispatch this task even after unblock",
            )


REQUEST_CHANGES_RE = re.compile(r"\bREQUEST\s+CHANGES\b", re.IGNORECASE)


def gate_no_fresh_request_changes(task: dict, report: GateReport) -> None:
    """If a reviewer posted REQUEST CHANGES after the most recent block event,
    the integrator should not be unblocked — the implementer needs to respawn.
    """
    comments = task.get("comments") or []
    # find latest block event timestamp
    events = task.get("events") or []
    last_block_ts = None
    for e in events:
        if (e.get("event") or e.get("name")) == "block":
            ts = e.get("ts") or e.get("at")
            if ts and (last_block_ts is None or ts > last_block_ts):
                last_block_ts = ts
    if last_block_ts is None:
        return
    for c in comments:
        body = c.get("body") or ""
        ts = c.get("ts") or c.get("created_at")
        if ts and ts >= last_block_ts and REQUEST_CHANGES_RE.search(body):
            report.add(
                "reviewer-changes",
                "critical",
                f"reviewer posted REQUEST CHANGES at {ts} (after the block at "
                f"{last_block_ts}); implementer must respawn before unblock",
            )
            return


# --- Driver ------------------------------------------------------------------

def run_gates(task_id: str, repo: Path, allow_stale_head: bool) -> GateReport:
    report = GateReport(task_id=task_id)
    task = hermes_show(task_id)
    if task is None:
        report.add(
            "task-lookup",
            "critical",
            f"could not resolve task {task_id!r} via `hermes kanban show --json`",
        )
        return report

    gate_task_blocked(task, report)
    gate_scientia_profile(task, report)
    gate_branch_head_advanced(task, repo, report, allow_stale_head)
    gate_parents_done(task, report)
    gate_no_fresh_request_changes(task, report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("task_id", help="Hermes kanban task id (e.g. t_abcd1234)")
    ap.add_argument("--repo", default=os.getcwd(),
                    help="repository root (default: cwd)")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON report")
    ap.add_argument("--allow-stale-head", action="store_true",
                    help="downgrade the stale-branch_head gate from critical to warning")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    report = run_gates(args.task_id, repo, args.allow_stale_head)

    if args.json:
        print(json.dumps({
            "task_id": report.task_id,
            "worst": report.worst(),
            "passed": report.passed(),
            "results": [
                {"gate": r.gate, "severity": r.severity, "message": r.message}
                for r in report.results
            ],
        }, indent=2))
    else:
        if report.passed():
            print(f"# unblock_gate: PASS for {report.task_id}")
            print(f"hermes kanban unblock {report.task_id}")
            return 0
        print(f"# unblock_gate: REFUSE for {report.task_id} (worst={report.worst()})")
        for r in report.results:
            print(f"- [{r.severity.upper()}] {r.gate}: {r.message}")
        print()
        print("Do not run `hermes kanban unblock` until each critical finding is resolved.")
        print("Override with --allow-stale-head only if you have just merged the unblocking work.")

    return 0 if report.passed() else 1


if __name__ == "__main__":
    sys.exit(main())
