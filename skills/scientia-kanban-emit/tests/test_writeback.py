"""Tests for the post-emit writebacks:

1. ## Kanban Tasks section in each spec.md (round-trips through
   KANBAN_SECTION_RE from idempotency_key.py).
2. Per-task index file at development/tasks/<tenant>/<change-id>/<id>.md.
3. development/log.md line for the `emitted` event.
"""

import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import _paths  # noqa: F401

import emit


SPEC_BEFORE_FIRST_EMIT = """---
title: "Spec: My Capability"
capability: my-capability
---

# Capability: My Capability

A short description.

## Acceptance Criteria

- One.

## Scenarios

### Scenario: Foo
```gherkin
Given Foo
```
"""


SPEC_WITH_OLD_KANBAN_SECTION = SPEC_BEFORE_FIRST_EMIT + """
## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->

- **Parent** — `t_old_parent` — `cap:ADR-0001:OLDHASH`
- **Aggregator** — `t_old_agg` — `cap:ADR-0001:OLDHASH:aggregator`
"""


def _principals():
    """Return the {role -> (task_id, idempotency_key, scenario_slug or None)} map
    that write_kanban_section expects."""
    return {
        "parent": {"task_id": "t_01", "idempotency_key": "cap:ADR-0001:HASH",
                   "scenario_slug": None},
        "aggregator": {"task_id": "t_99",
                       "idempotency_key": "cap:ADR-0001:HASH:aggregator",
                       "scenario_slug": None},
        "children": [
            {"task_id": "t_02", "idempotency_key": "cap:ADR-0001:foo:HF",
             "scenario_slug": "foo"},
            {"task_id": "t_03", "idempotency_key": "cap:ADR-0001:bar:HB",
             "scenario_slug": "bar"},
        ],
    }


class WriteKanbanSectionTests(unittest.TestCase):
    def test_appends_section_when_spec_has_none(self):
        with TemporaryDirectory() as td:
            spec = Path(td) / "spec.md"
            spec.write_text(SPEC_BEFORE_FIRST_EMIT)
            emit.write_kanban_section(spec, principals=_principals())
            text = spec.read_text()
            self.assertIn("## Kanban Tasks", text)
            self.assertIn("**Parent**", text)
            self.assertIn("`t_01`", text)
            self.assertIn("**Aggregator**", text)
            self.assertIn("`t_99`", text)
            self.assertIn("**Child: foo**", text)
            self.assertIn("`t_02`", text)
            self.assertIn("**Child: bar**", text)
            self.assertIn("`t_03`", text)

    def test_replaces_existing_section_in_place(self):
        with TemporaryDirectory() as td:
            spec = Path(td) / "spec.md"
            spec.write_text(SPEC_WITH_OLD_KANBAN_SECTION)
            emit.write_kanban_section(spec, principals=_principals())
            text = spec.read_text()
            # Old ids are gone
            self.assertNotIn("t_old_parent", text)
            self.assertNotIn("t_old_agg", text)
            # New ids are present
            self.assertIn("t_01", text)
            self.assertIn("t_99", text)

    def test_section_round_trips_through_idempotency_key_re(self):
        """The KANBAN_SECTION_RE in idempotency_key.py must exclude the new
        section from the hash. Otherwise we get infinite-emit loops."""
        from idempotency_key import KANBAN_SECTION_RE, strip_for_hash

        with TemporaryDirectory() as td:
            spec = Path(td) / "spec.md"
            spec.write_text(SPEC_BEFORE_FIRST_EMIT)
            before = strip_for_hash(spec.read_text())
            emit.write_kanban_section(spec, principals=_principals())
            after = strip_for_hash(spec.read_text())
            self.assertEqual(before, after,
                "Hashing input changed after writeback — KANBAN_SECTION_RE "
                "didn't strip the new section, causing a future re-emit "
                "to compute new keys for unchanged content.")

    def test_section_starts_with_canonical_comment_sigil(self):
        with TemporaryDirectory() as td:
            spec = Path(td) / "spec.md"
            spec.write_text(SPEC_BEFORE_FIRST_EMIT)
            emit.write_kanban_section(spec, principals=_principals())
            text = spec.read_text()
            self.assertIn(
                "<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->",
                text,
            )


