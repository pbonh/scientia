"""Tests for jobhunt_emit.py spec building, parsing, and emission."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from tests import _paths  # noqa: F401

import jobhunt_emit as je


BRIEF = """---
type: jobhunt-brief
campaign_id: c1
wiki_snapshot: (no-git)
provider: cdp
---

## 4 — Search Plan
- board=`linkedin` query="Senior Rust Engineer"
- board=`greenhouse` query="Staff Backend Engineer"
"""

POSTING = """---
title: "Senior Rust Engineer @ Acme"
type: jobhunt-posting
company: "[[jobhunt/companies/acme]]"
posting_url: "https://acme.example/jobs/123"
role: "Senior Rust Engineer"
---

## Summary
"""


def make_repo(tmp: Path) -> Path:
    (tmp / "development" / "job-hunt" / "briefs" / "c1").mkdir(parents=True)
    (tmp / "development" / "job-hunt" / "briefs" / "c1" / "brief.md").write_text(
        BRIEF, encoding="utf-8")
    (tmp / "wiki" / "jobhunt" / "postings").mkdir(parents=True)
    (tmp / "wiki" / "jobhunt" / "postings" / "acme-rust.md").write_text(
        POSTING, encoding="utf-8")
    return tmp


class TestParsing(unittest.TestCase):
    def test_read_brief_search_plan(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            fm, plan = je.read_brief(repo, "c1")
            self.assertEqual(fm["campaign_id"], "c1")
            self.assertEqual(plan, [
                ("linkedin", "Senior Rust Engineer"),
                ("greenhouse", "Staff Backend Engineer"),
            ])

    def test_postings_parse(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            postings = je._postings(repo)
            self.assertIn("acme-rust", postings)
            self.assertEqual(postings["acme-rust"]["company"], "acme")
            self.assertEqual(postings["acme-rust"]["url"],
                             "https://acme.example/jobs/123")


class TestSearchSpecs(unittest.TestCase):
    def test_one_per_board_role(self):
        specs = je.build_search_specs("c1", [("linkedin", "Rust Eng")], "http://x")
        self.assertEqual(len(specs), 1)
        s = specs[0]
        self.assertEqual(s.kind, "search")
        self.assertTrue(s.key.startswith("jobhunt-search:c1:linkedin:"))
        self.assertFalse(s.triage)
        self.assertIn("http://x", s.body)


class TestApplySpecs(unittest.TestCase):
    def test_chain_shape_and_gate(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            specs = je.build_apply_specs(repo, "c1", "http://cdp", {"acme-rust"})
            kinds = [s.kind for s in specs]
            self.assertEqual(kinds, ["author", "form-fill", "submit"])
            author, formfill, submit = specs
            # form-fill is the gated (triage) task, parented to author.
            self.assertTrue(formfill.triage)
            self.assertEqual(formfill.parents, [author.key])
            self.assertIn("DO NOT SUBMIT", formfill.body)
            # submit parented to form-fill, NOT triaged.
            self.assertFalse(submit.triage)
            self.assertEqual(submit.parents, [formfill.key])
            # shared url sha across the chain
            shas = {s.key.rsplit(":", 1)[1] for s in specs}
            self.assertEqual(len(shas), 1)

    def test_unknown_posting_raises(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            with self.assertRaises(ValueError):
                je.build_apply_specs(repo, "c1", "http://cdp", {"ghost"})

    def test_apply_all_covers_all(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            specs = je.build_apply_specs(repo, "c1", "http://cdp", None)
            self.assertEqual(len(specs), 3)  # one chain for the one posting


class TestEmit(unittest.TestCase):
    def test_emit_resolves_parents_and_writes_index(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            specs = je.build_apply_specs(repo, "c1", "http://cdp", {"acme-rust"})

            created = []
            counter = {"n": 0}

            def runner(argv, **kw):
                counter["n"] += 1
                tid = f"t_{counter['n']:02d}"
                created.append(argv)
                return SimpleNamespace(returncode=0, stdout=f'{{"id": "{tid}"}}',
                                       stderr="")

            key_to_id = je.emit_specs(repo, "c1", specs, dry_run=False, runner=runner)
            self.assertEqual(len(key_to_id), 3)
            # The form-fill create call must carry --parent <author id>.
            formfill_call = created[1]
            self.assertIn("--parent", formfill_call)
            self.assertIn(key_to_id[specs[0].key], formfill_call)
            self.assertIn("--triage", formfill_call)
            # The submit create call must carry --parent <formfill id> and NO --triage.
            submit_call = created[2]
            self.assertIn(key_to_id[specs[1].key], submit_call)
            self.assertNotIn("--triage", submit_call)
            # Index files written.
            idx = repo / "development" / "job-hunt" / "tasks" / "c1"
            self.assertEqual(len(list(idx.glob("*.md"))), 3)

    def test_dry_run_creates_no_index(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            specs = je.build_search_specs("c1", [("linkedin", "x")], "http://cdp")
            je.emit_specs(repo, "c1", specs, dry_run=True)
            idx = repo / "development" / "job-hunt" / "tasks" / "c1"
            self.assertFalse(idx.exists())


if __name__ == "__main__":
    unittest.main()
