"""Unit tests for unblock_gate.py.

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

import unblock_gate  # noqa: E402


def _integrator_task(
    branch_head: str = "deadbeef1234",
    branch_name: str = "impl/circuit-builder-build-t_147de37e",
    status: str = "blocked",
    assignee: str = "scientia-integrator",
    parent_ids: list[str] | None = None,
    comments: list[dict] | None = None,
    events: list[dict] | None = None,
) -> dict:
    handoff = (
        "## Required Handoff\n"
        f"- branch_name: {branch_name}\n"
        f"- branch_head: {branch_head}\n"
        "- blocked_reason: rebase conflict\n"
    )
    return {
        "id": "t_test",
        "status": status,
        "assignee": assignee,
        "result": handoff,
        "parent_ids": parent_ids or [],
        "comments": comments or [],
        "events": events or [],
    }


class StaleBranchHeadTests(unittest.TestCase):
    """Gate 2: integrator branch_head must advance before unblock."""

    def test_stale_head_is_critical(self):
        task = _integrator_task(branch_head="deadbeef1234")
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="deadbeef1234"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        self.assertFalse(report.passed())
        msgs = [(r.gate, r.severity) for r in report.results]
        self.assertIn(("branch-head", "critical"), msgs)

    def test_advanced_head_clears_gate(self):
        task = _integrator_task(branch_head="deadbeef1234")
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="cafef00d5678"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        gates = [r.gate for r in report.results]
        self.assertNotIn("branch-head", gates)

    def test_allow_stale_downgrades_to_warning(self):
        task = _integrator_task(branch_head="deadbeef1234")
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="deadbeef1234"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=True)
        sevs = {(r.gate, r.severity) for r in report.results}
        self.assertIn(("branch-head", "warning"), sevs)
        self.assertNotIn(("branch-head", "critical"), sevs)

    def test_implementer_skips_branch_head_gate(self):
        task = _integrator_task(branch_head="deadbeef1234",
                                 assignee="scientia-implementer")
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="deadbeef1234"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        # branch-head gate only applies to integrators
        self.assertNotIn("branch-head", [r.gate for r in report.results])


class ParentsDoneTests(unittest.TestCase):
    """Gate 3: every --parent must be `done`."""

    def test_missing_parent_is_critical(self):
        task = _integrator_task(branch_head="aaaa1111",
                                  parent_ids=["t_parent1"])
        parents = {"t_parent1": {"id": "t_parent1", "status": "running"}}
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "hermes_show_many", return_value=parents), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="bbbb2222"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        self.assertFalse(report.passed())
        msgs = [(r.gate, r.severity) for r in report.results]
        self.assertIn(("parents-done", "critical"), msgs)

    def test_all_parents_done_clears_gate(self):
        task = _integrator_task(branch_head="aaaa1111",
                                  parent_ids=["t_parent1"])
        parents = {"t_parent1": {"id": "t_parent1", "status": "done"}}
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "hermes_show_many", return_value=parents), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="bbbb2222"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        self.assertNotIn("parents-done", [r.gate for r in report.results])


class TaskStatusTests(unittest.TestCase):
    def test_not_blocked_is_critical(self):
        task = _integrator_task(branch_head="aaaa1111", status="running")
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="bbbb2222"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        msgs = [(r.gate, r.severity) for r in report.results]
        self.assertIn(("task-status", "critical"), msgs)

    def test_missing_task_is_critical(self):
        with mock.patch.object(unblock_gate, "hermes_show", return_value=None):
            report = unblock_gate.run_gates("t_nope", Path("/tmp"), allow_stale_head=False)
        msgs = [(r.gate, r.severity) for r in report.results]
        self.assertIn(("task-lookup", "critical"), msgs)


class RequestChangesTests(unittest.TestCase):
    def test_fresh_request_changes_blocks(self):
        events = [{"event": "block", "ts": "2026-01-01T14:00:00Z"}]
        comments = [
            {"ts": "2026-01-01T14:30:00Z",
             "body": "REQUEST CHANGES — lint regression on src/foo.rs"},
        ]
        task = _integrator_task(branch_head="aaaa1111", events=events,
                                  comments=comments)
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="bbbb2222"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        msgs = [(r.gate, r.severity) for r in report.results]
        self.assertIn(("reviewer-changes", "critical"), msgs)

    def test_old_request_changes_does_not_block(self):
        events = [{"event": "block", "ts": "2026-01-01T14:00:00Z"}]
        comments = [
            {"ts": "2026-01-01T13:00:00Z",
             "body": "REQUEST CHANGES — old, predates the block"},
        ]
        task = _integrator_task(branch_head="aaaa1111", events=events,
                                  comments=comments)
        with mock.patch.object(unblock_gate, "hermes_show", return_value=task), \
             mock.patch.object(unblock_gate, "git_branch_head", return_value="bbbb2222"):
            report = unblock_gate.run_gates("t_test", Path("/tmp"), allow_stale_head=False)
        self.assertNotIn("reviewer-changes", [r.gate for r in report.results])


class HandoffParseTests(unittest.TestCase):
    def test_extract_branch_head_canonical(self):
        h = "## Required Handoff\n- branch_head: abc1234def\n"
        self.assertEqual(unblock_gate.extract_branch_head(h), "abc1234def")

    def test_extract_branch_head_with_backticks(self):
        h = "## Required Handoff\n- branch_head: `abc1234def`\n"
        self.assertEqual(unblock_gate.extract_branch_head(h), "abc1234def")

    def test_extract_branch_name(self):
        h = "## Required Handoff\n- branch_name: impl/foo-bar\n- branch_head: aaa1234\n"
        self.assertEqual(unblock_gate.extract_branch_name(h), "impl/foo-bar")

    def test_missing_branch_head_returns_none(self):
        self.assertIsNone(unblock_gate.extract_branch_head("no handoff here"))


if __name__ == "__main__":
    unittest.main()
