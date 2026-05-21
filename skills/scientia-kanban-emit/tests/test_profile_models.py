"""Tests for scripts/profile_models.py — per-profile Hermes model config.

Covers:
- validate_profiles: accepts valid schemas, rejects each invalid case with a
  documented error.
- flatten_profile: nested mapping → dotted-key map for model, auxiliary,
  and model_aliases blocks.
- resolve_profile_name: default vs override.
- detect_drift: empty / single-key / multi-key / multi-profile cases,
  including the `auto`/`''` equivalence semantics.
- check_profile_models_drift: end-to-end preflight gate behavior with a
  mocked `hermes config show --json` runner.
"""

import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests import _paths  # noqa: F401 — puts scripts/ on sys.path

import profile_models as pm


# ---------------------------------------------------------------------------
# validate_profiles
# ---------------------------------------------------------------------------


class ValidateProfilesTests(unittest.TestCase):
    def test_none_returns_empty_dict(self):
        self.assertEqual(pm.validate_profiles(None), {})

    def test_empty_dict_returns_empty_dict(self):
        self.assertEqual(pm.validate_profiles({}), {})

    def test_accepts_minimal_role(self):
        block = {"implementer": {"model": {"default": "claude-opus-4.7"}}}
        self.assertEqual(pm.validate_profiles(block), block)

    def test_accepts_all_four_roles(self):
        block = {
            "implementer": {"model": {"default": "x"}},
            "reviewer": {"model": {"default": "y"}},
            "integrator": {"model": {"default": "z"}},
            "aggregator": {"model": {"default": "w"}},
        }
        self.assertEqual(pm.validate_profiles(block), block)

    def test_accepts_partial_role_block(self):
        # Only auxiliary, no model or model_aliases.
        block = {"reviewer": {"auxiliary": {"compression": {"provider": "auto"}}}}
        self.assertEqual(pm.validate_profiles(block), block)

    def test_accepts_empty_role_block(self):
        # An empty role block is benign — flattens to nothing.
        block = {"implementer": {}}
        self.assertEqual(pm.validate_profiles(block), block)

    def test_accepts_null_role_block(self):
        block = {"implementer": None}
        self.assertEqual(pm.validate_profiles(block), block)

    def test_accepts_full_hermes_fidelity(self):
        block = {
            "implementer": {
                "model": {
                    "provider": "anthropic",
                    "default": "claude-opus-4.7",
                    "base_url": "",
                    "api_mode": "chat_completions",
                },
                "auxiliary": {
                    "compression": {"provider": "auto", "model": ""},
                    "vision": {"provider": "openrouter",
                               "model": "google/gemini-2.5-flash"},
                },
                "model_aliases": {
                    "fav": {"model": "claude-sonnet-4.6", "provider": "anthropic"},
                },
            },
        }
        self.assertEqual(pm.validate_profiles(block), block)

    def test_rejects_non_mapping_top_level(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles(["not", "a", "mapping"])
        self.assertIn("mapping", str(ctx.exception))

    def test_rejects_unknown_role(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles({"badrole": {"model": {"default": "x"}}})
        self.assertIn("badrole", str(ctx.exception))
        self.assertIn("unknown role", str(ctx.exception))

    def test_rejects_non_mapping_role_block(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles({"implementer": "claude-opus-4.7"})
        self.assertIn("implementer", str(ctx.exception))
        self.assertIn("mapping", str(ctx.exception))

    def test_rejects_unknown_top_level_key(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles({"implementer": {"temperature": 0.5}})
        self.assertIn("temperature", str(ctx.exception))

    def test_rejects_unknown_model_key(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles(
                {"implementer": {"model": {"top_p": 0.9}}}
            )
        self.assertIn("top_p", str(ctx.exception))

    def test_rejects_unknown_auxiliary_task(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles(
                {"implementer": {"auxiliary": {"made_up_task": {"provider": "x"}}}}
            )
        self.assertIn("made_up_task", str(ctx.exception))

    def test_rejects_unknown_auxiliary_task_key(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles(
                {"implementer": {
                    "auxiliary": {"vision": {"top_p": 0.9}},
                }}
            )
        self.assertIn("top_p", str(ctx.exception))

    def test_rejects_model_alias_missing_required_key(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles(
                {"implementer": {"model_aliases": {
                    "fav": {"model": "claude-sonnet-4.6"},
                }}}
            )
        self.assertIn("provider", str(ctx.exception))
        self.assertIn("fav", str(ctx.exception))

    def test_rejects_model_alias_with_extra_key(self):
        with self.assertRaises(pm.ProfileConfigError) as ctx:
            pm.validate_profiles(
                {"implementer": {"model_aliases": {
                    "fav": {"model": "x", "provider": "y", "temperature": 0.5},
                }}}
            )
        self.assertIn("temperature", str(ctx.exception))

    def test_rejects_non_mapping_model_alias_entry(self):
        with self.assertRaises(pm.ProfileConfigError):
            pm.validate_profiles(
                {"implementer": {"model_aliases": {"fav": "claude-sonnet-4.6"}}}
            )


# ---------------------------------------------------------------------------
# flatten_profile
# ---------------------------------------------------------------------------


class FlattenProfileTests(unittest.TestCase):
    def test_empty_block_is_empty_map(self):
        self.assertEqual(pm.flatten_profile({}), {})

    def test_flattens_model_block(self):
        flat = pm.flatten_profile({"model": {
            "provider": "anthropic",
            "default": "claude-opus-4.7",
        }})
        self.assertEqual(flat, {
            "model.provider": "anthropic",
            "model.default": "claude-opus-4.7",
        })

    def test_flattens_auxiliary_block(self):
        flat = pm.flatten_profile({"auxiliary": {
            "vision": {"provider": "openrouter",
                       "model": "google/gemini-2.5-flash"},
        }})
        self.assertEqual(flat, {
            "auxiliary.vision.provider": "openrouter",
            "auxiliary.vision.model": "google/gemini-2.5-flash",
        })

    def test_flattens_model_aliases(self):
        flat = pm.flatten_profile({"model_aliases": {
            "fav": {"model": "claude-sonnet-4.6", "provider": "anthropic"},
        }})
        self.assertEqual(flat, {
            "model_aliases.fav.model": "claude-sonnet-4.6",
            "model_aliases.fav.provider": "anthropic",
        })

    def test_stringifies_none_as_empty_quoted(self):
        flat = pm.flatten_profile({"model": {"base_url": None}})
        self.assertEqual(flat, {"model.base_url": "''"})

    def test_stringifies_empty_string_as_empty_quoted(self):
        flat = pm.flatten_profile({"model": {"base_url": ""}})
        self.assertEqual(flat, {"model.base_url": "''"})

    def test_stringifies_bool_and_int(self):
        flat = pm.flatten_profile({"auxiliary": {
            "vision": {"timeout": 120, "extra_body": False},
        }})
        self.assertEqual(flat["auxiliary.vision.timeout"], "120")
        self.assertEqual(flat["auxiliary.vision.extra_body"], "false")


# ---------------------------------------------------------------------------
# resolve_profile_name
# ---------------------------------------------------------------------------


class ResolveProfileNameTests(unittest.TestCase):
    def test_default_when_no_overrides(self):
        self.assertEqual(
            pm.resolve_profile_name("implementer", None),
            "scientia-implementer",
        )

    def test_default_when_role_not_in_overrides(self):
        self.assertEqual(
            pm.resolve_profile_name(
                "reviewer", {"implementer": "my-impl"}
            ),
            "scientia-reviewer",
        )

    def test_uses_override(self):
        self.assertEqual(
            pm.resolve_profile_name(
                "implementer", {"implementer": "my-impl"}
            ),
            "my-impl",
        )

    def test_falsy_override_falls_back_to_default(self):
        # E.g. user wrote `implementer:` with no value → null.
        self.assertEqual(
            pm.resolve_profile_name("implementer", {"implementer": None}),
            "scientia-implementer",
        )

    def test_rejects_unknown_role(self):
        with self.assertRaises(pm.ProfileConfigError):
            pm.resolve_profile_name("ghost", None)


# ---------------------------------------------------------------------------
# detect_drift
# ---------------------------------------------------------------------------


class DetectDriftTests(unittest.TestCase):
    def test_empty_when_all_match(self):
        declared = {"model.default": "claude-opus-4.7"}
        effective = {"model.default": "claude-opus-4.7", "extra": "ignored"}
        self.assertEqual(pm.detect_drift(declared=declared, effective=effective), [])

    def test_single_key_mismatch(self):
        declared = {"model.default": "claude-opus-4.7"}
        effective = {"model.default": "anthropic/claude-sonnet-4.6"}
        drift = pm.detect_drift(declared=declared, effective=effective)
        self.assertEqual(drift, [(
            "model.default", "claude-opus-4.7", "anthropic/claude-sonnet-4.6",
        )])

    def test_missing_key_in_effective_is_drift(self):
        declared = {"model.default": "claude-opus-4.7"}
        effective = {}
        drift = pm.detect_drift(declared=declared, effective=effective)
        self.assertEqual(drift, [("model.default", "claude-opus-4.7", "<missing>")])

    def test_auto_and_empty_treated_as_equivalent(self):
        # Hermes accepts both `auto` and `''` as "let main pick" — they
        # should not register as drift against each other.
        declared = {"auxiliary.compression.provider": "auto"}
        effective = {"auxiliary.compression.provider": "''"}
        self.assertEqual(pm.detect_drift(declared=declared, effective=effective), [])

        declared = {"auxiliary.compression.provider": "''"}
        effective = {"auxiliary.compression.provider": "auto"}
        self.assertEqual(pm.detect_drift(declared=declared, effective=effective), [])

    def test_multiple_keys_all_reported(self):
        declared = {
            "model.default": "claude-opus-4.7",
            "model.provider": "anthropic",
        }
        effective = {
            "model.default": "claude-sonnet-4.6",
            "model.provider": "openrouter",
        }
        drift = pm.detect_drift(declared=declared, effective=effective)
        self.assertEqual(len(drift), 2)


# ---------------------------------------------------------------------------
# format_drift_reason
# ---------------------------------------------------------------------------


class FormatDriftReasonTests(unittest.TestCase):
    def test_includes_role_profile_and_keys(self):
        msg = pm.format_drift_reason(
            role="implementer",
            profile_name="scientia-implementer",
            drift=[
                ("model.default", "claude-opus-4.7", "claude-sonnet-4.6"),
                ("model.provider", "anthropic", "openrouter"),
            ],
        )
        self.assertIn("scientia-implementer", msg)
        self.assertIn("role=implementer", msg)
        self.assertIn("model.default", msg)
        self.assertIn("model.provider", msg)
        self.assertIn("claude-opus-4.7", msg)
        self.assertIn("re-run scientia-kanban-init", msg)


# ---------------------------------------------------------------------------
# check_profile_models_drift — end-to-end
# ---------------------------------------------------------------------------


def _make_runner(per_profile_config: dict):
    """Fake `subprocess.run` that returns a JSON-encoded config per profile.

    Maps `hermes -p <name> config show --json` → `per_profile_config[name]`.
    Unknown profiles return non-zero with a stub error message.
    """
    def runner(argv, **kw):
        try:
            idx = argv.index("-p")
            name = argv[idx + 1]
        except (ValueError, IndexError):
            return SimpleNamespace(returncode=2, stdout="", stderr="missing -p")
        if name not in per_profile_config:
            return SimpleNamespace(
                returncode=1, stdout="",
                stderr=f"profile {name} not found",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(per_profile_config[name]),
            stderr="",
        )
    return runner


class CheckProfileModelsDriftTests(unittest.TestCase):
    def test_passes_when_block_absent(self):
        runner = MagicMock()  # should not be called
        self.assertIsNone(pm.check_profile_models_drift(
            profiles_block=None, profile_names=None, runner=runner,
        ))
        runner.assert_not_called()

    def test_passes_when_block_empty(self):
        runner = MagicMock()
        self.assertIsNone(pm.check_profile_models_drift(
            profiles_block={}, profile_names=None, runner=runner,
        ))
        runner.assert_not_called()

    def test_passes_when_all_declared_keys_match(self):
        runner = _make_runner({
            "scientia-implementer": {
                "model": {"default": "claude-opus-4.7", "provider": "anthropic"},
                "auxiliary": {"vision": {"provider": "openrouter"}},
            },
        })
        block = {
            "implementer": {
                "model": {"default": "claude-opus-4.7"},
                "auxiliary": {"vision": {"provider": "openrouter"}},
            },
        }
        self.assertIsNone(pm.check_profile_models_drift(
            profiles_block=block, profile_names=None, runner=runner,
        ))

    def test_refuses_on_single_key_drift(self):
        runner = _make_runner({
            "scientia-implementer": {
                "model": {"default": "claude-sonnet-4.6"},
            },
        })
        block = {"implementer": {"model": {"default": "claude-opus-4.7"}}}
        reason = pm.check_profile_models_drift(
            profiles_block=block, profile_names=None, runner=runner,
        )
        self.assertIsNotNone(reason)
        self.assertIn("scientia-implementer", reason)
        self.assertIn("model.default", reason)
        self.assertIn("claude-opus-4.7", reason)
        self.assertIn("claude-sonnet-4.6", reason)

    def test_uses_profile_name_override(self):
        runner = _make_runner({
            "my-impl": {"model": {"default": "claude-opus-4.7"}},
        })
        block = {"implementer": {"model": {"default": "claude-opus-4.7"}}}
        # scientia-implementer profile doesn't exist in this fixture; only
        # my-impl does, so the override must be applied for the call to
        # find the profile.
        self.assertIsNone(pm.check_profile_models_drift(
            profiles_block=block,
            profile_names={"implementer": "my-impl"},
            runner=runner,
        ))

    def test_multiple_roles_each_reported(self):
        runner = _make_runner({
            "scientia-implementer": {"model": {"default": "wrong-1"}},
            "scientia-reviewer": {"model": {"default": "wrong-2"}},
        })
        block = {
            "implementer": {"model": {"default": "right-1"}},
            "reviewer": {"model": {"default": "right-2"}},
        }
        reason = pm.check_profile_models_drift(
            profiles_block=block, profile_names=None, runner=runner,
        )
        self.assertIsNotNone(reason)
        self.assertIn("scientia-implementer", reason)
        self.assertIn("scientia-reviewer", reason)

    def test_undeclared_keys_are_not_drift(self):
        # Hermes returns many keys; we only care about those scientia declares.
        runner = _make_runner({
            "scientia-implementer": {
                "model": {"default": "claude-opus-4.7"},
                "auxiliary": {
                    "vision": {"provider": "openrouter"},
                    "compression": {"provider": "anthropic"},  # not declared
                },
                "session": {"keep_history": True},  # whole undeclared subtree
            },
        })
        block = {"implementer": {"model": {"default": "claude-opus-4.7"}}}
        self.assertIsNone(pm.check_profile_models_drift(
            profiles_block=block, profile_names=None, runner=runner,
        ))

    def test_surfaces_hermes_read_failure(self):
        # Profile not in fixture → runner returns non-zero.
        runner = _make_runner({})
        block = {"implementer": {"model": {"default": "claude-opus-4.7"}}}
        reason = pm.check_profile_models_drift(
            profiles_block=block, profile_names=None, runner=runner,
        )
        self.assertIsNotNone(reason)
        self.assertIn("cannot read effective config", reason)
        self.assertIn("scientia-implementer", reason)

    def test_invalid_block_raises(self):
        with self.assertRaises(pm.ProfileConfigError):
            pm.check_profile_models_drift(
                profiles_block={"badrole": {"model": {"default": "x"}}},
                profile_names=None,
                runner=lambda *a, **kw: SimpleNamespace(
                    returncode=0, stdout="{}", stderr=""
                ),
            )


if __name__ == "__main__":
    unittest.main()
