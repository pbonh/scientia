"""Tests for the tasks.md emission path: build_task_bodies, emit_tasks,
and the per-scenario --parent wiring in emit_one."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from tests import _paths  # noqa: F401

import emit


# ---------------------------------------------------------------------------
# Fake runner — same pattern as test_emit_one
# ---------------------------------------------------------------------------


class FakeRunner:
    def __init__(self):
        self.calls: list[list[str]] = []
        self._next_id = 0

    def __call__(self, argv, *, capture_output=True, text=True, check=False, **_):
        self.calls.append(list(argv))
        if "create" in argv:
            self._next_id += 1
            tid = f"t_{self._next_id:02d}"
            return SimpleNamespace(returncode=0,
                                   stdout=json.dumps({"task_id": tid}),
                                   stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def _argv_value(argv, flag):
    """Return the value following `flag` in argv (None if absent)."""
    try:
        i = argv.index(flag)
        return argv[i + 1]
    except (ValueError, IndexError):
        return None


def _argv_all(argv, flag):
    """All values for a repeatable flag like --parent."""
    out = []
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            out.append(argv[i + 1])
    return out


# ---------------------------------------------------------------------------
# Change-dir fixture: minimal tasks.md + ADR + handoff
# ---------------------------------------------------------------------------


TASKS_MD = """---
title: "Tasks: cap"
tenant: foo
change_id: 2026-01-01-foo
---

# Implementation Plan

## Workspace

