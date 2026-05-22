"""Unit tests for sweep_blocked.py.

Run from the parent scripts/ directory:

    cd skills/scientia/scripts
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import sweep_blocked  # noqa: E402
import unblock_gate  # noqa: E402


def _make_handoff(branch_head: str = "abc1234",
                  branch_name: str = "impl/x-t_111") -> str:
    return (
        "## Required Handoff\n"
        f"- branch_name: {branch_name}\n"
        f"- branch_head: {branch_head}\n"
    )


class DeadlockDetectionTests(unittest.TestCase):
    """Parent-child deadlock pattern: a blocked parent whose `todo` child
    is parented to that same blocked parent. The child cannot dispatch
    until the parent is `done`, but the parent's block can only resolve
    once the child completes — neither side ever moves.
    """

    def test_detects_blocked_integrator_with_todo_respawn_child(self):
        # An integrator that blocked on a rebase conflict and (mistakenly)
        # created its implementer-respawn task as its own child.
        parent = {
            "id": "t_parent",
            "status": "blocked",
            "assignee": "scientia-integrator",
            "result": _make_handoff() + "\n- referencing child t_child\n",
            "children": ["t_child"],
        }
        child = {
            "id": "t_child",
            "status": "todo",
            "assignee": "scientia-implementer",
            "parent_ids": ["t_parent"],
        }
        with mock.patch.object(unblock_gate, "hermes_show",
                                side_effect=lambda tid: child if tid == "t_child" else None):
            deadlocks = sweep_blocked.find_deadlocks([parent])
        self.assertEqual(deadlocks, [("t_parent", "t_child")])

    def test_no_deadlock_when_child_is_running(self):
        parent = {
            "id": "t_parent",
            "status": "blocked",
            "result": _make_handoff(),
            "children": ["t_child"],
        }
        child = {"id": "t_child", "status": "running",
                  "parent_ids": ["t_parent"]}
        with mock.patch.object(unblock_gate, "hermes_show", return_value=child):
            deadlocks = sweep_blocked.find_deadlocks([parent])
        self.assertEqual(deadlocks, [])

    def test_no_deadlock_when_child_has_other_pending_parent(self):
        # Child has another non-done parent — it's blocked legitimately,
        # not by the deadlock pattern.
        parent = {
            "id": "t_parent",
            "status": "blocked",
            "result": _make_handoff(),
            "children": ["t_child"],
        }
        child = {"id": "t_child", "status": "todo",
                  "parent_ids": ["t_parent", "t_other"]}
        other = {"id": "t_other", "status": "running"}
        with mock.patch.object(unblock_gate, "hermes_show",
                                side_effect=lambda tid: {"t_child": child, "t_other": other}.get(tid)):
            deadlocks = sweep_blocked.find_deadlocks([parent])
        self.assertEqual(deadlocks, [])

    def test_deadlock_when_other_parents_done(self):
        # Child has another parent but it's done — the deadlock is real.
        parent = {
            "id": "t_parent",
            "status": "blocked",
            "result": _make_handoff(),
            "children": ["t_child"],
        }
        child = {"id": "t_child", "status": "todo",
                  "parent_ids": ["t_parent", "t_other"]}
        other = {"id": "t_other", "status": "done"}
        with mock.patch.object(unblock_gate, "hermes_show",
                                side_effect=lambda tid: {"t_child": child, "t_other": other}.get(tid)):
            deadlocks = sweep_blocked.find_deadlocks([parent])
        self.assertEqual(deadlocks, [("t_parent", "t_child")])


class SafeUnblockTests(unittest.TestCase):
    def test_advanced_branch_passes_gate(self):
        blocked = [{
            "id": "t_int",
            "status": "blocked",
            "assignee": "scientia-integrator",
            "result": _make_handoff(branch_head="oldsha1234"),
        }]
        # The gate would also be invoked, but we patch unblock_gate.run_gates
        # directly to avoid wiring full subprocess mocks.
        passing = unblock_gate.GateReport(task_id="t_int")
        with mock.patch.object(sweep_blocked, "hermes_list_blocked", return_value=blocked), \
             mock.patch.object(sweep_blocked, "find_deadlocks", return_value=[]), \
             mock.patch.object(unblock_gate, "run_gates", return_value=passing):
            result = sweep_blocked.run_sweep(Path("/tmp"), tenant=None, allow_stale_head=False)
        self.assertEqual(result.safe_unblocks, ["t_int"])
        self.assertEqual(result.refused, [])

    def test_stale_branch_refused(self):
        blocked = [{
            "id": "t_int",
            "status": "blocked",
            "assignee": "scientia-integrator",
            "result": _make_handoff(branch_head="oldsha1234"),
        }]
        failing = unblock_gate.GateReport(task_id="t_int")
        failing.add("branch-head", "critical", "branch HEAD is still oldsha1234")
        with mock.patch.object(sweep_blocked, "hermes_list_blocked", return_value=blocked), \
             mock.patch.object(sweep_blocked, "find_deadlocks", return_value=[]), \
             mock.patch.object(unblock_gate, "run_gates", return_value=failing):
            result = sweep_blocked.run_sweep(Path("/tmp"), tenant=None, allow_stale_head=False)
        self.assertEqual(result.safe_unblocks, [])
        self.assertEqual(len(result.refused), 1)
        self.assertEqual(result.refused[0][0], "t_int")


class EmptyBoardTests(unittest.TestCase):
    def test_no_blocked_tasks_is_clean(self):
        with mock.patch.object(sweep_blocked, "hermes_list_blocked", return_value=[]):
            result = sweep_blocked.run_sweep(Path("/tmp"), tenant=None, allow_stale_head=False)
        self.assertEqual(result.safe_unblocks, [])
        self.assertEqual(result.refused, [])
        self.assertEqual(result.deadlocks, [])


if __name__ == "__main__":
    unittest.main()
