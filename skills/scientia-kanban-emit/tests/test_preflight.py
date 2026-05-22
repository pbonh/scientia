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


def _write_hermes_config(dir_path: Path, max_concurrent_children: int | None) -> Path:
    """Write a minimal ~/.hermes/config.yaml-shaped file. None omits the key."""
    if max_concurrent_children is None:
        delegation_block = "delegation:\n  model: ''\n"
    else:
        delegation_block = (
            "delegation:\n"
            "  model: ''\n"
            f"  max_concurrent_children: {max_concurrent_children}\n"
        )
    text = (
        "model:\n"
        "  default: anything\n"
        f"{delegation_block}"
        "kanban:\n"
        "  dispatch_in_gateway: true\n"
    )
    p = dir_path / "config.yaml"
    p.write_text(text)
    return p


class CheckConcurrencyCapTests(unittest.TestCase):
    def test_passes_when_host_value_matches_desired(self):
        with TemporaryDirectory() as td:
            cfg = _write_hermes_config(Path(td), 3)
            self.assertIsNone(
                emit.check_concurrency_cap(desired=3, hermes_config_path=cfg)
            )

    def test_refuses_when_host_value_differs(self):
        with TemporaryDirectory() as td:
            cfg = _write_hermes_config(Path(td), 5)
            reason = emit.check_concurrency_cap(desired=3, hermes_config_path=cfg)
            self.assertIsNotNone(reason)
            self.assertIn("host=5", reason)
            self.assertIn("desired=3", reason)
            self.assertIn("hermes config set delegation.max_concurrent_children 3", reason)

    def test_passes_when_hermes_config_missing(self):
        # No ~/.hermes/config.yaml at all → defer to check_hermes_on_path.
        cfg = Path("/nonexistent/.hermes/config.yaml")
        self.assertIsNone(emit.check_concurrency_cap(desired=3, hermes_config_path=cfg))

    def test_treats_absent_key_as_hermes_default_of_3(self):
        with TemporaryDirectory() as td:
            cfg = _write_hermes_config(Path(td), None)
            # desired=3 matches hermes' built-in default → pass
            self.assertIsNone(
                emit.check_concurrency_cap(desired=3, hermes_config_path=cfg)
            )
            # desired=5 differs from hermes' default → refuse with host=3
            reason = emit.check_concurrency_cap(desired=5, hermes_config_path=cfg)
            self.assertIsNotNone(reason)
            self.assertIn("host=3", reason)
            self.assertIn("desired=5", reason)

    def test_only_matches_key_under_delegation_block(self):
        # `max_concurrent_children` in another (hypothetical) section must not
        # be mistaken for the delegation value.
        with TemporaryDirectory() as td:
            cfg = Path(td) / "config.yaml"
            cfg.write_text(
                "other:\n"
                "  max_concurrent_children: 99\n"
                "delegation:\n"
                "  max_concurrent_children: 3\n"
            )
            self.assertIsNone(
                emit.check_concurrency_cap(desired=3, hermes_config_path=cfg)
            )


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


def _write_adr_with_shared_types(
    dir_path: Path,
    adr_id: str,
    status: str,
    shared_types: list[str],
    form: str = "block",
) -> Path:
    """Write an ADR with the new `shared_types:` field. `form` ∈ {block, inline}."""
    if form == "inline":
        shared = f"shared_types: [{', '.join(shared_types)}]\n"
    else:
        shared = "shared_types:\n" + "".join(f"  - {p}\n" for p in shared_types)
    body = (
        "---\n"
        f"title: \"{adr_id}: shape\"\n"
        f"adr_id: {adr_id}\n"
        f"status: {status}\n"
        f"{shared}"
        "---\n\n# ADR\n"
    )
    p = dir_path / f"{adr_id.lower().replace('adr-', '')}-shape.md"
    p.write_text(body)
    return p


def _write_tasks_md(change_dir: Path, items: list[str]) -> Path:
    text = (
        "---\ntitle: t\n---\n\n# Implementation Plan\n\n"
        + "\n".join(items)
        + "\n"
    )
    p = change_dir / "tasks.md"
    p.write_text(text)
    return p


