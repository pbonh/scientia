"""Tests for scripts/rebuild_index.py.

The index is a pure function of wiki/jobhunt/ frontmatter. We assert:
- record extraction (applications, status history, interviews, contacts)
- the funnel/conversion report
- sqlite + yaml writers
- the --check staleness signal (the only divergence channel gate_jobhunt uses)
"""

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import _paths  # noqa: F401

import rebuild_index as ri


APP_ACME = """---
title: "Application — Senior Rust Engineer @ Acme"
type: jobhunt-application
status: interviewing
applied_at: 2026-05-21T10:00:00Z
company: "[[jobhunt/companies/acme]]"
posting: "[[jobhunt/postings/acme-rust]]"
campaign_id: "2026-05-20-rust"
kanban_task_id: "t_ff01"
submit_task_id: "t_sub01"
idempotency_key: "application:acme:abcd1234ef567890"
---

## Status History
- 2026-05-20T09:00:00Z — (none) → draft — scientia-jobhunt-ingest — created
- 2026-05-21T10:00:00Z — draft → applied — human — submitted
- 2026-05-22T12:00:00Z — applied → screening — scientia-jobhunt-ingest — recruiter
- 2026-05-24T15:00:00Z — screening → interviewing — scientia-jobhunt-ingest — passed

## Notes
appended notes here must not be parsed as history.
- 2099-01-01T00:00:00Z — interviewing → offer — human — NOT in history section
"""

APP_GLOBEX = """---
title: "Application — Staff Backend @ Globex"
type: jobhunt-application
status: rejected
company: "[[jobhunt/companies/globex]]"
idempotency_key: "application:globex:99887766aabbccdd"
---

## Status History
- 2026-05-18T09:00:00Z — (none) → draft — scientia-jobhunt-ingest — created
- 2026-05-19T10:00:00Z — draft → applied — human — submitted
- 2026-05-23T10:00:00Z — applied → rejected — scientia-jobhunt-ingest — auto-reject
"""

INTERVIEW = """---
title: "technical interview — Acme"
type: jobhunt-interview
application: "[[jobhunt/applications/acme]]"
interview_type: technical
scheduled_at: 2099-01-15T17:00:00Z
status: scheduled
rating: null
---

## Prep Notes
"""

CONTACT = """---
title: "Jane Doe — Acme"
type: jobhunt-contact
company: "[[jobhunt/companies/acme]]"
name: "Jane Doe"
role_in_process: recruiter
---

## Notes
"""


def make_repo(tmp: Path) -> Path:
    jh = tmp / "wiki" / "jobhunt"
    for sub in ("applications", "interviews", "contacts"):
        (jh / sub).mkdir(parents=True, exist_ok=True)
    (jh / "applications" / "acme.md").write_text(APP_ACME, encoding="utf-8")
    (jh / "applications" / "globex.md").write_text(APP_GLOBEX, encoding="utf-8")
    (jh / "interviews" / "acme-tech.md").write_text(INTERVIEW, encoding="utf-8")
    (jh / "contacts" / "jane.md").write_text(CONTACT, encoding="utf-8")
    return tmp


class TestRecords(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.repo = make_repo(Path(self._td.name))
        self.records = ri.build_records(self.repo)

    def tearDown(self):
        self._td.cleanup()

    def test_applications_extracted(self):
        apps = {a["app_slug"]: a for a in self.records["applications"]}
        self.assertEqual(set(apps), {"acme", "globex"})
        self.assertEqual(apps["acme"]["status"], "interviewing")
        self.assertEqual(apps["acme"]["company"], "jobhunt/companies/acme")
        self.assertEqual(apps["acme"]["kanban_task_id"], "t_ff01")

    def test_status_history_stops_at_section_boundary(self):
        # The "offer" line lives under ## Notes and must NOT be parsed.
        acme_hist = [h for h in self.records["status_history"]
                     if h["app_slug"] == "acme"]
        tos = [h["to_status"] for h in acme_hist]
        self.assertEqual(tos, ["draft", "applied", "screening", "interviewing"])
        self.assertNotIn("offer", tos)

    def test_ever_statuses(self):
        apps = {a["app_slug"]: a for a in self.records["applications"]}
        self.assertEqual(
            set(apps["acme"]["ever_statuses"]),
            {"draft", "applied", "screening", "interviewing"})

    def test_interviews_and_contacts(self):
        self.assertEqual(len(self.records["interviews"]), 1)
        iv = self.records["interviews"][0]
        self.assertEqual(iv["application"], "jobhunt/applications/acme")
        self.assertEqual(iv["interview_type"], "technical")
        self.assertEqual(len(self.records["contacts"]), 1)
        self.assertEqual(self.records["contacts"][0]["name"], "Jane Doe")


class TestReport(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.repo = make_repo(Path(self._td.name))
        self.report = ri.build_report(ri.build_records(self.repo))

    def tearDown(self):
        self._td.cleanup()

    def test_funnel_counts(self):
        # Both apps reached `applied`; one reached `screening`+`interviewing`.
        self.assertIn("applied → screening: 1/2 (50%)", self.report)
        self.assertIn("screening → interviewing: 1/1 (100%)", self.report)

    def test_upcoming_interview_listed(self):
        self.assertIn("2099-01-15T17:00:00Z", self.report)


class TestWritersAndCheck(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.repo = make_repo(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def _run(self, *args):
        import sys
        argv = sys.argv
        sys.argv = ["rebuild_index.py", "--repo-root", str(self.repo), *args]
        try:
            return ri.main()
        finally:
            sys.argv = argv

    def test_sqlite_written_and_queryable(self):
        rc = self._run("--format", "sqlite")
        self.assertEqual(rc, 0)
        db = self.repo / "development" / "job-hunt" / "pipeline.sqlite"
        self.assertTrue(db.exists())
        con = sqlite3.connect(db)
        try:
            rows = dict(con.execute("select app_slug, status from applications"))
        finally:
            con.close()
        self.assertEqual(rows, {"acme": "interviewing", "globex": "rejected"})

    def test_check_passes_when_fresh(self):
        self.assertEqual(self._run("--format", "sqlite"), 0)
        self.assertEqual(self._run("--format", "sqlite", "--check"), 0)

    def test_check_fails_when_stale(self):
        self.assertEqual(self._run("--format", "sqlite"), 0)
        # Mutate a status the index was built from.
        p = self.repo / "wiki" / "jobhunt" / "applications" / "acme.md"
        p.write_text(p.read_text().replace("status: interviewing",
                                           "status: offer"), encoding="utf-8")
        self.assertEqual(self._run("--format", "sqlite", "--check"), 1)

    def test_check_fails_when_missing(self):
        self.assertEqual(self._run("--format", "sqlite", "--check"), 1)

    def test_yaml_written(self):
        self.assertEqual(self._run("--format", "yaml"), 0)
        y = self.repo / "development" / "job-hunt" / "pipeline.yaml"
        self.assertTrue(y.exists())
        self.assertIn("applications:", y.read_text())


if __name__ == "__main__":
    unittest.main()
