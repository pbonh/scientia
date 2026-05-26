"""Tests for jobhunt_ingest.py — capture → wiki/jobhunt page upserts."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import _paths  # noqa: F401

import jobhunt_ingest as ji


def make_repo(tmp: Path) -> Path:
    (tmp / "wiki" / "jobhunt").mkdir(parents=True)
    (tmp / "wiki" / "index.md").write_text(
        "---\ntitle: Index\ntype: index\n---\n\n# Index\n\n## Concepts\n",
        encoding="utf-8")
    (tmp / "wiki" / "log.md").write_text("# log\n", encoding="utf-8")
    return tmp


def write_capture(repo: Path, campaign: str, name: str, obj: dict):
    d = repo / "development" / "job-hunt" / "captures" / campaign
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(obj), encoding="utf-8")


def read(repo: Path, rel: str) -> str:
    return (repo / rel).read_text(encoding="utf-8")


class TestSearch(unittest.TestCase):
    def test_creates_company_and_posting(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            write_capture(repo, "c1", "s.json", {
                "kind": "search", "board": "linkedin",
                "postings": [{"slug": "acme-rust", "company": "Acme",
                              "company_slug": "acme",
                              "url": "https://acme.example/123",
                              "role": "Senior Rust Engineer"}]})
            res = ji.ingest(repo, "c1")
            self.assertEqual(res["errors"], [])
            self.assertTrue((repo / "wiki/jobhunt/companies/acme.md").exists())
            posting = read(repo, "wiki/jobhunt/postings/acme-rust.md")
            self.assertIn("type: jobhunt-posting", posting)
            self.assertIn("company: \"[[jobhunt/companies/acme]]\"", posting)
            self.assertIn("posting_url: \"https://acme.example/123\"", posting)


class TestApplicationLifecycle(unittest.TestCase):
    def test_draft_then_applied_history(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            write_capture(repo, "c1", "app.json", {
                "kind": "application", "slug": "acme-rust",
                "company_slug": "acme", "posting_slug": "acme-rust",
                "status": "draft", "kanban_task_id": "t_ff01"})
            ji.ingest(repo, "c1")
            page = read(repo, "wiki/jobhunt/applications/acme-rust.md")
            self.assertIn("status: draft", page)
            self.assertIn("(none) → draft", page)

            # Now applied.
            write_capture(repo, "c1", "app.json", {
                "kind": "application", "slug": "acme-rust",
                "company_slug": "acme", "status": "applied",
                "applied_at": "2026-05-25T18:00:00Z", "note": "portal"})
            ji.ingest(repo, "c1")
            page = read(repo, "wiki/jobhunt/applications/acme-rust.md")
            self.assertIn("status: applied", page)
            self.assertIn("applied_at: 2026-05-25T18:00:00Z", page)
            self.assertIn("(none) → draft", page)
            self.assertIn("draft → applied", page)

    def test_illegal_transition_refused(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            write_capture(repo, "c1", "app.json", {
                "kind": "application", "slug": "x", "company_slug": "c",
                "status": "applied"})
            ji.ingest(repo, "c1")
            # Try to go applied -> draft (illegal).
            write_capture(repo, "c1", "app.json", {
                "kind": "application", "slug": "x", "company_slug": "c",
                "status": "draft"})
            res = ji.ingest(repo, "c1")
            self.assertTrue(any("illegal transition" in e for e in res["errors"]))
            page = read(repo, "wiki/jobhunt/applications/x.md")
            self.assertIn("status: applied", page)  # unchanged

    def test_idempotent_no_duplicate_history(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            cap = {"kind": "application", "slug": "x", "company_slug": "c",
                   "status": "applied", "applied_at": "2026-05-25T00:00:00Z"}
            write_capture(repo, "c1", "app.json", cap)
            ji.ingest(repo, "c1")
            ji.ingest(repo, "c1")  # second run, same capture
            page = read(repo, "wiki/jobhunt/applications/x.md")
            # draft->applied appears exactly once.
            self.assertEqual(page.count("draft → applied"), 1)


class TestInterviewContactAndIndex(unittest.TestCase):
    def test_interview_and_contact_pages(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            write_capture(repo, "c1", "iv.json", {
                "kind": "interview", "slug": "acme-tech",
                "application_slug": "acme-rust", "interview_type": "technical",
                "scheduled_at": "2026-06-02T17:00:00Z", "status": "scheduled"})
            write_capture(repo, "c1", "ct.json", {
                "kind": "contact", "slug": "jane", "company_slug": "acme",
                "name": "Jane Doe", "role_in_process": "recruiter",
                "email": "jane@acme.example"})
            ji.ingest(repo, "c1")
            iv = read(repo, "wiki/jobhunt/interviews/acme-tech.md")
            self.assertIn("interview_type: technical", iv)
            ct = read(repo, "wiki/jobhunt/contacts/jane.md")
            self.assertIn("Jane Doe", ct)
            self.assertIn("role_in_process: recruiter", ct)

    def test_index_md_section_regenerated_idempotently(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            write_capture(repo, "c1", "app.json", {
                "kind": "application", "slug": "x", "company_slug": "c",
                "status": "draft"})
            ji.ingest(repo, "c1")
            ji.ingest(repo, "c1")
            index = read(repo, "wiki/index.md")
            self.assertEqual(index.count("## Job-Hunt"), 1)
            self.assertIn("[[jobhunt/applications/x]]", index)


class TestUnknownKind(unittest.TestCase):
    def test_unknown_kind_reported(self):
        with TemporaryDirectory() as d:
            repo = make_repo(Path(d))
            write_capture(repo, "c1", "bad.json", {"kind": "wat"})
            res = ji.ingest(repo, "c1")
            self.assertTrue(any("unknown capture kind" in e for e in res["errors"]))


if __name__ == "__main__":
    unittest.main()
