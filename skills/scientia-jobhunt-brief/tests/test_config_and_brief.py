"""Tests for the jobhunt config parser and frontmatter helpers in brief.py.

The config parser is a small stdlib reader for the optional `jobhunt:` block
(PyYAML is not a scientia dependency); it is the trickiest reusable piece, so
it gets focused coverage here. An end-to-end brief build is also exercised.
"""

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import _paths  # noqa: F401

import brief


CONFIG = """scientia_schema_version: 1
hermes:
  max_concurrent_children: 3
jobhunt:
  user_profile_page: wiki/jobhunt/profile/me.md
  browser:
    provider: cdp
    cdp_endpoint: http://127.0.0.1:9222
    # key_env: BROWSERBASE_API_KEY
  index: { format: sqlite }
  human_gate: { mode: triage }
verify:
  block_on_severity: critical
"""


class TestConfigParser(unittest.TestCase):
    def _load(self, text: str):
        with TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "development").mkdir()
            (repo / "development" / "config.yaml").write_text(text, encoding="utf-8")
            return brief.load_jobhunt(repo)

    def test_absent_block_returns_none(self):
        self.assertIsNone(self._load("scientia_schema_version: 1\n"))

    def test_commented_block_returns_none(self):
        self.assertIsNone(self._load("#jobhunt:\n#  browser:\n#    provider: cdp\n"))

    def test_nested_and_inline(self):
        jhc = self._load(CONFIG)
        self.assertIsNotNone(jhc)
        self.assertEqual(brief.cfg_get(jhc, "browser.provider"), "cdp")
        self.assertEqual(brief.cfg_get(jhc, "browser.cdp_endpoint"),
                         "http://127.0.0.1:9222")
        # inline `{ format: sqlite }`
        self.assertEqual(brief.cfg_get(jhc, "index.format"), "sqlite")
        self.assertEqual(brief.cfg_get(jhc, "human_gate.mode"), "triage")
        self.assertEqual(brief.cfg_get(jhc, "user_profile_page"),
                         "wiki/jobhunt/profile/me.md")

    def test_full_line_comment_inside_block_ignored(self):
        jhc = self._load(CONFIG)
        # key_env is commented out -> absent
        self.assertIsNone(brief.cfg_get(jhc, "browser.key_env"))

    def test_block_ends_at_next_top_level_key(self):
        jhc = self._load(CONFIG)
        # `verify:` is a sibling top-level key, must not leak in.
        self.assertIsNone(brief.cfg_get(jhc, "block_on_severity"))


class TestFrontmatterHelpers(unittest.TestCase):
    def test_fm_list_inline(self):
        fm = brief.parse_frontmatter('---\nroles: ["A", "B"]\n---\n')
        self.assertEqual(brief.fm_list(fm, "roles"), ["A", "B"])

    def test_fm_list_empty(self):
        fm = brief.parse_frontmatter("---\nroles: []\n---\n")
        self.assertEqual(brief.fm_list(fm, "roles"), [])

    def test_fm_scalar_null(self):
        fm = brief.parse_frontmatter("---\napplied_at: null\n---\n")
        self.assertIsNone(brief.fm_scalar(fm, "applied_at"))


class TestEndToEnd(unittest.TestCase):
    def test_build_writes_brief(self):
        with TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "development").mkdir()
            (repo / "development" / "config.yaml").write_text(CONFIG, encoding="utf-8")
            (repo / "development" / "log.md").write_text("# log\n", encoding="utf-8")
            prof = repo / "wiki" / "jobhunt" / "profile"
            crit = repo / "wiki" / "jobhunt" / "criteria"
            prof.mkdir(parents=True)
            crit.mkdir(parents=True)
            (prof / "me.md").write_text(
                "---\ntype: jobhunt-user-profile\n"
                "resume_source: development/job-hunt/artifacts/base/resume.md\n---\n\n"
                "## Contact\nx@y.z\n\n## Skills\n- rust\n", encoding="utf-8")
            (crit / "rust.md").write_text(
                '---\ntype: jobhunt-target-criteria\n'
                'roles: ["Senior Rust Engineer"]\nboards: ["linkedin"]\n'
                'locations: ["Remote"]\nexclusions: ["crypto"]\n---\n', encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

            import sys
            argv = sys.argv
            sys.argv = ["brief.py", "--repo-root", str(repo), "--campaign", "rust"]
            try:
                rc = brief.main()
            finally:
                sys.argv = argv
            self.assertEqual(rc, 0)
            briefs = list((repo / "development" / "job-hunt" / "briefs").glob("*/brief.md"))
            self.assertEqual(len(briefs), 1)
            text = briefs[0].read_text()
            self.assertIn("type: jobhunt-brief", text)
            self.assertIn("provider: cdp", text)
            self.assertIn('board=`linkedin` query="Senior Rust Engineer"', text)


if __name__ == "__main__":
    unittest.main()
