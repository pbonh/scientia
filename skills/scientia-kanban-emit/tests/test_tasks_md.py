"""Tests for tasks_md.py — parser, topological sort, and prereq helpers."""

import unittest

from tests import _paths  # noqa: F401

import tasks_md


TASKS_MD_SAMPLE = """---
title: "Tasks: foo"
tenant: foo-bar
change_id: 2026-01-01-foo
---

# Implementation Plan

## Workspace & Shared Infrastructure

- [ ] **1.** Set up shared workspace — non-behavioral
- [ ] **2.** Define shared types module — @adr: ADR-0001 (depends on #1)
- [ ] **3.** Implement core data structure — @spec: cap-a#scn-1 (depends on #2)

## Capability: cap-a

- [ ] **4.** Implement first pass — @spec: cap-a#scn-1 (depends on #3)
- [ ] **5.** Implement driver — @spec: cap-a#scn-2 @spec: cap-a#scn-1 (depends on #4)

## Capability: cap-b

- [ ] **6.** Integrate solver backend — @adr: ADR-0002 (depends on #4)
- [ ] **7.** Implement control loop — @spec: cap-b#scn-3 (depends on #6, #5)

## Cross-Cutting: Docs

- [x] **8.** Write crate-level docs — non-behavioral (depends on #5, #7)
"""