class WriteIndexEntryTests(unittest.TestCase):
    def test_writes_file_at_canonical_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            emit.write_index_entry(
                repo_root=root,
                tenant="ansible",
                change_id="2026-05-20-test",
                capability="my-capability",
                task_id="t_42",
                idempotency_key="my-capability:ADR-0001:HASH",
                role="child",
                scenario_slug="foo",
                parent_task_id="t_01",
                spec_rel_path="openspec/changes/ansible-2026-05-20-test/specs/my-capability/spec.md",
                title="Foo scenario",
                assignee="scientia-implementer",
            )
            expected = (root / "development" / "tasks" / "ansible"
                        / "2026-05-20-test" / "t_42.md")
            self.assertTrue(expected.is_file())

    def test_frontmatter_carries_all_required_fields(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            emit.write_index_entry(
                repo_root=root,
                tenant="ansible",
                change_id="2026-05-20-test",
                capability="my-capability",
                task_id="t_42",
                idempotency_key="my-capability:ADR-0001:HASH",
                role="child",
                scenario_slug="foo",
                parent_task_id="t_01",
                spec_rel_path="openspec/changes/x/specs/m/spec.md",
                title="Foo",
                assignee="scientia-implementer",
            )
            text = (root / "development" / "tasks" / "ansible"
                    / "2026-05-20-test" / "t_42.md").read_text()
            for required in (
                "task_id: t_42",
                "type: kanban-index",
                "tenant: ansible",
                "change_id: 2026-05-20-test",
                "capability: my-capability",
                "role: child",
                "scenario: foo",
                "idempotency_key: my-capability:ADR-0001:HASH",
                "spec_path: openspec/changes/x/specs/m/spec.md",
                "parent_task: t_01",
            ):
                self.assertIn(required, text)

    def test_parent_role_has_no_scenario_field(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            emit.write_index_entry(
                repo_root=root,
                tenant="t",
                change_id="c",
                capability="cap",
                task_id="t_01",
                idempotency_key="cap:ADR-0001:H",
                role="parent",
                scenario_slug=None,
                parent_task_id=None,
                spec_rel_path="path/to/spec.md",
                title="cap — spec",
                assignee="scientia-implementer",
            )
            text = (root / "development" / "tasks" / "t" / "c" / "t_01.md").read_text()
            # `scenario:` line shouldn't appear; `parent_task:` shouldn't either
            self.assertNotRegex(text, r"^scenario:\s", )
            self.assertNotRegex(text, r"^parent_task:\s")


class AppendLogTests(unittest.TestCase):
    def test_appends_new_line_when_log_missing(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            emit.append_log_emitted(
                repo_root=root,
                tenant="ansible",
                change_id="2026-05-20-test",
                pattern="P2-pipeline",
                tasks=9,
            )
            log = (root / "development" / "log.md").read_text()
            self.assertIn("scientia-kanban-emit", log)
            self.assertIn("emitted", log)
            self.assertIn("ansible/2026-05-20-test", log)
            self.assertIn("pattern=P2-pipeline", log)
            self.assertIn("tasks=9", log)

    def test_line_format_matches_scientia_convention(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "development").mkdir()
            (root / "development" / "log.md").write_text(
                "# Development Log\n\n<!-- entries -->\n"
            )
            emit.append_log_emitted(
                repo_root=root,
                tenant="ansible",
                change_id="2026-05-20-test",
                pattern="P2-pipeline",
                tasks=9,
            )
            last = (root / "development" / "log.md").read_text().splitlines()[-1]
            # - <ISO8601Z> — scientia-kanban-emit — emitted — <tenant>/<change_id> — pattern=<p> tasks=<n>
            self.assertRegex(
                last,
                r"^- \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z — scientia-kanban-emit — emitted — "
                r"ansible/2026-05-20-test — pattern=P2-pipeline tasks=9$",
            )


if __name__ == "__main__":
    unittest.main()