class CheckAdrSharedTypesTests(unittest.TestCase):
    """Verifies the `@uses-shared:` gate: an emit must refuse when a task
    consumes a shared type whose contract is not yet `accepted`."""

    SHARED_TYPE = "pkg/foo.rs::SharedThing"

    def test_passes_when_no_tasks_md(self):
        with TemporaryDirectory() as td:
            self.assertIsNone(emit.check_adr_shared_types(Path(td)))

    def test_passes_when_no_uses_shared_markers(self):
        with TemporaryDirectory() as td:
            ch = Path(td)
            _write_tasks_md(ch, ["- [ ] **1.** Do thing — @spec: cap#scn"])
            self.assertIsNone(emit.check_adr_shared_types(ch))

    def test_refuses_when_uses_shared_without_any_adr(self):
        with TemporaryDirectory() as td:
            ch = Path(td)
            _write_tasks_md(ch, [
                f"- [ ] **1.** Use shape — @spec: cap#scn @uses-shared:{self.SHARED_TYPE}"
            ])
            reason = emit.check_adr_shared_types(ch)
            self.assertIsNotNone(reason)
            self.assertIn(self.SHARED_TYPE, reason)
            self.assertIn("task #1", reason)

    def test_refuses_when_only_proposed_adr_ratifies(self):
        with TemporaryDirectory() as td:
            ch = Path(td)
            adr = ch / "adr"
            adr.mkdir()
            _write_adr_with_shared_types(adr, "ADR-0005", "proposed", [self.SHARED_TYPE])
            _write_tasks_md(ch, [
                f"- [ ] **1.** Use shape — @uses-shared:{self.SHARED_TYPE}"
            ])
            reason = emit.check_adr_shared_types(ch)
            self.assertIsNotNone(reason)

    def test_passes_when_accepted_adr_ratifies(self):
        with TemporaryDirectory() as td:
            ch = Path(td)
            adr = ch / "adr"
            adr.mkdir()
            _write_adr_with_shared_types(adr, "ADR-0005", "accepted", [self.SHARED_TYPE])
            _write_tasks_md(ch, [
                f"- [ ] **1.** Use shape — @uses-shared:{self.SHARED_TYPE}"
            ])
            self.assertIsNone(emit.check_adr_shared_types(ch))

    def test_passes_with_inline_list_form(self):
        with TemporaryDirectory() as td:
            ch = Path(td)
            adr = ch / "adr"
            adr.mkdir()
            _write_adr_with_shared_types(
                adr, "ADR-0005", "accepted", [self.SHARED_TYPE], form="inline",
            )
            _write_tasks_md(ch, [
                f"- [ ] **1.** Use shape — @uses-shared:{self.SHARED_TYPE}"
            ])
            self.assertIsNone(emit.check_adr_shared_types(ch))

    def test_partial_coverage_lists_only_unratified(self):
        with TemporaryDirectory() as td:
            ch = Path(td)
            adr = ch / "adr"
            adr.mkdir()
            _write_adr_with_shared_types(adr, "ADR-0005", "accepted", [self.SHARED_TYPE])
            other = "pkg/lib.rs::SharedOther"
            _write_tasks_md(ch, [
                f"- [ ] **1.** Use stamp — @uses-shared:{self.SHARED_TYPE}",
                f"- [ ] **2.** Use solver — @uses-shared:{other}",
            ])
            reason = emit.check_adr_shared_types(ch)
            self.assertIsNotNone(reason)
            self.assertIn(other, reason)
            self.assertNotIn(self.SHARED_TYPE, reason)  # ratified one not flagged

    def test_multiple_consumers_all_refused_when_adr_proposed(self):
        """Two sibling tasks both consume the same shared type. While the
        ratifying ADR is still proposed, emit must refuse and name every
        offending task — not just the first."""
        with TemporaryDirectory() as td:
            ch = Path(td)
            adr = ch / "adr"
            adr.mkdir()
            _write_adr_with_shared_types(
                adr, "ADR-0005", "proposed", [self.SHARED_TYPE],
            )
            _write_tasks_md(ch, [
                f"- [ ] **29.** Consumer A — @uses-shared:{self.SHARED_TYPE}",
                f"- [ ] **31.** Consumer B — @uses-shared:{self.SHARED_TYPE}",
            ])
            reason = emit.check_adr_shared_types(ch)
            self.assertIsNotNone(reason)
            self.assertIn("task #29", reason)
            self.assertIn("task #31", reason)


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
            hermes_cfg = _write_hermes_config(change, 3)

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", return_value=subprocess.CompletedProcess(
                     args=[], returncode=0, stdout="", stderr="")):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
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
            hermes_cfg = _write_hermes_config(change, 3)

            with patch("shutil.which", return_value=None):  # no hermes
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                )
        # Expect ≥3 distinct failures (no hermes, no gateway, no verify, deprecated ADR)
        self.assertGreaterEqual(len(reasons), 3)

    def test_concurrency_drift_surfaces_in_aggregated_reasons(self):
        with TemporaryDirectory() as td:
            change = Path(td)
            (change / "adr").mkdir()
            (change / "specs").mkdir()
            _write_verify_report(change, "2026-05-20T1825", "clean",
                                 {"critical": 0, "warning": 0, "suggestion": 0})
            processes = change / "processes.json"
            processes.write_text(json.dumps([{"kind": "gateway", "pid": 1}]))
            hermes_cfg = _write_hermes_config(change, 7)  # host=7, desired=3

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", return_value=subprocess.CompletedProcess(
                     args=[], returncode=0, stdout="", stderr="")):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                )
        self.assertEqual(len(reasons), 1)
        self.assertIn("max_concurrent_children drift", reasons[0])
        self.assertIn("host=7", reasons[0])
        self.assertIn("desired=3", reasons[0])


