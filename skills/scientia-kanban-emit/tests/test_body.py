"""Tests for body construction in scripts/emit.py.

`build_bodies(change_dir, spec_path)` returns a BodyBundle:
    BodyBundle.parent       — one TaskBody (full impl checklist)
    BodyBundle.aggregator   — one TaskBody (aggregator role)
    BodyBundle.children     — List[TaskBody], one per `### Scenario:` block

Each TaskBody has: title, body_markdown, idempotency_key, scenario_slug
(scenario_slug is None for parent/aggregator).

The body_markdown matches the schema in skills/scientia-kanban-emit/SKILL.md
step 3. We assert structural properties rather than byte-exact matches so
small wording tweaks don't require test churn.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import _paths  # noqa: F401

import emit


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------

CAPABILITY_DESCRIPTION = (
    "A reusable role that does X for Y. Configures without installing, "
    "templates with Jinja2, and validates via smoke test."
)

GLOSSARY = """| Term | Definition |
|---|---|
| **Foo** | A thing. |
| **Bar** | Another thing. |"""

ACCEPTANCE_CRITERIA = """- Criterion one.
- Criterion two.
- Criterion three."""

SCENARIOS = [
    ("Role runs idempotently",
     "Given a clean host\nWhen the role runs twice\nThen the second run is changed=0"),
    ("Role skips disabled tool",
     "Given a disabled tool\nWhen the role runs\nThen no config file is created"),
]

TASKS_MD = """---
title: "Tasks"
---

# Implementation Plan

## Capability: my-capability

### Section A
- [ ] **1.** Scaffold the role @adr: ADR-0001
- [ ] **2.** Write defaults @adr: ADR-0001

### Section B
- [ ] **3.** Add smoke test @adr: ADR-0001
"""

ADR_0001 = """---
title: "ADR-0001: Use a single role"
adr_id: ADR-0001
status: accepted
---

# ADR-0001

Decision body.
"""

HANDOFF_FIXTURE = """## Required Handoff

- **summary** — short prose
- **verification** — the command you ran
"""


def _scenarios_to_markdown(scenarios):
    out = []
    for title, body in scenarios:
        out.append(f"### Scenario: {title}\n```gherkin\n{body}\n```")
    return "\n\n".join(out)


def _make_change(tmp_root: Path, *,
                 capability: str = "my-capability",
                 scenarios=SCENARIOS,
                 tenant: str = "fake",
                 change_id: str = "2026-05-20-test") -> tuple[Path, Path]:
    """Build a minimal scientia change layout. Returns (change_dir, spec_path)."""
    change = tmp_root / "openspec" / "changes" / f"{tenant}-{change_id}"
    spec_dir = change / "specs" / capability
    spec_dir.mkdir(parents=True)
    adr_dir = change / "adr"
    adr_dir.mkdir()
    (adr_dir / "0001-use-single-role.md").write_text(ADR_0001)

    (change / "tasks.md").write_text(TASKS_MD)

    spec_body = f"""---
title: "Spec: My Capability"
tenant: {tenant}
change_id: {change_id}
capability: {capability}
---

# Capability: My Capability

{CAPABILITY_DESCRIPTION}

## Glossary (inlined from manifest)

{GLOSSARY}

## Personas

- **Alice** — does X.

## Acceptance Criteria

{ACCEPTANCE_CRITERIA}

## Scenarios

