"""Tests for preflight gates in scripts/emit.py.

Each gate function takes its inputs explicitly (no globals) and returns:
- None  → preflight passed
- str   → preflight refused, with a human-readable reason
"""

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests import _paths  # noqa: F401  — puts scripts/ on sys.path

import emit


class CheckGatewayTests(unittest.TestCase):
    def test_refuses_when_processes_json_is_empty_list(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "processes.json"
            path.write_text("[]")
            reason = emit.check_gateway(path)
            self.assertIsNotNone(reason)
            self.assertIn("gateway", reason.lower())

    def test_refuses_when_processes_json_is_missing(self):
        path = Path("/nonexistent/processes.json")
        reason = emit.check_gateway(path)
        self.assertIsNotNone(reason)

    def test_passes_when_gateway_entry_present(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "processes.json"
            path.write_text(json.dumps([
                {"kind": "gateway", "pid": 42, "started_at": "2026-05-20T20:00:00Z"}
            ]))
            self.assertIsNone(emit.check_gateway(path))

    def test_refuses_when_only_non_gateway_processes_present(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "processes.json"
            path.write_text(json.dumps([
                {"kind": "worker", "pid": 99}
            ]))
            self.assertIsNotNone(emit.check_gateway(path))


class CheckHermesOnPathTests(unittest.TestCase):
    def test_passes_when_hermes_resolves(self):
        with patch("shutil.which", return_value="/usr/local/bin/hermes"):
            self.assertIsNone(emit.check_hermes_on_path())

    def test_refuses_when_hermes_missing(self):
        with patch("shutil.which", return_value=None):
            reason = emit.check_hermes_on_path()
            self.assertIsNotNone(reason)
            self.assertIn("hermes", reason.lower())


def _write_verify_report(dir_path: Path, ts: str, worst: str,
                         counts: dict) -> Path:
    """Write a verify-{ts}.md with frontmatter matching scientia conventions."""
    counts_block = "\n".join(f"  {k}: {v}" for k, v in counts.items())
    body = (
        "---\n"
        f"title: \"Verify report — fake/{ts}\"\n"
        "type: verify-report\n"
        f"worst_severity: {worst}\n"
        "counts:\n"
        f"{counts_block}\n"
        "---\n\n# Verify report\n"
    )
    p = dir_path / f"verify-{ts}.md"
    p.write_text(body)
    return p


class CheckVerifySeverityTests(unittest.TestCase):
    def test_refuses_when_no_verify_report_exists(self):
        with TemporaryDirectory() as td:
            reason = emit.check_verify_severity(Path(td), block_on="critical")
            self.assertIsNotNone(reason)
            self.assertIn("verify", reason.lower())

    def test_passes_when_worst_severity_is_clean(self):
        with TemporaryDirectory() as td:
            _write_verify_report(Path(td), "2026-05-20T1825", "clean",
                                 {"critical": 0, "warning": 0, "suggestion": 3})
            self.assertIsNone(emit.check_verify_severity(Path(td), block_on="critical"))

    def test_passes_when_severity_below_block_threshold(self):
        with TemporaryDirectory() as td:
            _write_verify_report(Path(td), "2026-05-20T1825", "warning",
                                 {"critical": 0, "warning": 1, "suggestion": 0})
            # block_on=critical means warning is acceptable
            self.assertIsNone(emit.check_verify_severity(Path(td), block_on="critical"))

    def test_refuses_when_worst_meets_block_threshold(self):
        with TemporaryDirectory() as td:
            _write_verify_report(Path(td), "2026-05-20T1825", "critical",
                                 {"critical": 2, "warning": 0, "suggestion": 0})
            reason = emit.check_verify_severity(Path(td), block_on="critical")
            self.assertIsNotNone(reason)
            self.assertIn("critical", reason.lower())

    def test_picks_latest_report_by_filename_when_multiple_exist(self):
        with TemporaryDirectory() as td:
            _write_verify_report(Path(td), "2026-05-20T1000", "critical",
                                 {"critical": 5, "warning": 0, "suggestion": 0})
            _write_verify_report(Path(td), "2026-05-20T1825", "clean",
                                 {"critical": 0, "warning": 0, "suggestion": 0})
            # Latest (1825) is clean, so we pass even though an earlier one was critical.
            self.assertIsNone(emit.check_verify_severity(Path(td), block_on="critical"))


def _write_adr(dir_path: Path, adr_id: str, status: str,
               superseded_by: str | None = None) -> Path:
    body = (
        "---\n"
        f"title: \"{adr_id}: fake\"\n"
        f"adr_id: {adr_id}\n"
        f"status: {status}\n"
        f"superseded_by: {superseded_by if superseded_by else 'null'}\n"
        "---\n\n# ADR\n"
    )
    p = dir_path / f"{adr_id.lower().replace('adr-', '')}-fake.md"
    p.write_text(body)
    return p


class CheckAdrStatusTests(unittest.TestCase):
    def test_passes_when_all_adrs_accepted(self):
        with TemporaryDirectory() as td:
            adr_dir = Path(td) / "adr"
            adr_dir.mkdir()
            _write_adr(adr_dir, "ADR-0001", "accepted")
            _write_adr(adr_dir, "ADR-0002", "accepted")
            self.assertIsNone(emit.check_adr_status(Path(td)))

    def test_passes_when_proposed(self):
        with TemporaryDirectory() as td:
            adr_dir = Path(td) / "adr"
            adr_dir.mkdir()
            _write_adr(adr_dir, "ADR-0001", "proposed")
            self.assertIsNone(emit.check_adr_status(Path(td)))

    def test_refuses_when_deprecated_without_successor(self):
        with TemporaryDirectory() as td:
            adr_dir = Path(td) / "adr"
            adr_dir.mkdir()
            _write_adr(adr_dir, "ADR-0001", "deprecated")
            reason = emit.check_adr_status(Path(td))
            self.assertIsNotNone(reason)
            self.assertIn("ADR-0001", reason)

    def test_passes_when_superseded_with_successor(self):
        with TemporaryDirectory() as td:
            adr_dir = Path(td) / "adr"
            adr_dir.mkdir()
            _write_adr(adr_dir, "ADR-0001", "superseded", superseded_by="ADR-0007")
            self.assertIsNone(emit.check_adr_status(Path(td)))

    def test_refuses_when_superseded_without_successor(self):
        with TemporaryDirectory() as td:
            adr_dir = Path(td) / "adr"
            adr_dir.mkdir()
            _write_adr(adr_dir, "ADR-0001", "superseded")  # superseded_by: null
            self.assertIsNotNone(emit.check_adr_status(Path(td)))

    def test_passes_when_no_adr_dir_present(self):
        # Some changes have no ADRs; that's not a refusal condition.
        with TemporaryDirectory() as td:
            self.assertIsNone(emit.check_adr_status(Path(td)))


class CheckSpecOnTrunkTests(unittest.TestCase):
    """`git:spec-on-trunk` — every specs/*/spec.md must be reachable from trunk
    (i.e., committed on the default branch). We model this by checking that
    `git log <branch> -- <spec>` returns a non-empty commit list.
    """

    def test_passes_when_git_command_returns_commits(self):
        with patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="deadbeef\n", stderr=""
            )
            with TemporaryDirectory() as td:
                spec = Path(td) / "specs" / "x" / "spec.md"
                spec.parent.mkdir(parents=True)
                spec.write_text("# spec\n")
                self.assertIsNone(emit.check_spec_on_trunk(Path(td), trunk="main"))

    def test_refuses_when_spec_not_on_trunk(self):
        with patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            with TemporaryDirectory() as td:
                spec = Path(td) / "specs" / "x" / "spec.md"
                spec.parent.mkdir(parents=True)
                spec.write_text("# spec\n")
                reason = emit.check_spec_on_trunk(Path(td), trunk="main")
                self.assertIsNotNone(reason)
                self.assertIn("trunk", reason.lower())

    def test_passes_when_no_specs_exist(self):
        # Vacuously true. A change with zero specs has no spec-on-trunk problem.
        with TemporaryDirectory() as td:
            (Path(td) / "specs").mkdir()
            self.assertIsNone(emit.check_spec_on_trunk(Path(td), trunk="main"))


class PreflightAggregatorTests(unittest.TestCase):
    """`preflight` runs every gate and returns the list of refusal reasons."""

    def test_returns_empty_list_when_all_gates_pass(self):
        with TemporaryDirectory() as td:
            change = Path(td)
            (change / "adr").mkdir()
            (change / "specs").mkdir()
            _write_verify_report(change, "2026-05-20T1825", "clean",
                                 {"critical": 0, "warning": 0, "suggestion": 0})
            processes = change / "processes.json"
            processes.write_text(json.dumps([{"kind": "gateway", "pid": 1}]))

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", return_value=subprocess.CompletedProcess(
                     args=[], returncode=0, stdout="", stderr="")):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                )
        self.assertEqual(reasons, [])

    def test_collects_all_failures_not_just_first(self):
        # Multiple gates fail simultaneously — preflight reports them all.
        with TemporaryDirectory() as td:
            change = Path(td)
            (change / "adr").mkdir()
            _write_adr(change / "adr", "ADR-0001", "deprecated")
            # no verify report → gate fails
            processes = change / "processes.json"
            processes.write_text("[]")  # no gateway

            with patch("shutil.which", return_value=None):  # no hermes
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                )
        # Expect ≥3 distinct failures (no hermes, no gateway, no verify, deprecated ADR)
        self.assertGreaterEqual(len(reasons), 3)


if __name__ == "__main__":
    unittest.main()
