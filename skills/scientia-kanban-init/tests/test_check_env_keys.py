"""Tests for scripts/check_env_keys.py — API key reachability preflight."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Dict, List

from tests import _paths  # noqa: F401

import check_env_keys as cek


HOST_PROVIDERS = [
    {
        "name": "fireworks",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "key_env": "FIREWORKS_API_KEY",
        "api_mode": "chat_completions",
        "models": {
            "accounts/fireworks/models/glm-5p1": {"context_length": 131072},
        },
    },
    {
        "name": "firepass",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "key_env": "FIREWORKS_FIREPASS_API_KEY",
    },
    {
        # Keyless local server — no key_env. Should be skipped.
        "name": "local",
        "base_url": "http://localhost:8080/v1",
    },
]


def _host_runner(providers: List[dict] | None = None):
    payload = {"custom_providers": providers if providers is not None
               else HOST_PROVIDERS}

    def runner(argv, **_kw):
        runner.calls.append(list(argv))
        return SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr="",
        )
    runner.calls = []
    return runner


def _write_env(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# read_dotenv_keys
# ---------------------------------------------------------------------------


class ReadDotenvKeysTests(unittest.TestCase):
    def test_returns_empty_when_file_missing(self):
        with TemporaryDirectory() as td:
            self.assertEqual(
                cek.read_dotenv_keys(Path(td) / "nope.env"), set(),
            )

    def test_picks_up_simple_assignments(self):
        with TemporaryDirectory() as td:
            p = Path(td) / ".env"
            _write_env(p, ["FOO=bar", "BAZ=qux"])
            self.assertEqual(cek.read_dotenv_keys(p), {"FOO", "BAZ"})

    def test_ignores_comments_and_blank_lines(self):
        with TemporaryDirectory() as td:
            p = Path(td) / ".env"
            _write_env(p, ["# comment", "", "FOO=bar", "  ", "# BAZ=skip"])
            self.assertEqual(cek.read_dotenv_keys(p), {"FOO"})

    def test_strips_export_prefix(self):
        with TemporaryDirectory() as td:
            p = Path(td) / ".env"
            _write_env(p, ["export FIREWORKS_API_KEY=abc"])
            self.assertEqual(
                cek.read_dotenv_keys(p), {"FIREWORKS_API_KEY"},
            )

    def test_ignores_lines_without_equals(self):
        with TemporaryDirectory() as td:
            p = Path(td) / ".env"
            _write_env(p, ["FOO=bar", "INVALID_LINE_NO_EQUALS"])
            self.assertEqual(cek.read_dotenv_keys(p), {"FOO"})


# ---------------------------------------------------------------------------
# collect_required_env_keys
# ---------------------------------------------------------------------------


class CollectRequiredEnvKeysTests(unittest.TestCase):
    def test_empty_block_returns_empty(self):
        self.assertEqual(
            cek.collect_required_env_keys(
                profiles_block={},
                profile_names=None,
                host_providers=HOST_PROVIDERS,
            ),
            {},
        )

    def test_picks_up_model_provider_ref(self):
        block = {
            "implementer": {
                "model": {"provider": "custom:fireworks", "default": "x"},
            },
        }
        result = cek.collect_required_env_keys(
            profiles_block=block,
            profile_names=None,
            host_providers=HOST_PROVIDERS,
        )
        self.assertEqual(
            result, {"FIREWORKS_API_KEY": ["scientia-implementer"]}
        )

    def test_aggregates_across_roles(self):
        block = {
            "implementer": {
                "model": {"provider": "custom:fireworks"},
            },
            "reviewer": {
                "model": {"provider": "custom:fireworks"},
            },
            "integrator": {
                "model": {"provider": "custom:firepass"},
            },
        }
        result = cek.collect_required_env_keys(
            profiles_block=block,
            profile_names=None,
            host_providers=HOST_PROVIDERS,
        )
        self.assertEqual(
            set(result.keys()),
            {"FIREWORKS_API_KEY", "FIREWORKS_FIREPASS_API_KEY"},
        )
        self.assertEqual(
            sorted(result["FIREWORKS_API_KEY"]),
            ["scientia-implementer", "scientia-reviewer"],
        )
        self.assertEqual(
            result["FIREWORKS_FIREPASS_API_KEY"],
            ["scientia-integrator"],
        )

    def test_skips_keyless_providers(self):
        # `local` has no key_env — should be omitted.
        block = {"implementer": {"model": {"provider": "custom:local"}}}
        self.assertEqual(
            cek.collect_required_env_keys(
                profiles_block=block,
                profile_names=None,
                host_providers=HOST_PROVIDERS,
            ),
            {},
        )

    def test_skips_unknown_providers(self):
        # Propagation step will refuse loudly; this gate is silent.
        block = {"implementer": {"model": {"provider": "custom:nonexistent"}}}
        self.assertEqual(
            cek.collect_required_env_keys(
                profiles_block=block,
                profile_names=None,
                host_providers=HOST_PROVIDERS,
            ),
            {},
        )

    def test_respects_profile_name_overrides(self):
        block = {"implementer": {"model": {"provider": "custom:fireworks"}}}
        result = cek.collect_required_env_keys(
            profiles_block=block,
            profile_names={"implementer": "my-impl"},
            host_providers=HOST_PROVIDERS,
        )
        self.assertEqual(result["FIREWORKS_API_KEY"], ["my-impl"])

    def test_walks_auxiliary_and_aliases(self):
        block = {
            "reviewer": {
                "auxiliary": {
                    "compression": {"provider": "custom:fireworks"},
                },
                "model_aliases": {
                    "fav": {"provider": "custom:firepass", "model": "m"},
                },
            },
        }
        result = cek.collect_required_env_keys(
            profiles_block=block,
            profile_names=None,
            host_providers=HOST_PROVIDERS,
        )
        self.assertEqual(
            set(result.keys()),
            {"FIREWORKS_API_KEY", "FIREWORKS_FIREPASS_API_KEY"},
        )


# ---------------------------------------------------------------------------
# check_env_keys (end-to-end)
# ---------------------------------------------------------------------------


class CheckEnvKeysTests(unittest.TestCase):
    BASE_CONFIG = {
        "hermes": {
            "profiles": {
                "implementer": {"model": {"provider": "custom:fireworks"}},
                "reviewer": {"model": {"provider": "custom:firepass"}},
            },
        },
    }

    def test_returns_none_when_profiles_absent(self):
        runner = _host_runner()
        result = cek.check_env_keys(
            config={"hermes": {}},
            runner=runner,
            environ={},
        )
        self.assertIsNone(result)
        # No host lookup needed when there's no profiles block.
        self.assertEqual(runner.calls, [])

    def test_returns_none_when_keys_in_process_env(self):
        runner = _host_runner()
        with TemporaryDirectory() as td:
            result = cek.check_env_keys(
                config=self.BASE_CONFIG,
                runner=runner,
                environ={
                    "FIREWORKS_API_KEY": "x",
                    "FIREWORKS_FIREPASS_API_KEY": "y",
                },
                hermes_home=Path(td),
                profiles_root=Path(td) / "profiles",
            )
        self.assertIsNone(result)

    def test_returns_none_when_keys_in_host_env(self):
        runner = _host_runner()
        with TemporaryDirectory() as td:
            home = Path(td)
            _write_env(home / ".env", [
                "FIREWORKS_API_KEY=x",
                "FIREWORKS_FIREPASS_API_KEY=y",
            ])
            result = cek.check_env_keys(
                config=self.BASE_CONFIG,
                runner=runner,
                environ={},
                hermes_home=home,
                profiles_root=home / "profiles",
            )
        self.assertIsNone(result)

    def test_returns_none_when_keys_in_profile_env(self):
        runner = _host_runner()
        with TemporaryDirectory() as td:
            home = Path(td)
            roots = home / "profiles"
            _write_env(roots / "scientia-implementer" / ".env", [
                "FIREWORKS_API_KEY=x",
            ])
            _write_env(roots / "scientia-reviewer" / ".env", [
                "FIREWORKS_FIREPASS_API_KEY=y",
            ])
            result = cek.check_env_keys(
                config=self.BASE_CONFIG,
                runner=runner,
                environ={},
                hermes_home=home,
                profiles_root=roots,
            )
        self.assertIsNone(result)

    def test_refuses_when_key_missing_everywhere(self):
        runner = _host_runner()
        with TemporaryDirectory() as td:
            home = Path(td)
            result = cek.check_env_keys(
                config=self.BASE_CONFIG,
                runner=runner,
                environ={},
                hermes_home=home,
                profiles_root=home / "profiles",
            )
        self.assertIsNotNone(result)
        # Both missing keys appear in the refusal.
        self.assertIn("FIREWORKS_API_KEY", result)
        self.assertIn("FIREWORKS_FIREPASS_API_KEY", result)
        # Profile names attributed to each.
        self.assertIn("scientia-implementer", result)
        self.assertIn("scientia-reviewer", result)
        # Remediation hint.
        self.assertIn("~/.hermes/.env", result)
        self.assertIn("scientia does not manage secrets", result)

    def test_refusal_lists_only_actually_missing(self):
        runner = _host_runner()
        with TemporaryDirectory() as td:
            home = Path(td)
            # Only the FIREWORKS_API_KEY is reachable (via host .env).
            _write_env(home / ".env", ["FIREWORKS_API_KEY=x"])
            result = cek.check_env_keys(
                config=self.BASE_CONFIG,
                runner=runner,
                environ={},
                hermes_home=home,
                profiles_root=home / "profiles",
            )
        self.assertIsNotNone(result)
        self.assertNotIn("FIREWORKS_API_KEY (needed", result)
        self.assertIn("FIREWORKS_FIREPASS_API_KEY", result)

    def test_keyless_providers_do_not_require_anything(self):
        # A profile referencing the keyless `local` provider yields no
        # required keys, so the gate passes even with empty env.
        runner = _host_runner()
        with TemporaryDirectory() as td:
            home = Path(td)
            result = cek.check_env_keys(
                config={
                    "hermes": {
                        "profiles": {
                            "implementer": {
                                "model": {"provider": "custom:local"},
                            },
                        },
                    },
                },
                runner=runner,
                environ={},
                hermes_home=home,
                profiles_root=home / "profiles",
            )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
