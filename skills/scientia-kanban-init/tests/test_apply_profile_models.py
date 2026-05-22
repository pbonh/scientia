"""Tests for scripts/apply_profile_models.py.

The shared validation/flatten/drift helpers are exercised in
scientia-kanban-emit/tests/test_profile_models.py. These tests focus on:
- apply_one_profile: skips matching keys, calls hermes config set for
  mismatches, aborts on first failure.
- apply_all: routes through profile_names overrides, writes log lines,
  handles hands-off when block is absent.
"""

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import List

from tests import _paths  # noqa: F401

import apply_profile_models as apm


def _make_runner(
    *,
    effective: dict,
    set_failures: List[str] | None = None,
):
    """Fake `subprocess.run`.

    - `hermes -p NAME config show --json` → JSON of `effective`.
    - `hermes -p NAME config set KEY VAL` → success unless KEY in
      `set_failures` (which makes returncode=1).
    Records every call in runner.calls.
    """
    set_failures = set_failures or []

    def runner(argv, **kw):
        runner.calls.append(list(argv))
        if "show" in argv:
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(effective), stderr="",
            )
        if "set" in argv:
            try:
                key = argv[argv.index("set") + 1]
            except (ValueError, IndexError):
                return SimpleNamespace(returncode=2, stdout="",
                                       stderr="malformed set call")
            if key in set_failures:
                return SimpleNamespace(
                    returncode=1, stdout="",
                    stderr=f"hermes rejected {key}",
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    runner.calls = []
    return runner


# ---------------------------------------------------------------------------
# apply_one_profile
# ---------------------------------------------------------------------------


class ApplyOneProfileTests(unittest.TestCase):
    def test_no_op_when_all_keys_already_match(self):
        runner = _make_runner(effective={
            "model": {"default": "claude-opus-4.7", "provider": "anthropic"},
        })
        applied, unchanged, errors = apm.apply_one_profile(
            role="implementer",
            profile_name="scientia-implementer",
            declared={
                "model.default": "claude-opus-4.7",
                "model.provider": "anthropic",
            },
            runner=runner,
        )
        self.assertEqual(applied, 0)
        self.assertEqual(unchanged, 2)
        self.assertEqual(errors, [])
        # Only the show call, no set calls.
        set_calls = [c for c in runner.calls if "set" in c]
        self.assertEqual(set_calls, [])

    def test_applies_mismatched_keys_only(self):
        runner = _make_runner(effective={
            "model": {"default": "claude-sonnet-4.6", "provider": "anthropic"},
        })
        applied, unchanged, errors = apm.apply_one_profile(
            role="implementer",
            profile_name="scientia-implementer",
            declared={
                "model.default": "claude-opus-4.7",      # mismatch
                "model.provider": "anthropic",            # already matches
            },
            runner=runner,
        )
        self.assertEqual(applied, 1)
        self.assertEqual(unchanged, 1)
        self.assertEqual(errors, [])
        set_calls = [c for c in runner.calls if "set" in c]
        self.assertEqual(len(set_calls), 1)
        self.assertIn("model.default", set_calls[0])
        self.assertIn("claude-opus-4.7", set_calls[0])

    def test_aborts_on_first_set_failure(self):
        runner = _make_runner(
            effective={"model": {"default": "old", "provider": "old"}},
            set_failures=["model.default"],
        )
        applied, unchanged, errors = apm.apply_one_profile(
            role="implementer",
            profile_name="scientia-implementer",
            declared={
                "model.default": "claude-opus-4.7",
                "model.provider": "anthropic",
            },
            runner=runner,
        )
        # Sorted dict iteration: model.default tries first, fails, abort
        # before model.provider is attempted.
        self.assertEqual(applied, 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("model.default", errors[0])
        self.assertIn("hermes rejected", errors[0])
        # Only one set call (the failing one).
        set_calls = [c for c in runner.calls if "set" in c]
        self.assertEqual(len(set_calls), 1)

    def test_includes_profile_name_in_hermes_argv(self):
        runner = _make_runner(effective={})
        apm.apply_one_profile(
            role="reviewer",
            profile_name="my-custom-reviewer",
            declared={"model.default": "claude-haiku-4.5"},
            runner=runner,
        )
        # Both show and set should have -p my-custom-reviewer
        for call in runner.calls:
            self.assertIn("-p", call)
            self.assertEqual(call[call.index("-p") + 1], "my-custom-reviewer")


# ---------------------------------------------------------------------------
# apply_all
# ---------------------------------------------------------------------------


class ApplyAllTests(unittest.TestCase):
    def test_hands_off_when_profiles_block_absent(self):
        runner = _make_runner(effective={})
        with TemporaryDirectory() as td:
            summary = apm.apply_all(
                config={"hermes": {"max_concurrent_children": 3}},
                repo_root=Path(td),
                runner=runner,
            )
            self.assertEqual(summary, {})
            log = (Path(td) / "development" / "log.md").read_text()
            self.assertIn("model-config-skipped", log)
            self.assertIn("hermes.profiles-absent", log)
        # No hermes calls at all.
        self.assertEqual(runner.calls, [])

    def test_applies_all_declared_roles(self):
        runner = _make_runner(effective={
            "model": {"default": "stale", "provider": "stale"},
        })
        config = {
            "hermes": {
                "profiles": {
                    "implementer": {"model": {"default": "claude-opus-4.7"}},
                    "reviewer": {"model": {"default": "claude-sonnet-4.6"}},
                },
            },
        }
        with TemporaryDirectory() as td:
            summary = apm.apply_all(
                config=config, repo_root=Path(td), runner=runner,
            )
            self.assertEqual(
                summary["implementer"]["profile"], "scientia-implementer"
            )
            self.assertEqual(
                summary["reviewer"]["profile"], "scientia-reviewer"
            )
            self.assertEqual(summary["implementer"]["applied"], 1)
            self.assertEqual(summary["reviewer"]["applied"], 1)
            # Log has one model-config-applied line per role.
            log = (Path(td) / "development" / "log.md").read_text().splitlines()
            applied_lines = [
                l for l in log if "model-config-applied" in l
            ]
            self.assertEqual(len(applied_lines), 2)

    def test_uses_profile_name_overrides(self):
        runner = _make_runner(effective={})
        config = {
            "hermes": {
                "profile_names": {"implementer": "my-impl"},
                "profiles": {
                    "implementer": {"model": {"default": "claude-opus-4.7"}},
                },
            },
        }
        with TemporaryDirectory() as td:
            summary = apm.apply_all(
                config=config, repo_root=Path(td), runner=runner,
            )
        self.assertEqual(summary["implementer"]["profile"], "my-impl")
        # All hermes calls should have -p my-impl
        for call in runner.calls:
            self.assertEqual(call[call.index("-p") + 1], "my-impl")

    def test_raises_on_set_failure(self):
        runner = _make_runner(
            effective={"model": {"default": "stale"}},
            set_failures=["model.default"],
        )
        config = {
            "hermes": {
                "profiles": {
                    "implementer": {"model": {"default": "claude-opus-4.7"}},
                },
            },
        }
        with TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError) as ctx:
                apm.apply_all(
                    config=config, repo_root=Path(td), runner=runner,
                )
        self.assertIn("model.default", str(ctx.exception))

    def test_raises_on_schema_error(self):
        config = {"hermes": {"profiles": {"badrole": {"model": {}}}}}
        with TemporaryDirectory() as td:
            with self.assertRaises(apm.ProfileConfigError):
                apm.apply_all(
                    config=config,
                    repo_root=Path(td),
                    runner=_make_runner(effective={}),
                )


# ---------------------------------------------------------------------------
# Custom-provider propagation integration
# ---------------------------------------------------------------------------


def _make_runner_with_host(
    *,
    effective: dict,
    host_custom_providers: list,
    set_failures: list | None = None,
):
    """Fake runner that also responds to host-level `hermes config show --json`.

    - `hermes config show --json` (no -p)           → host config JSON.
    - `hermes -p NAME config show --json`           → JSON of `effective`.
    - `hermes -p NAME config set KEY VAL`           → success unless KEY in
                                                      `set_failures`.
    """
    set_failures = set_failures or []

    def runner(argv, **kw):
        runner.calls.append(list(argv))
        has_profile_flag = "-p" in argv
        is_show = "show" in argv and "--json" in argv
        if is_show and not has_profile_flag:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"custom_providers": host_custom_providers}),
                stderr="",
            )
        if is_show:
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(effective), stderr="",
            )
        if "set" in argv:
            try:
                key = argv[argv.index("set") + 1]
            except (ValueError, IndexError):
                return SimpleNamespace(returncode=2, stdout="",
                                       stderr="malformed set call")
            if key in set_failures:
                return SimpleNamespace(
                    returncode=1, stdout="",
                    stderr=f"hermes rejected {key}",
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    runner.calls = []
    return runner


class ApplyAllCustomProviderPropagationTests(unittest.TestCase):
    HOST_PROVIDERS = [
        {
            "name": "fireworks",
            "base_url": "https://api.fireworks.ai/inference/v1",
            "key_env": "FIREWORKS_API_KEY",
            "api_mode": "chat_completions",
            "models": {
                "accounts/fireworks/models/glm-5p1": {"context_length": 131072},
                "accounts/fireworks/models/kimi-k2p6": {"context_length": 131072},
            },
        },
        {
            "name": "firepass",
            "base_url": "https://api.fireworks.ai/inference/v1",
            "key_env": "FIREWORKS_FIREPASS_API_KEY",
        },
    ]

    def test_propagates_when_role_references_custom_provider(self):
        runner = _make_runner_with_host(
            effective={},
            host_custom_providers=self.HOST_PROVIDERS,
        )
        config = {
            "hermes": {
                "profiles": {
                    "implementer": {
                        "model": {
                            "provider": "custom:fireworks",
                            "default": "accounts/fireworks/models/glm-5p1",
                        },
                    },
                },
            },
        }
        with TemporaryDirectory() as td:
            td_path = Path(td)
            profiles_root = td_path / "profiles"
            summary = apm.apply_all(
                config=config,
                repo_root=td_path,
                runner=runner,
                profiles_root=profiles_root,
            )

            # The propagation block lands in the profile config.yaml.
            cfg = profiles_root / "scientia-implementer" / "config.yaml"
            self.assertTrue(cfg.is_file())
            text = cfg.read_text(encoding="utf-8")
            self.assertIn("custom_providers:", text)
            self.assertIn("- name: fireworks", text)
            self.assertIn("key_env: FIREWORKS_API_KEY", text)
            self.assertIn("base_url: https://api.fireworks.ai/inference/v1", text)
            self.assertIn("api_mode: chat_completions", text)
            self.assertIn("context_length: 131072", text)
            # firepass NOT propagated — it wasn't referenced.
            self.assertNotIn("FIREWORKS_FIREPASS_API_KEY", text)

            # Summary records what was propagated.
            self.assertEqual(
                summary["implementer"]["propagated_custom_providers"],
                ["fireworks"],
            )

            # Log line for the propagation.
            log_text = (td_path / "development" / "log.md").read_text()
            self.assertIn("custom-providers-propagated", log_text)
            self.assertIn("providers=fireworks", log_text)

    def test_skips_host_lookup_when_no_custom_refs(self):
        # No custom: references → no host config read.
        runner = _make_runner_with_host(
            effective={},
            host_custom_providers=self.HOST_PROVIDERS,
        )
        config = {
            "hermes": {
                "profiles": {
                    "implementer": {
                        "model": {"provider": "anthropic", "default": "claude-opus-4.7"},
                    },
                },
            },
        }
        with TemporaryDirectory() as td:
            apm.apply_all(
                config=config,
                repo_root=Path(td),
                runner=runner,
                profiles_root=Path(td) / "profiles",
            )
        # No host config show (no -p, with show+--json) calls.
        host_calls = [
            c for c in runner.calls
            if "show" in c and "--json" in c and "-p" not in c
        ]
        self.assertEqual(host_calls, [])

    def test_raises_when_referenced_provider_missing_from_host(self):
        runner = _make_runner_with_host(
            effective={},
            host_custom_providers=[],  # host has none
        )
        config = {
            "hermes": {
                "profiles": {
                    "implementer": {
                        "model": {"provider": "custom:fireworks"},
                    },
                },
            },
        }
        with TemporaryDirectory() as td:
            with self.assertRaises(RuntimeError) as ctx:
                apm.apply_all(
                    config=config,
                    repo_root=Path(td),
                    runner=runner,
                    profiles_root=Path(td) / "profiles",
                )
            self.assertIn("fireworks", str(ctx.exception))
            self.assertIn("not in host config", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