class PreflightProfileModelsDriftTests(unittest.TestCase):
    """`profiles_block` threaded into preflight() must drive the
    profile-models drift gate (separately from the existing
    max_concurrent_children gate)."""

    def _passing_change(self, td: Path):
        change = td
        (change / "adr").mkdir()
        (change / "specs").mkdir()
        _write_verify_report(change, "2026-05-20T1825", "clean",
                             {"critical": 0, "warning": 0, "suggestion": 0})
        processes = change / "processes.json"
        processes.write_text(json.dumps([{"kind": "gateway", "pid": 1}]))
        hermes_cfg = _write_hermes_config(change, 3)
        return change, processes, hermes_cfg

    def test_no_profiles_block_is_noop(self):
        with TemporaryDirectory() as td:
            change, processes, hermes_cfg = self._passing_change(Path(td))
            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", return_value=subprocess.CompletedProcess(
                     args=[], returncode=0, stdout="", stderr="")):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                    profiles_block=None,
                    profile_names=None,
                )
            self.assertEqual(reasons, [])

    def test_drift_in_profile_models_surfaces_in_preflight(self):
        with TemporaryDirectory() as td:
            change, processes, hermes_cfg = self._passing_change(Path(td))
            profiles_block = {
                "implementer": {"model": {"default": "claude-opus-4.7"}},
            }

            def fake_run(argv, **kw):
                # git log calls succeed; hermes config show returns a drifted value
                if argv[:2] == ["hermes", "-p"]:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0,
                        stdout=json.dumps({"model": {"default": "claude-sonnet-4.6"}}),
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="", stderr="",
                )

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", side_effect=fake_run):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                    profiles_block=profiles_block,
                    profile_names=None,
                    profile_runner=fake_run,
                )
        # Expect exactly one refusal — the profile-models drift one.
        self.assertEqual(len(reasons), 1)
        self.assertIn("profile model config drift", reasons[0])
        self.assertIn("model.default", reasons[0])

    def test_matching_profile_models_passes_preflight(self):
        with TemporaryDirectory() as td:
            change, processes, hermes_cfg = self._passing_change(Path(td))
            profiles_block = {
                "implementer": {"model": {"default": "claude-opus-4.7"}},
            }

            def fake_run(argv, **kw):
                if argv[:2] == ["hermes", "-p"]:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=0,
                        stdout=json.dumps({"model": {"default": "claude-opus-4.7"}}),
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="", stderr="",
                )

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", side_effect=fake_run):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                    profiles_block=profiles_block,
                    profile_names=None,
                    profile_runner=fake_run,
                )
        self.assertEqual(reasons, [])