- [ ] **1.** Workspace stub — non-behavioral
- [ ] **2.** Shared types — @adr: ADR-0001 (depends on #1)

## Capability: cap-a

- [ ] **3.** Cap-a core impl — @spec: cap-a#scn-1 (depends on #2)
"""

ADR_MD = """---
adr_id: ADR-0001
title: Some decision
status: accepted
---

# Decision

Body.
"""

HANDOFF_MD = """## Required Handoff
- something
"""


def _make_change(tmpdir: Path) -> Path:
    """Create a minimal change_dir with tasks.md + adr/ + handoff.

    Returns the change_dir path.
    """
    change_dir = tmpdir / "openspec" / "changes" / "foo-2026-01-01-foo"
    change_dir.mkdir(parents=True)
    (change_dir / "tasks.md").write_text(TASKS_MD, encoding="utf-8")

    adr_dir = change_dir / "adr"
    adr_dir.mkdir()
    (adr_dir / "ADR-0001.md").write_text(ADR_MD, encoding="utf-8")

    return change_dir


# ---------------------------------------------------------------------------
# build_task_bodies
# ---------------------------------------------------------------------------


class BuildTaskBodiesTest(unittest.TestCase):

    def test_returns_one_body_per_item_in_topo_order(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            change_dir = _make_change(tmp)
            handoff = tmp / "HANDOFF.md"
            handoff.write_text(HANDOFF_MD, encoding="utf-8")

            bundle = emit.build_task_bodies(
                change_dir=change_dir,
                change_slug="2026-01-01-foo",
                handoff_path=handoff,
            )
            self.assertEqual([b.number for b in bundle.items], [1, 2, 3])

    def test_idempotency_keys_include_change_slug_and_task_slug(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            change_dir = _make_change(tmp)
            handoff = tmp / "HANDOFF.md"
            handoff.write_text(HANDOFF_MD, encoding="utf-8")

            bundle = emit.build_task_bodies(
                change_dir=change_dir,
                change_slug="2026-01-01-foo",
                handoff_path=handoff,
            )
            for body in bundle.items:
                self.assertTrue(
                    body.idempotency_key.startswith("2026-01-01-foo:task-"),
                    body.idempotency_key,
                )

    def test_empty_bundle_when_no_tasks_md(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            change_dir = tmp / "openspec" / "changes" / "foo-bar"
            change_dir.mkdir(parents=True)
            (change_dir / "adr").mkdir()
            handoff = tmp / "HANDOFF.md"
            handoff.write_text(HANDOFF_MD, encoding="utf-8")

            bundle = emit.build_task_bodies(
                change_dir=change_dir,
                change_slug="bar",
                handoff_path=handoff,
            )
            self.assertEqual(bundle.items, [])


# ---------------------------------------------------------------------------
# emit_tasks
# ---------------------------------------------------------------------------


class EmitTasksTest(unittest.TestCase):

    def _bundle(self) -> emit.TaskItemBundle:
        with TemporaryDirectory() as td:
            tmp = Path(td)
            change_dir = _make_change(tmp)
            handoff = tmp / "HANDOFF.md"
            handoff.write_text(HANDOFF_MD, encoding="utf-8")
            return emit.build_task_bodies(
                change_dir=change_dir,
                change_slug="2026-01-01-foo",
                handoff_path=handoff,
            )

    def test_emits_three_stages_per_item(self):
        bundle = self._bundle()
        runner = FakeRunner()
        result = emit.emit_tasks(
            bundle=bundle, tenant="foo", workspace="worktree", runner=runner,
        )
        # 3 items * 3 stages = 9 keys.
        self.assertEqual(len(result.ids_by_key), 9)

    def test_uses_worktree_workspace_flag(self):
        bundle = self._bundle()
        runner = FakeRunner()
        emit.emit_tasks(
            bundle=bundle, tenant="foo", workspace="worktree", runner=runner,
        )
        creates = [c for c in runner.calls if "create" in c]
        self.assertEqual(len(creates), 9)
        for argv in creates:
            self.assertEqual(_argv_value(argv, "--workspace"), "worktree")

    def test_assignees_are_implementer_reviewer_integrator(self):
        bundle = self._bundle()
        runner = FakeRunner()
        emit.emit_tasks(
            bundle=bundle, tenant="foo", workspace="worktree", runner=runner,
        )
        creates = [c for c in runner.calls if "create" in c]
        # Stages should rotate impl→review→integrate per item.
        expected = ["scientia-implementer", "scientia-reviewer", "scientia-integrator"] * 3
        actual = [_argv_value(c, "--assignee") for c in creates]
        self.assertEqual(actual, expected)

    def test_review_depends_on_impl_and_integrate_on_review(self):
        bundle = self._bundle()
        runner = FakeRunner()
        emit.emit_tasks(
            bundle=bundle, tenant="foo", workspace="worktree", runner=runner,
        )
        creates = [c for c in runner.calls if "create" in c]
        # Within each item's pipeline, review --parent = impl id; integrate --parent = review id.
        for item_idx in range(3):
            impl = creates[item_idx * 3]
            review = creates[item_idx * 3 + 1]
            integrate = creates[item_idx * 3 + 2]
            impl_id = f"t_{(item_idx * 3) + 1:02d}"
            review_id = f"t_{(item_idx * 3) + 2:02d}"
            self.assertIn(impl_id, _argv_all(review, "--parent"))
            self.assertIn(review_id, _argv_all(integrate, "--parent"))

    def test_impl_depends_on_previous_item_integrate(self):
        bundle = self._bundle()
        runner = FakeRunner()
        emit.emit_tasks(
            bundle=bundle, tenant="foo", workspace="worktree", runner=runner,
        )
        creates = [c for c in runner.calls if "create" in c]
        # Item #2 depends on #1 → its impl should have #1's integrate id as --parent.
        item1_integrate_id = "t_03"  # third created task
        item2_impl_argv = creates[3]
        self.assertIn(item1_integrate_id, _argv_all(item2_impl_argv, "--parent"))

        # Item #3 depends on #2 → its impl should have #2's integrate (t_06).
        item3_impl_argv = creates[6]
        self.assertIn("t_06", _argv_all(item3_impl_argv, "--parent"))
        # Item #3 does NOT directly depend on #1, so #1's integrate must NOT be
        # listed as --parent on #3's impl (the closure happens elsewhere).
        self.assertNotIn("t_03", _argv_all(item3_impl_argv, "--parent"))

    def test_records_have_tasks_md_number(self):
        bundle = self._bundle()
        runner = FakeRunner()
        result = emit.emit_tasks(
            bundle=bundle, tenant="foo", workspace="worktree", runner=runner,
        )
        nums = sorted({r.tasks_md_number for r in result.records})
        self.assertEqual(nums, [1, 2, 3])
        for r in result.records:
            self.assertEqual(r.role, "task-item")


# ---------------------------------------------------------------------------
# _scenario_prereq_map
# ---------------------------------------------------------------------------


class ScenarioPrereqMapTest(unittest.TestCase):

    def test_maps_scenario_to_closure_integrate_ids(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            change_dir = _make_change(tmp)
            handoff = tmp / "HANDOFF.md"
            handoff.write_text(HANDOFF_MD, encoding="utf-8")
            bundle = emit.build_task_bodies(
                change_dir=change_dir,
                change_slug="2026-01-01-foo",
                handoff_path=handoff,
            )
            runner = FakeRunner()
            result = emit.emit_tasks(
                bundle=bundle, tenant="foo", workspace="worktree", runner=runner,
            )
            prereqs = emit._scenario_prereq_map(
                items=bundle.items, ids_by_key=result.ids_by_key,
            )

            # Only one scenario referenced: cap-a#scn-1.
            self.assertIn(("cap-a", "scn-1"), prereqs)
            ids = prereqs[("cap-a", "scn-1")]

            # Should include universal #1 (no @spec, not non-behavioral) and
            # the transitive closure for the scenario (#3, #2 are in the chain,
            # but #2 is also universal).
            # Specifically: integrate of #1, #2, #3 should all appear.
            integrate_t_03 = result.ids_by_key[
                f"{bundle.items[0].idempotency_key}:integrate"
            ]
            integrate_t_06 = result.ids_by_key[
                f"{bundle.items[1].idempotency_key}:integrate"
            ]
            integrate_t_09 = result.ids_by_key[
                f"{bundle.items[2].idempotency_key}:integrate"
            ]
            self.assertIn(integrate_t_03, ids)
            self.assertIn(integrate_t_06, ids)
            self.assertIn(integrate_t_09, ids)
            # Dedup: no id should appear twice.
            self.assertEqual(len(ids), len(set(ids)))


# ---------------------------------------------------------------------------
# emit_one with task_prereqs_by_scenario
# ---------------------------------------------------------------------------


class EmitOneWithTaskPrereqsTest(unittest.TestCase):

    def _bundle_with_child(self, scenario_slug: str) -> emit.BodyBundle:
        parent = emit.TaskBody(
            title="[cap] cap — spec",
            body_markdown="parent body",
            idempotency_key="cap:ADR-0001:PHASH",
            assignee="scientia-implementer",
        )
        aggregator = emit.TaskBody(
            title="[cap] aggregator",
            body_markdown="agg body",
            idempotency_key="cap:ADR-0001:PHASH:aggregator",
            assignee="scientia-aggregator",
        )
        child = emit.TaskBody(
            title="[cap] X",
            body_markdown="child body",
            idempotency_key=f"cap:ADR-0001:{scenario_slug}:CHILDHASH",
            assignee="scientia-implementer",
            scenario_slug=scenario_slug,
        )
        return emit.BodyBundle(parent=parent, aggregator=aggregator, children=[child])

    def test_impl_stage_gets_extra_parents(self):
        bundle = self._bundle_with_child("scn-1")
        runner = FakeRunner()
        # Use prereq ids with a distinct prefix so they don't collide with
        # FakeRunner's sequential `t_NN` ids for the same-call creates.
        prereq_a = "prereq_aaa"
        prereq_b = "prereq_bbb"
        emit.emit_one(
            bundle=bundle,
            pattern="P2-pipeline",
            tenant="foo",
            workspace="dir:/abs",
            runner=runner,
            task_prereqs_by_scenario={"scn-1": [prereq_a, prereq_b]},
        )
        creates = [c for c in runner.calls if "create" in c]
        # Order: parent, impl, review, integrate, aggregator
        impl_argv = creates[1]
        review_argv = creates[2]
        integrate_argv = creates[3]

        impl_parents = _argv_all(impl_argv, "--parent")
        # impl --parent: spec parent task id (t_01) + extra prereqs.
        self.assertIn("t_01", impl_parents)
        self.assertIn(prereq_a, impl_parents)
        self.assertIn(prereq_b, impl_parents)

        # review and integrate should only chain to the previous stage —
        # NOT carry the extra prereqs (those gate only impl).
        review_parents = _argv_all(review_argv, "--parent")
        integrate_parents = _argv_all(integrate_argv, "--parent")
        self.assertNotIn(prereq_a, review_parents)
        self.assertNotIn(prereq_b, review_parents)
        self.assertNotIn(prereq_a, integrate_parents)
        self.assertNotIn(prereq_b, integrate_parents)

    def test_no_extra_parents_when_scenario_not_in_map(self):
        bundle = self._bundle_with_child("other-scenario")
        runner = FakeRunner()
        emit.emit_one(
            bundle=bundle,
            pattern="P2-pipeline",
            tenant="foo",
            workspace="dir:/abs",
            runner=runner,
            task_prereqs_by_scenario={"scn-1": ["prereq_xyz"]},
        )
        creates = [c for c in runner.calls if "create" in c]
        impl_argv = creates[1]
        impl_parents = _argv_all(impl_argv, "--parent")
        self.assertNotIn("prereq_xyz", impl_parents)

    def test_back_compat_without_map(self):
        bundle = self._bundle_with_child("scn")
        runner = FakeRunner()
        # Omit task_prereqs_by_scenario entirely — existing callers shouldn't break.
        emit.emit_one(
            bundle=bundle,
            pattern="P2-pipeline",
            tenant="foo",
            workspace="dir:/abs",
            runner=runner,
        )
        creates = [c for c in runner.calls if "create" in c]
        # Same 5 creates as before; impl should only have the parent task id.
        impl_argv = creates[1]
        self.assertEqual(_argv_all(impl_argv, "--parent"), ["t_01"])


if __name__ == "__main__":
    unittest.main()
