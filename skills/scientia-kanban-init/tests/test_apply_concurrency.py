"""Tests for scripts/apply_concurrency.py — propagating the concurrency cap.

Covers:
- read_effective_delegation_cap: host vs profile argv, None for unset,
  failure surfacing, type rejection.
- set_delegation_cap: argv shape, error surface.
- apply_concurrency: idempotency (already-set), per-target writes, the
  ROLES iteration order, validation refusal on bad caps.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any, Dict, List

from tests import _paths  # noqa: F401

import apply_concurrency as ac


def _make_runner(
    *,
    host_cap: int | None = None,
    profile_caps: Dict[str, int | None] | None = None,
    fail_on: List[str] | None = None,
):
    """Fake `subprocess.run`.

    - `hermes config show --json` (no -p)             → host config JSON.
    - `hermes -p NAME config show --json`             → profile config JSON.
    - `hermes [-p NAME] config set delegation.max_concurrent_children N`
      → success unless NAME (or 'host') is in `fail_on`.

    Records every call in runner.calls.
    """
    profile_caps = profile_caps or {}
    fail_on = fail_on or []

    def runner(argv, **_kw):
        runner.calls.append(list(argv))
        is_show = "show" in argv and "--json" in argv
        is_set = "set" in argv
        has_profile = "-p" in argv
        profile = argv[argv.index("-p") + 1] if has_profile else None

        if is_show:
            payload: Dict[str, Any]
            if profile is None:
                cap = host_cap
            else:
                cap = profile_caps.get(profile)
            if cap is None:
                payload = {}
            else:
                payload = {"delegation": {"max_concurrent_children": cap}}
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr="",
            )
        if is_set:
            target = profile or "host"
            if target in fail_on:
                return SimpleNamespace(
                    returncode=1, stdout="",
                    stderr=f"hermes rejected {target}",
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    runner.calls = []
    return runner


# ---------------------------------------------------------------------------
# read_effective_delegation_cap
# ---------------------------------------------------------------------------


class ReadEffectiveDelegationCapTests(unittest.TestCase):
    def test_returns_int_when_set(self):
        runner = _make_runner(host_cap=5)
        self.assertEqual(ac.read_effective_delegation_cap(runner=runner), 5)
        self.assertNotIn("-p", runner.calls[0])

    def test_returns_none_when_unset(self):
        runner = _make_runner(host_cap=None)
        self.assertIsNone(ac.read_effective_delegation_cap(runner=runner))

    def test_profile_argv_includes_p_flag(self):
        runner = _make_runner(profile_caps={"scientia-implementer": 3})
        ac.read_effective_delegation_cap(
            profile="scientia-implementer", runner=runner,
        )
        self.assertIn("-p", runner.calls[0])
        self.assertEqual(
            runner.calls[0][runner.calls[0].index("-p") + 1],
            "scientia-implementer",
        )

    def test_raises_on_nonzero_exit(self):
        def runner(argv, **_kw):
            return SimpleNamespace(
                returncode=2, stdout="", stderr="boom",
            )
        with self.assertRaises(RuntimeError) as ctx:
            ac.read_effective_delegation_cap(runner=runner)
        self.assertIn("boom", str(ctx.exception))

    def test_raises_on_invalid_json(self):
        def runner(argv, **_kw):
            return SimpleNamespace(
                returncode=0, stdout="not json", stderr="",
            )
        with self.assertRaises(RuntimeError) as ctx:
            ac.read_effective_delegation_cap(runner=runner)
        self.assertIn("invalid JSON", str(ctx.exception))

    def test_rejects_boolean_value(self):
        def runner(argv, **_kw):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"delegation": {"max_concurrent_children": True}}),
                stderr="",
            )
        with self.assertRaises(RuntimeError) as ctx:
            ac.read_effective_delegation_cap(runner=runner)
        self.assertIn("boolean", str(ctx.exception))

    def test_rejects_non_integer_value(self):
        def runner(argv, **_kw):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"delegation": {"max_concurrent_children": "3"}}),
                stderr="",
            )
        with self.assertRaises(RuntimeError) as ctx:
            ac.read_effective_delegation_cap(runner=runner)
        self.assertIn("non-integer", str(ctx.exception))


# ---------------------------------------------------------------------------
# set_delegation_cap
# ---------------------------------------------------------------------------


class SetDelegationCapTests(unittest.TestCase):
    def test_host_argv_shape(self):
        runner = _make_runner()
        ac.set_delegation_cap(profile=None, value=4, runner=runner)
        self.assertEqual(len(runner.calls), 1)
        call = runner.calls[0]
        self.assertNotIn("-p", call)
        self.assertIn("set", call)
        self.assertIn("delegation.max_concurrent_children", call)
        self.assertIn("4", call)

    def test_profile_argv_shape(self):
        runner = _make_runner()
        ac.set_delegation_cap(
            profile="my-profile", value=7, runner=runner,
        )
        call = runner.calls[0]
        self.assertEqual(call[call.index("-p") + 1], "my-profile")
        self.assertEqual(call[-1], "7")

    def test_surfaces_failure(self):
        runner = _make_runner(fail_on=["host"])
        with self.assertRaises(RuntimeError) as ctx:
            ac.set_delegation_cap(profile=None, value=3, runner=runner)
        self.assertIn("rejected host", str(ctx.exception))


# ---------------------------------------------------------------------------
# apply_concurrency
# ---------------------------------------------------------------------------


class ApplyConcurrencyTests(unittest.TestCase):
    def test_writes_all_targets_when_unset(self):
        runner = _make_runner(host_cap=None, profile_caps={})
        with TemporaryDirectory() as td:
            summary = ac.apply_concurrency(
                config={"hermes": {"max_concurrent_children": 5}},
                repo_root=Path(td),
                runner=runner,
            )

        # Host + 4 roles.
        self.assertEqual(
            set(summary.keys()),
            {"host", "implementer", "reviewer",
             "integrator", "aggregator"},
        )
        for target, info in summary.items():
            self.assertEqual(info["value"], 5)
            self.assertEqual(info["action"], "applied")
            self.assertIsNone(info.get("previous"))

        # 5 reads + 5 writes = 10 calls.
        set_calls = [c for c in runner.calls if "set" in c]
        show_calls = [c for c in runner.calls if "show" in c]
        self.assertEqual(len(set_calls), 5)
        self.assertEqual(len(show_calls), 5)

    def test_no_writes_when_all_already_match(self):
        runner = _make_runner(
            host_cap=3,
            profile_caps={
                "scientia-implementer": 3,
                "scientia-reviewer": 3,
                "scientia-integrator": 3,
                "scientia-aggregator": 3,
            },
        )
        with TemporaryDirectory() as td:
            summary = ac.apply_concurrency(
                config={"hermes": {"max_concurrent_children": 3}},
                repo_root=Path(td),
                runner=runner,
            )
        for info in summary.values():
            self.assertEqual(info["action"], "already-set")
        # Only reads.
        self.assertEqual([c for c in runner.calls if "set" in c], [])

    def test_partial_drift_only_writes_drifted_targets(self):
        # Host already correct; implementer drifted; rest already correct.
        runner = _make_runner(
            host_cap=4,
            profile_caps={
                "scientia-implementer": 2,
                "scientia-reviewer": 4,
                "scientia-integrator": 4,
                "scientia-aggregator": 4,
            },
        )
        with TemporaryDirectory() as td:
            summary = ac.apply_concurrency(
                config={"hermes": {"max_concurrent_children": 4}},
                repo_root=Path(td),
                runner=runner,
            )

        self.assertEqual(summary["host"]["action"], "already-set")
        self.assertEqual(summary["implementer"]["action"], "applied")
        self.assertEqual(summary["implementer"]["previous"], 2)
        for role in ("reviewer", "integrator", "aggregator"):
            self.assertEqual(summary[role]["action"], "already-set")

        # Only one set call, against the implementer.
        set_calls = [c for c in runner.calls if "set" in c]
        self.assertEqual(len(set_calls), 1)
        self.assertEqual(
            set_calls[0][set_calls[0].index("-p") + 1],
            "scientia-implementer",
        )

    def test_defaults_to_three_when_unset(self):
        runner = _make_runner(host_cap=3, profile_caps={
            "scientia-implementer": 3,
            "scientia-reviewer": 3,
            "scientia-integrator": 3,
            "scientia-aggregator": 3,
        })
        with TemporaryDirectory() as td:
            summary = ac.apply_concurrency(
                config={"hermes": {}},  # no max_concurrent_children
                repo_root=Path(td),
                runner=runner,
            )
        # Default 3 — every target already-set.
        for info in summary.values():
            self.assertEqual(info["value"], 3)
            self.assertEqual(info["action"], "already-set")

    def test_respects_profile_name_overrides(self):
        runner = _make_runner(
            host_cap=3,
            profile_caps={"my-impl": 3, "scientia-reviewer": 3,
                          "scientia-integrator": 3,
                          "scientia-aggregator": 3},
        )
        with TemporaryDirectory() as td:
            summary = ac.apply_concurrency(
                config={
                    "hermes": {
                        "max_concurrent_children": 3,
                        "profile_names": {"implementer": "my-impl"},
                    },
                },
                repo_root=Path(td),
                runner=runner,
            )
        self.assertEqual(summary["implementer"]["profile"], "my-impl")
        for call in runner.calls:
            if "-p" in call:
                self.assertIn(call[call.index("-p") + 1],
                              {"my-impl", "scientia-reviewer",
                               "scientia-integrator", "scientia-aggregator"})

    def test_logs_per_target(self):
        runner = _make_runner(host_cap=None, profile_caps={})
        with TemporaryDirectory() as td:
            ac.apply_concurrency(
                config={"hermes": {"max_concurrent_children": 5}},
                repo_root=Path(td),
                runner=runner,
            )
            log = (Path(td) / "development" / "log.md").read_text()
        applied_lines = [
            l for l in log.splitlines() if "concurrency-applied" in l
        ]
        # Host + 4 roles.
        self.assertEqual(len(applied_lines), 5)
        self.assertTrue(any("target=host" in l for l in applied_lines))
        for role in ("implementer", "reviewer",
                     "integrator", "aggregator"):
            self.assertTrue(
                any(f"target={role}" in l for l in applied_lines),
                f"missing log line for {role}",
            )

    def test_rejects_non_positive_cap(self):
        runner = _make_runner()
        for bad in (0, -1, "3", 3.5, True, None):
            with TemporaryDirectory() as td:
                with self.assertRaises(ValueError):
                    ac.apply_concurrency(
                        config={"hermes": {"max_concurrent_children": bad}},
                        repo_root=Path(td),
                        runner=runner,
                    )

    def test_aborts_on_first_set_failure(self):
        runner = _make_runner(host_cap=None, fail_on=["host"])
        with TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError) as ctx:
                ac.apply_concurrency(
                    config={"hermes": {"max_concurrent_children": 5}},
                    repo_root=Path(td),
                    runner=runner,
                )
        self.assertIn("rejected host", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