class ParseTasksMdTest(unittest.TestCase):

    def test_returns_one_item_per_bullet(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        self.assertEqual(len(items), 8)
        self.assertEqual([i.number for i in items], [1, 2, 3, 4, 5, 6, 7, 8])

    def test_extracts_title_without_markers(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertNotIn("@spec", by_num[3].title)
        self.assertNotIn("@adr", by_num[2].title)
        self.assertNotIn("depends on", by_num[2].title)
        self.assertIn("Define shared types module", by_num[2].title)

    def test_spec_refs(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(by_num[5].spec_refs, [
            tasks_md.SpecRef("cap-a", "scn-2"),
            tasks_md.SpecRef("cap-a", "scn-1"),
        ])
        self.assertEqual(by_num[1].spec_refs, [])

    def test_adr_refs(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(by_num[2].adr_refs, ["ADR-0001"])
        self.assertEqual(by_num[6].adr_refs, ["ADR-0002"])
        self.assertEqual(by_num[3].adr_refs, [])

    def test_depends_on(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(by_num[1].depends_on, [])
        self.assertEqual(by_num[2].depends_on, [1])
        self.assertEqual(by_num[7].depends_on, [6, 5])

    def test_non_behavioral_flag(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertTrue(by_num[1].non_behavioral)
        self.assertTrue(by_num[8].non_behavioral)
        self.assertFalse(by_num[5].non_behavioral)

    def test_section_capture(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(by_num[1].section, "Workspace & Shared Infrastructure")
        self.assertEqual(by_num[4].section, "Capability: cap-a")
        self.assertEqual(by_num[7].section, "Capability: cap-b")

    def test_checked(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertFalse(by_num[1].checked)
        self.assertTrue(by_num[8].checked)

    def test_slug_zero_padded(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        self.assertEqual(items[0].slug, "task-01")
        self.assertEqual(items[-1].slug, "task-08")

    def test_hash_stable_across_unrelated_changes(self):
        items_a = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        # Mutate an unrelated bullet; item #1's hash should not change.
        text_b = TASKS_MD_SAMPLE.replace(
            "Implement control loop", "Implement control loop (rev2)"
        )
        items_b = tasks_md.parse_tasks_md(text_b)
        by_a = {i.number: i for i in items_a}
        by_b = {i.number: i for i in items_b}
        self.assertEqual(by_a[1].hash(), by_b[1].hash())
        self.assertNotEqual(by_a[7].hash(), by_b[7].hash())


class TopologicalOrderTest(unittest.TestCase):

    def test_preserves_dependency_order(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        ordered = tasks_md.topological_order(items)
        position = {item.number: i for i, item in enumerate(ordered)}
        # Every depends_on parent must come before its child.
        for item in ordered:
            for dep in item.depends_on:
                self.assertLess(position[dep], position[item.number],
                                f"#{dep} should come before #{item.number}")

    def test_stable_tie_breaking_by_number(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        ordered = tasks_md.topological_order(items)
        # #1 has no deps, so it should be first.
        self.assertEqual(ordered[0].number, 1)

    def test_detects_cycle(self):
        cyclic = """- [ ] **1.** A — @adr: ADR-0001 (depends on #2)
- [ ] **2.** B — @adr: ADR-0001 (depends on #1)
"""
        items = tasks_md.parse_tasks_md(cyclic)
        with self.assertRaises(ValueError) as cm:
            tasks_md.topological_order(items)
        self.assertIn("cycle", str(cm.exception).lower())

    def test_dangling_depends_on_is_ignored(self):
        text = """- [ ] **1.** A — @adr: ADR-0001 (depends on #99)
- [ ] **2.** B — @adr: ADR-0001 (depends on #1)
"""
        items = tasks_md.parse_tasks_md(text)
        ordered = tasks_md.topological_order(items)
        # #99 doesn't exist so #1 should have effective in-degree 0.
        self.assertEqual([i.number for i in ordered], [1, 2])


class SharedInfrastructureTest(unittest.TestCase):

    def test_returns_items_without_spec_marker(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        infra = tasks_md.shared_infrastructure(items)
        nums = sorted(i.number for i in infra)
        # #1 (no markers), #2 (@adr only), #6 (@adr only), #8 (docs, non-behavioral).
        # All four have no @spec, so all four are returned by the bare helper.
        # The emit-side filter excludes non-behavioral items separately.
        self.assertEqual(nums, [1, 2, 6, 8])


class ItemsForScenarioTest(unittest.TestCase):

    def test_includes_transitive_closure(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        # cap-a#scn-1 is seeded by #3, #4, #5.
        # Closure includes #3, #4, #5 (seeds) + #2 (dep of #3) + #1 (dep of #2).
        closure = tasks_md.items_for_scenario(items, "cap-a", "scn-1")
        nums = sorted(i.number for i in closure)
        self.assertEqual(nums, [1, 2, 3, 4, 5])

    def test_empty_when_no_match(self):
        items = tasks_md.parse_tasks_md(TASKS_MD_SAMPLE)
        self.assertEqual(
            tasks_md.items_for_scenario(items, "nonexistent", "scenario"),
            [],
        )


USES_SHARED_AND_TOUCHES_SAMPLE = """---
title: "Tasks: bar"
---

# Implementation Plan

- [ ] **1.** Define SharedThing — @adr: ADR-0005
- [ ] **2.** First consumer — @spec: cap-a#scn-1 @uses-shared:pkg/foo.rs::SharedThing @touches:pkg/foo_a.rs
- [ ] **3.** Second consumer — @spec: cap-b#scn-1 @uses-shared:pkg/foo.rs::SharedThing @uses-shared:pkg/lib.rs::SharedOther @touches:pkg/foo_b.rs,pkg/lib.rs (depends on #1)
- [ ] **4.** Touch the same files — @spec: cap-b#scn-2 @touches:pkg/foo_b.rs (depends on #1)
"""


class UsesSharedMarkerTest(unittest.TestCase):

    def test_parses_single_uses_shared(self):
        items = tasks_md.parse_tasks_md(USES_SHARED_AND_TOUCHES_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(
            by_num[2].uses_shared,
            ["pkg/foo.rs::SharedThing"],
        )

    def test_parses_multiple_uses_shared(self):
        items = tasks_md.parse_tasks_md(USES_SHARED_AND_TOUCHES_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(sorted(by_num[3].uses_shared), [
            "pkg/foo.rs::SharedThing",
            "pkg/lib.rs::SharedOther",
        ])

    def test_uses_shared_does_not_leak_into_title(self):
        items = tasks_md.parse_tasks_md(USES_SHARED_AND_TOUCHES_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertNotIn("@uses-shared", by_num[2].title)
        self.assertNotIn("@touches", by_num[2].title)


class TouchesMarkerTest(unittest.TestCase):

    def test_parses_single_touch(self):
        items = tasks_md.parse_tasks_md(USES_SHARED_AND_TOUCHES_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(
            by_num[2].touches,
            ["pkg/foo_a.rs"],
        )

    def test_parses_comma_separated_touches(self):
        items = tasks_md.parse_tasks_md(USES_SHARED_AND_TOUCHES_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(sorted(by_num[3].touches), [
            "pkg/foo_b.rs",
            "pkg/lib.rs",
        ])

    def test_absent_marker_is_empty(self):
        items = tasks_md.parse_tasks_md(USES_SHARED_AND_TOUCHES_SAMPLE)
        by_num = {i.number: i for i in items}
        self.assertEqual(by_num[1].touches, [])


class WaveOrderingTest(unittest.TestCase):

    def test_disjoint_touches_share_wave_zero(self):
        items = tasks_md.parse_tasks_md(USES_SHARED_AND_TOUCHES_SAMPLE)
        # Strip depends_on so we test wave logic in isolation from topo order.
        items = [
            tasks_md.TaskItem(number=i.number, title=i.title, section="",
                              touches=i.touches, raw_line=i.raw_line)
            for i in items
        ]
        waves = tasks_md.wave_topological_order(items, max_parallel_per_file_group=2)
        wave_of = {item.number: w for w, item in waves}
        # #1 has no @touches (no constraint), #2 has pkg/foo_a.rs only
        # — both should sit in wave 0.
        self.assertEqual(wave_of[1], 0)
        self.assertEqual(wave_of[2], 0)

    def test_overflow_pushes_to_next_wave(self):
        # Three items all touching the same file with max_parallel=2
        # → 2 in wave 0, 1 in wave 1.
        items = [
            tasks_md.TaskItem(number=1, title="a", section="",
                              touches=["src/x.rs"], raw_line="- [ ] **1.** a @touches:src/x.rs"),
            tasks_md.TaskItem(number=2, title="b", section="",
                              touches=["src/x.rs"], raw_line="- [ ] **2.** b @touches:src/x.rs"),
            tasks_md.TaskItem(number=3, title="c", section="",
                              touches=["src/x.rs"], raw_line="- [ ] **3.** c @touches:src/x.rs"),
        ]
        waves = tasks_md.wave_topological_order(items, max_parallel_per_file_group=2)
        wave_of = {item.number: w for w, item in waves}
        self.assertEqual(wave_of[1], 0)
        self.assertEqual(wave_of[2], 0)
        self.assertEqual(wave_of[3], 1)

    def test_disjoint_files_parallel_under_overflow(self):
        # Three items, two share src/a.rs, one is on src/b.rs.
        # With max_parallel=2: #1, #2 share wave 0 (src/a.rs slots 1/2);
        # #3 (src/b.rs) also fits in wave 0.
        items = [
            tasks_md.TaskItem(number=1, title="a", section="",
                              touches=["src/a.rs"], raw_line="- [ ] **1.**"),
            tasks_md.TaskItem(number=2, title="b", section="",
                              touches=["src/a.rs"], raw_line="- [ ] **2.**"),
            tasks_md.TaskItem(number=3, title="c", section="",
                              touches=["src/b.rs"], raw_line="- [ ] **3.**"),
        ]
        waves = tasks_md.wave_topological_order(items, max_parallel_per_file_group=2)
        wave_of = {item.number: w for w, item in waves}
        self.assertEqual(wave_of[1], 0)
        self.assertEqual(wave_of[2], 0)
        self.assertEqual(wave_of[3], 0)

    def test_max_one_forces_serial(self):
        items = [
            tasks_md.TaskItem(number=1, title="a", section="",
                              touches=["src/x.rs"], raw_line="- [ ] **1.**"),
            tasks_md.TaskItem(number=2, title="b", section="",
                              touches=["src/x.rs"], raw_line="- [ ] **2.**"),
            tasks_md.TaskItem(number=3, title="c", section="",
                              touches=["src/x.rs"], raw_line="- [ ] **3.**"),
        ]
        waves = tasks_md.wave_topological_order(items, max_parallel_per_file_group=1)
        wave_of = {item.number: w for w, item in waves}
        self.assertEqual(wave_of[1], 0)
        self.assertEqual(wave_of[2], 1)
        self.assertEqual(wave_of[3], 2)

    def test_depends_on_lower_bound_respected(self):
        # #2 depends on #1 — even if both touch disjoint files, #2 must be in
        # a later wave.
        items = [
            tasks_md.TaskItem(number=1, title="a", section="",
                              touches=["src/a.rs"], raw_line="- [ ] **1.**"),
            tasks_md.TaskItem(number=2, title="b", section="",
                              touches=["src/b.rs"], depends_on=[1],
                              raw_line="- [ ] **2.**"),
        ]
        waves = tasks_md.wave_topological_order(items)
        wave_of = {item.number: w for w, item in waves}
        self.assertEqual(wave_of[1], 0)
        self.assertEqual(wave_of[2], 1)

    def test_no_touches_means_no_file_conflict(self):
        items = [
            tasks_md.TaskItem(number=1, title="a", section="", raw_line="- [ ] **1.**"),
            tasks_md.TaskItem(number=2, title="b", section="", raw_line="- [ ] **2.**"),
            tasks_md.TaskItem(number=3, title="c", section="", raw_line="- [ ] **3.**"),
        ]
        waves = tasks_md.wave_topological_order(items, max_parallel_per_file_group=1)
        # No @touches means no file-group counter, so all share wave 0.
        for _, item in waves:
            self.assertEqual(0, [w for w, i in waves if i.number == item.number][0])


if __name__ == "__main__":
    unittest.main()
