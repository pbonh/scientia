"""Tests for orchestrate() and the CLI wrapper main().

orchestrate() ties together preflight + pattern_for + build_bodies +
emit_one + writeback + index + log. It takes its dependencies explicitly
(runner, processes_json_path, config) so it's fully unit-testable.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from tests import _paths  # noqa: F401

import emit


# ---------------------------------------------------------------------------
# Fixture builder for orchestrate-level tests
# ---------------------------------------------------------------------------


CONFIG = {
    "emit": {
        "default_pattern_by_adr_status": {
            "accepted": "P2-pipeline",
            "proposed": "P5-human-in-loop",
            "deprecated": "refuse",
            "superseded": "refuse",
        },
        "require_approval_tenants": [],
    },
    "verify": {"block_on_severity": "critical"},
    "hermes": {
        "profile_names": {
            "implementer": "scientia-implementer",
            "reviewer": "scientia-reviewer",
            "integrator": "scientia-integrator",
            "aggregator": "scientia-aggregator",
        },
    },
}


def _make_runner(stub_existing=None):
    class R:
        def __init__(self):
            self.calls = []
            self._next = 0
            self.existing = stub_existing or {}

        def __call__(self, argv, **kw):
            self.calls.append(list(argv))
            if "create" in argv:
                try:
                    key = argv[argv.index("--idempotency-key") + 1]
                except (ValueError, IndexError):
                    key = None
                if key and key in self.existing:
                    tid = self.existing[key]
                else:
                    self._next += 1
                    tid = f"t_{self._next:02d}"
                return SimpleNamespace(returncode=0,
                                       stdout=json.dumps({"task_id": tid}),
                                       stderr="")
            if "list" in argv:
                # Pre-emit lookup of existing keys: respond with our `existing` map
                items = [{"id": tid, "idempotency_key": k}
                         for k, tid in self.existing.items()]
                return SimpleNamespace(returncode=0,
                                       stdout=json.dumps(items), stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
    return R()


def _seed_repo(root: Path, *, tenant="t", change_slug="2026-05-20-test",
               capability="cap", scenarios=2) -> Path:
    """Create a minimal repo layout that orchestrate() can read."""
    change = root / "openspec" / "changes" / f"{tenant}-{change_slug}"
    spec_dir = change / "specs" / capability
    spec_dir.mkdir(parents=True)
    adr_dir = change / "adr"
    adr_dir.mkdir()
    (adr_dir / "0001-thing.md").write_text(
        "---\nadr_id: ADR-0001\nstatus: accepted\ntitle: \"ADR-0001: A thing\"\n---\n"
    )

    (change / "tasks.md").write_text(
        "---\ntitle: T\n---\n\n# Implementation Plan\n\n- [ ] **1.** Do thing @adr: ADR-0001\n"
    )

    # Verify report — clean
    (change / "verify-2026-05-20T1825.md").write_text(
        "---\ntype: verify-report\nworst_severity: clean\n"
        "counts:\n  critical: 0\n  warning: 0\n  suggestion: 0\n---\n"
    )

    # processes.json — gateway up
    (root / "processes.json").write_text(json.dumps(
        [{"kind": "gateway", "pid": 1}]
    ))

    # ~/.hermes/config.yaml stub — host concurrency matches CONFIG's default (3)
    (root / "hermes_config.yaml").write_text(
        "model:\n  default: anything\n"
        "delegation:\n  max_concurrent_children: 3\n"
        "kanban:\n  dispatch_in_gateway: true\n"
    )

    # spec.md
    sc_blocks = "\n\n".join(
        f"### Scenario: scenario {i+1}\n```gherkin\nGiven x\nWhen y\nThen z\n```"
        for i in range(scenarios)
    )
    (spec_dir / "spec.md").write_text(
        f"---\ntitle: S\ncapability: {capability}\n---\n\n"
        f"# Capability: My Cap\n\nA description.\n\n"
        f"## Glossary (inlined from manifest)\n\n| T | D |\n|---|---|\n| **F** | foo. |\n\n"
        f"## Acceptance Criteria\n\n- One.\n\n## Scenarios\n\n{sc_blocks}\n"
    )

    return change


def _patch_git(monkeypatch_func):
    """Make subprocess.run('git log ...') always succeed as 'on trunk'."""
    real = __import__("subprocess").run

    def fake(argv, **kw):
        if argv[:2] == ["git", "log"]:
            return SimpleNamespace(returncode=0, stdout="deadbeef\n", stderr="")
        return real(argv, **kw)

    monkeypatch_func(fake)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class OrchestrateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.change = _seed_repo(self.root, scenarios=2)
        self.handoff = self.root / "HANDOFF.md"
        self.handoff.write_text("## Required Handoff\n\n- summary — short prose\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_emits_correct_number_of_tasks_for_P2(self):
        runner = _make_runner()
        from unittest.mock import patch as _patch
        with _patch("subprocess.run") as sub:
            sub.side_effect = lambda argv, **kw: SimpleNamespace(
                returncode=0, stdout="deadbeef\n", stderr=""
            )
            result = emit.orchestrate(
                repo_root=self.root,
                change_id="t/2026-05-20-test",
                config=CONFIG,
                processes_json_path=self.root / "processes.json",
                handoff_path=self.handoff,
                runner=runner,
                dry_run=False,
                hermes_config_path=self.root / "hermes_config.yaml",
            )
        # tasks.md emit: 1 item * 3 stages = 3
        # per-spec emit: 1 parent + 2 children * 3 stages + 1 aggregator = 8
        # total = 11
        self.assertEqual(result["tasks"], 11)
        self.assertEqual(result["pattern"], "P2-pipeline")

    def test_dry_run_does_not_write_files(self):
        runner = _make_runner()
        from unittest.mock import patch as _patch
        with _patch("subprocess.run") as sub:
            sub.side_effect = lambda argv, **kw: SimpleNamespace(
                returncode=0, stdout="deadbeef\n", stderr=""
            )
            emit.orchestrate(
                repo_root=self.root,
                change_id="t/2026-05-20-test",
                config=CONFIG,
                processes_json_path=self.root / "processes.json",
                handoff_path=self.handoff,
                runner=runner,
                dry_run=True,
            )
        # No index files written
        tasks_dir = self.root / "development" / "tasks"
        self.assertFalse(tasks_dir.exists())
        # No log line appended
        self.assertFalse((self.root / "development" / "log.md").exists())
        # No `## Kanban Tasks` section added to spec
        spec_text = (self.change / "specs" / "cap" / "spec.md").read_text()
        self.assertNotIn("## Kanban Tasks", spec_text)

    def test_dry_run_does_not_invoke_runner(self):
        runner = _make_runner()
        from unittest.mock import patch as _patch
        with _patch("subprocess.run") as sub:
            sub.side_effect = lambda argv, **kw: SimpleNamespace(
                returncode=0, stdout="deadbeef\n", stderr=""
            )
            emit.orchestrate(
                repo_root=self.root,
                change_id="t/2026-05-20-test",
                config=CONFIG,
                processes_json_path=self.root / "processes.json",
                handoff_path=self.handoff,
                runner=runner,
                dry_run=True,
            )
        self.assertEqual(runner.calls, [])

    def test_writes_index_entries_and_log_on_real_run(self):
        runner = _make_runner()
        from unittest.mock import patch as _patch
        with _patch("subprocess.run") as sub:
            sub.side_effect = lambda argv, **kw: SimpleNamespace(
                returncode=0, stdout="deadbeef\n", stderr=""
            )
            emit.orchestrate(
                repo_root=self.root,
                change_id="t/2026-05-20-test",
                config=CONFIG,
                processes_json_path=self.root / "processes.json",
                handoff_path=self.handoff,
                runner=runner,
                dry_run=False,
                hermes_config_path=self.root / "hermes_config.yaml",
            )
        tasks_dir = self.root / "development" / "tasks" / "t" / "2026-05-20-test"
        self.assertTrue(tasks_dir.is_dir())
        # 11 index files: 8 per-spec (parent + 2*3 + aggregator) + 3 tasks.md (1 item * 3 stages)
        self.assertEqual(len(list(tasks_dir.glob("*.md"))), 11)
        log = (self.root / "development" / "log.md").read_text()
        self.assertIn("scientia-kanban-emit — emitted", log)
        # spec.md has the writeback section now
        spec_text = (self.change / "specs" / "cap" / "spec.md").read_text()
        self.assertIn("## Kanban Tasks", spec_text)

    def test_raises_when_preflight_refuses(self):
        # break the gateway preflight
        (self.root / "processes.json").write_text("[]")
        runner = _make_runner()
        with self.assertRaises(emit.PreflightRefused) as ctx:
            emit.orchestrate(
                repo_root=self.root,
                change_id="t/2026-05-20-test",
                config=CONFIG,
                processes_json_path=self.root / "processes.json",
                handoff_path=self.handoff,
                runner=runner,
                hermes_config_path=self.root / "hermes_config.yaml",
            )
        self.assertTrue(any("gateway" in r.lower() for r in ctx.exception.reasons))


class EndToEndAgainstTestScientiaImplTests(unittest.TestCase):
    """If ../test_scientia_impl exists, run orchestrate against the real
    `ansible/2026-05-20-terminal-tool-configs` change in dry-run mode and
    assert the expected fan-out.

    Skipped silently when the sibling repo isn't checked out.
    """

    REPO = Path(__file__).resolve().parent.parent.parent.parent.parent / "test_scientia_impl"

    @classmethod
    def setUpClass(cls):
        if not cls.REPO.is_dir():
            raise unittest.SkipTest(f"{cls.REPO} not present")

    def test_dry_run_against_real_fixture(self):
        from unittest.mock import patch as _patch
        config = CONFIG  # the real config.yaml uses the same shape
        handoff = (Path(__file__).resolve().parent.parent
                   / "references" / "HANDOFF_SCHEMA.md")
        runner = _make_runner()

        # Pretend the gateway is up by pointing at a temp processes.json.
        with TemporaryDirectory() as td:
            pjson = Path(td) / "processes.json"
            pjson.write_text(json.dumps([{"kind": "gateway", "pid": 1}]))

            with _patch("subprocess.run") as sub:
                sub.side_effect = lambda argv, **kw: SimpleNamespace(
                    returncode=0, stdout="deadbeef\n", stderr=""
                )
                result = emit.orchestrate(
                    repo_root=self.REPO,
                    change_id="ansible/2026-05-20-terminal-tool-configs",
                    config=config,
                    processes_json_path=pjson,
                    handoff_path=handoff,
                    runner=runner,
                    dry_run=True,
                )
        # 7 scenarios in the real spec → P2-pipeline → 1 parent + 7*3 + 1 = 23
        self.assertEqual(result["tasks"], 23)
        self.assertEqual(result["pattern"], "P2-pipeline")


class MainCLITests(unittest.TestCase):
    """`python3 -m emit --change <id> --dry-run` exits 0 and writes nothing."""

    def test_main_dry_run_returns_zero(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _seed_repo(root)
            (root / "HANDOFF.md").write_text("## Required Handoff\n\n- summary\n")

            from unittest.mock import patch as _patch
            with _patch("subprocess.run") as sub:
                sub.side_effect = lambda argv, **kw: SimpleNamespace(
                    returncode=0, stdout="deadbeef\n", stderr=""
                )
                rc = emit.main([
                    "--change", "t/2026-05-20-test",
                    "--dry-run",
                    "--repo-root", str(root),
                    "--processes-json", str(root / "processes.json"),
                    "--handoff", str(root / "HANDOFF.md"),
                ])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