class PreflightProfilesExistTests(unittest.TestCase):
    """`check_profiles_exist` runs unconditionally — independent of
    `hermes.profiles` model-config. Missing profiles must surface as a
    preflight refusal so emit doesn't strand tasks as
    `skipped_nonspawnable`."""

    def _passing_change(self, td: Path):
        change = td
        (change / "adr").mkdir()
        (change / "specs").mkdir()
        _write_verify_report(change, "2026-05-20T1825", "clean",
                             {"critical": 0, "warning": 0, "suggestion": 0})
        processes = change / "processes.json"
        processes.write_text(json.dumps([{"kind": "gateway", "pid": 1}]))
        hermes_cfg = _write_hermes_config(change, 3)
        return change, processes, hermes_cfg

    def test_missing_profile_refuses_preflight(self):
        with TemporaryDirectory() as td:
            change, processes, hermes_cfg = self._passing_change(Path(td))

            def fake_run(argv, **kw):
                # scientia-integrator does not exist; the others do.
                if argv[:3] == ["hermes", "profile", "show"]:
                    name = argv[3]
                    rc = 1 if name == "scientia-integrator" else 0
                    return subprocess.CompletedProcess(
                        args=argv, returncode=rc, stdout="", stderr="",
                    )
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="", stderr="",
                )

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", side_effect=fake_run):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                    profiles_block=None,
                    profile_names=None,
                    profile_runner=fake_run,
                )
        self.assertEqual(len(reasons), 1)
        self.assertIn("scientia-integrator", reasons[0])
        self.assertIn("scientia-kanban-init", reasons[0])

    def test_all_profiles_present_passes_preflight(self):
        with TemporaryDirectory() as td:
            change, processes, hermes_cfg = self._passing_change(Path(td))

            def fake_run(argv, **kw):
                # All four scientia profiles exist.
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="", stderr="",
                )

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", side_effect=fake_run):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                    profiles_block=None,
                    profile_names=None,
                    profile_runner=fake_run,
                )
        self.assertEqual(reasons, [])

    def test_existence_independent_of_model_config_drift(self):
        # Even with hermes.profiles absent, the existence gate still fires.
        with TemporaryDirectory() as td:
            change, processes, hermes_cfg = self._passing_change(Path(td))

            def fake_run(argv, **kw):
                if argv[:3] == ["hermes", "profile", "show"]:
                    return subprocess.CompletedProcess(
                        args=argv, returncode=1, stdout="",
                        stderr="profile not found",
                    )
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="", stderr="",
                )

            with patch("shutil.which", return_value="/usr/local/bin/hermes"), \
                 patch("subprocess.run", side_effect=fake_run):
                reasons = emit.preflight(
                    change_dir=change,
                    processes_json_path=processes,
                    block_on_severity="critical",
                    trunk="main",
                    desired_concurrency=3,
                    hermes_config_path=hermes_cfg,
                    profiles_block=None,  # absent → drift gate is no-op
                    profile_names=None,
                    profile_runner=fake_run,
                )
        # Exactly one refusal — the existence gate, listing all four roles.
        self.assertEqual(len(reasons), 1)
        for role in ("implementer", "reviewer", "integrator", "aggregator"):
            self.assertIn(f"scientia-{role}", reasons[0])


class YamlSubsetSingleQuoteTests(unittest.TestCase):
    """The YAML parser must treat single-quoted strings the same as
    double-quoted (notably for `model: ''` → empty string, not the
    literal `"''"`)."""

    def test_single_quoted_empty_string(self):
        result = emit._parse_yaml_subset("k: ''\n")
        self.assertEqual(result, {"k": ""})

    def test_single_quoted_non_empty(self):
        result = emit._parse_yaml_subset("k: 'value'\n")
        self.assertEqual(result, {"k": "value"})

    def test_double_quoted_still_works(self):
        result = emit._parse_yaml_subset('k: "value"\n')
        self.assertEqual(result, {"k": "value"})

    def test_nested_hermes_profiles_block_parses(self):
        text = (
            "hermes:\n"
            "  profiles:\n"
            "    implementer:\n"
            "      model:\n"
            "        provider: anthropic\n"
            "        default: claude-opus-4.7\n"
            "        base_url: ''\n"
        )
        result = emit._parse_yaml_subset(text)
        self.assertEqual(
            result["hermes"]["profiles"]["implementer"]["model"],
            {
                "provider": "anthropic",
                "default": "claude-opus-4.7",
                "base_url": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