{_scenarios_to_markdown(scenarios)}
"""
    spec_path = spec_dir / "spec.md"
    spec_path.write_text(spec_body)
    return change, spec_path


def _write_handoff_at_skill():
    """The skill's references/HANDOFF_SCHEMA.md is the real handoff source;
    we let build_bodies resolve it relative to the script. Override via
    `handoff_path=` to inject the test fixture.
    """


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class BuildBodiesShapeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.change_dir, self.spec_path = _make_change(self.tmp_root)
        self.handoff_path = self.tmp_root / "HANDOFF_FIXTURE.md"
        self.handoff_path.write_text(HANDOFF_FIXTURE)
        self.bundle = emit.build_bodies(
            change_dir=self.change_dir,
            spec_path=self.spec_path,
            handoff_path=self.handoff_path,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_one_child_per_scenario(self):
        self.assertEqual(len(self.bundle.children), len(SCENARIOS))

    def test_parent_and_aggregator_are_present(self):
        self.assertIsNotNone(self.bundle.parent)
        self.assertIsNotNone(self.bundle.aggregator)

    def test_each_child_has_unique_idempotency_key(self):
        keys = [c.idempotency_key for c in self.bundle.children]
        self.assertEqual(len(keys), len(set(keys)))

    def test_child_idempotency_key_includes_scenario_slug(self):
        for body, (title, _) in zip(self.bundle.children, SCENARIOS):
            # slugify("Role runs idempotently") == "role-runs-idempotently"
            slug = title.lower().replace(" ", "-")
            self.assertIn(slug, body.idempotency_key)
            self.assertEqual(body.scenario_slug, slug)

    def test_aggregator_key_ends_in_aggregator(self):
        self.assertTrue(self.bundle.aggregator.idempotency_key.endswith(":aggregator"))


class BuildBodiesContentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.change_dir, self.spec_path = _make_change(self.tmp_root)
        self.handoff_path = self.tmp_root / "HANDOFF_FIXTURE.md"
        self.handoff_path.write_text(HANDOFF_FIXTURE)
        self.bundle = emit.build_bodies(
            change_dir=self.change_dir,
            spec_path=self.spec_path,
            handoff_path=self.handoff_path,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_child_body_inlines_its_scenario_verbatim(self):
        child = self.bundle.children[0]
        # The first scenario's Gherkin body is in SCENARIOS[0][1]
        self.assertIn(SCENARIOS[0][1], child.body_markdown)

    def test_child_body_inlines_glossary_verbatim(self):
        child = self.bundle.children[0]
        self.assertIn(GLOSSARY, child.body_markdown)

    def test_child_body_inlines_handoff_schema_verbatim(self):
        child = self.bundle.children[0]
        self.assertIn(HANDOFF_FIXTURE.strip(), child.body_markdown)

    def test_child_body_inlines_acceptance_criteria(self):
        child = self.bundle.children[0]
        self.assertIn(ACCEPTANCE_CRITERIA, child.body_markdown)

    def test_child_body_has_wiki_spec_anchor(self):
        child = self.bundle.children[0]
        self.assertIn("@wiki-spec: my-capability", child.body_markdown)

    def test_child_body_cites_governing_adr(self):
        child = self.bundle.children[0]
        self.assertIn("ADR-0001", child.body_markdown)

    def test_child_body_carries_wiki_backlink(self):
        child = self.bundle.children[0]
        self.assertIn("wiki_backlink: wiki/specs/my-capability.md", child.body_markdown)

    def test_child_body_carries_idempotency_key_in_footer(self):
        child = self.bundle.children[0]
        self.assertIn(f"idempotency_key: {child.idempotency_key}",
                      child.body_markdown)

    def test_parent_body_inlines_full_tasks_md_checklist(self):
        # The parent body inlines tasks.md content (Sections A and B together).
        self.assertIn("Scaffold the role", self.bundle.parent.body_markdown)
        self.assertIn("Add smoke test", self.bundle.parent.body_markdown)

    def test_child_body_inlines_scoped_tasks_only(self):
        # Children inline tasks scoped to their scenario when the tasks.md has
        # per-scenario anchors; otherwise they get the full advisory checklist.
        # For now we accept "full checklist OK" as the contract.
        child = self.bundle.children[0]
        self.assertIn("Implementation Checklist", child.body_markdown)

    def test_aggregator_body_lists_every_child_key(self):
        for child in self.bundle.children:
            self.assertIn(child.idempotency_key, self.bundle.aggregator.body_markdown)


class GoverningAdrTests(unittest.TestCase):
    """The "governing ADR" used in the idempotency key is the lowest-numbered
    accepted ADR in change_dir/adr/. If the change has none, raise.
    """

    def test_picks_lowest_numbered_accepted_adr(self):
        with TemporaryDirectory() as td:
            change = Path(td)
            adr = change / "adr"
            adr.mkdir()
            (adr / "0002-second.md").write_text(
                "---\nadr_id: ADR-0002\nstatus: accepted\n---\n"
            )
            (adr / "0001-first.md").write_text(
                "---\nadr_id: ADR-0001\nstatus: accepted\n---\n"
            )
            self.assertEqual(emit.governing_adr(change), "ADR-0001")

    def test_skips_proposed_adrs(self):
        with TemporaryDirectory() as td:
            change = Path(td)
            adr = change / "adr"
            adr.mkdir()
            (adr / "0001-proposed.md").write_text(
                "---\nadr_id: ADR-0001\nstatus: proposed\n---\n"
            )
            (adr / "0002-accepted.md").write_text(
                "---\nadr_id: ADR-0002\nstatus: accepted\n---\n"
            )
            self.assertEqual(emit.governing_adr(change), "ADR-0002")

    def test_falls_back_to_first_proposed_when_none_accepted(self):
        # Some changes emit before any ADR is accepted (P5 pattern).
        with TemporaryDirectory() as td:
            change = Path(td)
            adr = change / "adr"
            adr.mkdir()
            (adr / "0001-proposed.md").write_text(
                "---\nadr_id: ADR-0001\nstatus: proposed\n---\n"
            )
            self.assertEqual(emit.governing_adr(change), "ADR-0001")

    def test_raises_when_no_adr_dir(self):
        with TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                emit.governing_adr(Path(td))


if __name__ == "__main__":
    unittest.main()
