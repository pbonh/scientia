"""Tests for per-profile model configuration (ProfileModel).

Covers:
  - ProfileModel dataclass construction and defaults
  - Model resolution in build_plan (per-profile override, default fallback, None)
  - Model inclusion in REST/CLI render payloads
  - Preflight checks for provider, model id, and api_key_env
  - Validator checks for provider, model id, temperature, max_tokens
  - Config.yaml parsing sanity
"""

from pathlib import Path

import pytest

from scientia.hermes import parse, preflight, render, validators
from scientia.hermes.plan import (
    CardSpec,
    CycleError,
    EmitPlan,
    PlanOptions,
    ProfileModel,
    Routing,
    TaskRouting,
    build_plan,
)

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"
CID = "test-change"

# --------------------------------------------------------------------------- #
# ProfileModel dataclass                                                       #
# --------------------------------------------------------------------------- #


class TestProfileModelDataclass:
    def test_defaults_to_fireworks_provider(self):
        pm = ProfileModel(model="llama-v3p1-70b-instruct")
        assert pm.provider == "fireworks"
        assert pm.model == "llama-v3p1-70b-instruct"
        assert pm.base_url is None
        assert pm.api_key_env is None
        assert pm.temperature is None
        assert pm.max_tokens is None

    def test_fully_specified(self):
        pm = ProfileModel(
            provider="openai",
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            temperature=0.7,
            max_tokens=4096,
        )
        assert pm.provider == "openai"
        assert pm.model == "gpt-4o"
        assert pm.base_url == "https://api.openai.com/v1"
        assert pm.api_key_env == "OPENAI_API_KEY"
        assert pm.temperature == 0.7
        assert pm.max_tokens == 4096

    def test_frozen(self):
        pm = ProfileModel(provider="fireworks", model="m")
        with pytest.raises(AttributeError):
            pm.provider = "openai"

    def test_anthropic_provider(self):
        pm = ProfileModel(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key_env="ANTHROPIC_API_KEY",
            temperature=0.2,
            max_tokens=8192,
        )
        assert pm.provider == "anthropic"


# --------------------------------------------------------------------------- #
# Model resolution in build_plan                                              #
# --------------------------------------------------------------------------- #

def _simple_tasks():
    return parse.parse_tasks(
        "- [ ] **1.** a <!-- traces-spec: c#s -->\n"
        "- [ ] **2.** b (depends on #1) <!-- traces-spec: c#s -->\n"
    )


def _plan_with_models(routing, options=None):
    tasks = _simple_tasks()
    return build_plan(
        CID, tasks, [], parse.ComponentMap({}), [],
        routing, options or PlanOptions(conflict_prevention=False, emit_epic=False),
    )


FIREWORKS_IMPL = ProfileModel(
    provider="fireworks",
    model="accounts/fireworks/models/llama-v3p1-70b-instruct",
    base_url="https://api.fireworks.ai/inference/v1",
    api_key_env="FIREWORKS_API_KEY",
    temperature=0.1,
    max_tokens=8192,
)

FIREWORKS_REV = ProfileModel(
    provider="fireworks",
    model="accounts/fireworks/models/qwen2p5-72b-instruct",
    base_url="https://api.fireworks.ai/inference/v1",
    api_key_env="FIREWORKS_API_KEY",
    temperature=0.3,
    max_tokens=4096,
)

OPENAI_DEFAULT = ProfileModel(
    provider="openai",
    model="gpt-4o",
    api_key_env="OPENAI_API_KEY",
    temperature=0.2,
    max_tokens=4096,
)


class TestModelResolution:
    def test_no_model_config_produces_none_on_cards(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
        )
        plan = _plan_with_models(routing)
        for card in plan.cards:
            assert card.model is None

    def test_default_model_applies_to_all_profiles(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            default_model=OPENAI_DEFAULT,
        )
        plan = _plan_with_models(routing)
        for card in plan.cards:
            assert card.model is not None
            assert card.model.provider == "openai"
            assert card.model.model == "gpt-4o"

    def test_per_profile_model_overrides_default(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": FIREWORKS_IMPL,
                "reviewer": FIREWORKS_REV,
            },
            default_model=OPENAI_DEFAULT,
        )
        plan = _plan_with_models(routing)
        by_stage = {c.stage: c for c in plan.cards}
        # implementer card uses the fireworks override
        assert by_stage["impl"].model.provider == "fireworks"
        assert by_stage["impl"].model.model == "accounts/fireworks/models/llama-v3p1-70b-instruct"
        assert by_stage["impl"].model.temperature == 0.1
        # reviewer card uses its own fireworks override
        assert by_stage["review"].model.provider == "fireworks"
        assert by_stage["review"].model.model == "accounts/fireworks/models/qwen2p5-72b-instruct"
        # integrator falls through to the openai default
        assert by_stage["integrate"].model.provider == "openai"

    def test_per_profile_model_without_default(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": FIREWORKS_IMPL,
            },
        )
        plan = _plan_with_models(routing)
        by_stage = {c.stage: c for c in plan.cards}
        assert by_stage["impl"].model == FIREWORKS_IMPL
        assert by_stage["review"].model is None
        assert by_stage["integrate"].model is None

    def test_profile_model_with_empty_model_string_falls_to_default(self):
        """A profile_models entry with model="" means 'use the default'."""
        empty = ProfileModel(provider="fireworks", model="")
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={"implementer": empty},
            default_model=OPENAI_DEFAULT,
        )
        plan = _plan_with_models(routing)
        impl = next(c for c in plan.cards if c.stage == "impl")
        assert impl.model == OPENAI_DEFAULT

    def test_epic_gets_default_model_when_unassigned(self):
        tasks = _simple_tasks()
        c4, comp_map, contracts = parse.parse_design((FIX / "design.md").read_text())
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            default_model=OPENAI_DEFAULT,
        )
        plan = build_plan(
            CID, tasks, c4, comp_map, contracts,
            routing, PlanOptions(conflict_prevention=False, emit_epic=True),
        )
        # epic has no assignee, so it gets default_model
        assert plan.epic is not None
        assert plan.epic.model == OPENAI_DEFAULT

    def test_epic_gets_profile_model_when_assigned(self):
        tasks = _simple_tasks()
        c4, comp_map, contracts = parse.parse_design((FIX / "design.md").read_text())
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            epic_assignee="implementer",
            profile_models={"implementer": FIREWORKS_IMPL},
        )
        plan = build_plan(
            CID, tasks, c4, comp_map, contracts,
            routing, PlanOptions(conflict_prevention=False, emit_epic=True),
        )
        assert plan.epic is not None
        assert plan.epic.model == FIREWORKS_IMPL

    def test_multi_vendor_routing(self):
        """Different profiles can use different vendors simultaneously."""
        anthropic_rev = ProfileModel(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key_env="ANTHROPIC_API_KEY",
            temperature=0.2,
            max_tokens=4096,
        )
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": FIREWORKS_IMPL,
                "reviewer": anthropic_rev,
                "integrator": OPENAI_DEFAULT,
            },
        )
        plan = _plan_with_models(routing)
        by_stage = {c.stage: c for c in plan.cards}
        assert by_stage["impl"].model.provider == "fireworks"
        assert by_stage["review"].model.provider == "anthropic"
        assert by_stage["integrate"].model.provider == "openai"


# --------------------------------------------------------------------------- #
# Render — model in payloads                                                  #
# --------------------------------------------------------------------------- #


class TestRenderModelPayload:
    def test_task_payload_includes_model_when_present(self):
        card = CardSpec(
            key="k", title="t", body="b", assignee="a",
            parents=(), tenant=None, workspace="worktree",
            branch=None, skills=(), priority=None, stage="impl",
            model=ProfileModel(
                provider="fireworks",
                model="accounts/fireworks/models/llama-v3p1-70b-instruct",
                base_url="https://api.fireworks.ai/inference/v1",
                api_key_env="FIREWORKS_API_KEY",
                temperature=0.1,
                max_tokens=8192,
            ),
        )
        payload = render.task_payload(card)
        assert "model" in payload
        m = payload["model"]
        assert m["provider"] == "fireworks"
        assert m["model"] == "accounts/fireworks/models/llama-v3p1-70b-instruct"
        assert m["base_url"] == "https://api.fireworks.ai/inference/v1"
        assert m["api_key_env"] == "FIREWORKS_API_KEY"
        assert m["temperature"] == 0.1
        assert m["max_tokens"] == 8192

    def test_task_payload_omits_model_when_absent(self):
        card = CardSpec(
            key="k", title="t", body="b", assignee="a",
            parents=(), tenant=None, workspace="worktree",
            branch=None, skills=(), priority=None, stage="impl",
        )
        payload = render.task_payload(card)
        assert "model" not in payload

    def test_task_payload_model_omits_none_fields(self):
        card = CardSpec(
            key="k", title="t", body="b", assignee="a",
            parents=(), tenant=None, workspace="worktree",
            branch=None, skills=(), priority=None, stage="impl",
            model=ProfileModel(provider="fireworks", model="m"),
        )
        payload = render.task_payload(card)
        m = payload["model"]
        assert m == {"provider": "fireworks", "model": "m"}

    def test_rest_ops_include_model_in_create(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={"implementer": FIREWORKS_IMPL},
        )
        plan = _plan_with_models(routing)
        id_for = lambda k: "H0"
        ops = render.to_rest(plan, id_for)
        creates = [o for o in ops if o["path"] == "/tasks"]
        impl_create = next(
            o for o in creates
            if o["json"]["idempotency_key"].endswith(":impl")
        )
        assert "model" in impl_create["json"]
        assert impl_create["json"]["model"]["provider"] == "fireworks"

    def test_cli_argv_drops_model_flags_model_is_profile_level(self):
        # v0.15.1 `hermes kanban create` has NO model flags. A card's model rides
        # on the assignee *profile* (provisioned by scientia-hermes-init), so the
        # CLI backend must not try to set it per-task — even when one is present.
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={"implementer": FIREWORKS_IMPL},
        )
        plan = _plan_with_models(routing)
        id_for = lambda k: "H0"
        argv = render.to_cli(plan, id_for)
        creates = [a for a in argv if "create" in a and "--idempotency-key" in a]
        assert creates
        for a in creates:
            assert not any(tok.startswith("--model") for tok in a)
        # REST, by contrast, still carries the model (see test_rest_ops_include_model_in_create).

    def test_cli_argv_omits_model_flags_when_no_model(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
        )
        plan = _plan_with_models(routing)
        id_for = lambda k: "H0"
        argv = render.to_cli(plan, id_for)
        for a in argv:
            if "create" in a and "--idempotency-key" in a:
                assert not any(tok.startswith("--model") for tok in a)


# --------------------------------------------------------------------------- #
# Preflight — model validation                                                #
# --------------------------------------------------------------------------- #


class TestPreflightModelChecks:
    def _plan_with_model(self, model, assignee="implementer"):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={assignee: model} if model else {},
        )
        return _plan_with_models(routing)

    def test_plan_with_valid_model_passes(self, monkeypatch):
        monkeypatch.setenv("FIREWORKS_API_KEY", "test-key")
        plan = self._plan_with_model(FIREWORKS_IMPL)
        res = preflight.check(plan, require_gateway=False)
        assert res.ok, res.errors

    def test_missing_api_key_env_fails(self):
        plan = self._plan_with_model(ProfileModel(
            provider="fireworks",
            model="m",
            api_key_env="NONEXISTENT_API_KEY_12345",
        ))
        res = preflight.check(plan, require_gateway=False)
        assert not res.ok
        assert any("NONEXISTENT_API_KEY_12345" in e for e in res.errors)

    def test_api_key_env_present_passes(self, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "x")
        plan = self._plan_with_model(ProfileModel(
            provider="fireworks",
            model="m",
            api_key_env="MY_API_KEY",
        ))
        res = preflight.check(plan, require_gateway=False)
        assert res.ok, res.errors

    def test_model_without_api_key_env_passes(self):
        plan = self._plan_with_model(ProfileModel(
            provider="fireworks",
            model="m",
        ))
        res = preflight.check(plan, require_gateway=False)
        assert res.ok, res.errors

    def test_empty_model_identifier_not_flagged_by_preflight(self):
        """An empty model string causes fallback to default; if default is None
        the card simply has no model, which preflight allows.  The empty string
        is caught by validators.validate_routing instead."""
        plan = self._plan_with_model(ProfileModel(
            provider="fireworks",
            model="",
        ))
        res = preflight.check(plan, require_gateway=False)
        assert res.ok  # preflight sees no model on the card (fell through to None)

    def test_unknown_provider_warns(self):
        plan = self._plan_with_model(ProfileModel(
            provider="acme-llm",
            model="supermodel-v1",
        ))
        res = preflight.check(plan, require_gateway=False)
        # Unknown provider is a warning, not an error
        assert res.ok
        assert any("acme-llm" in w for w in res.warnings)

    def test_missing_api_key_deduplicates(self):
        """Two cards sharing the same api_key_env should produce one error."""
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(
                    provider="fireworks", model="m1",
                    api_key_env="SHARED_MISSING_KEY",
                ),
                "reviewer": ProfileModel(
                    provider="fireworks", model="m2",
                    api_key_env="SHARED_MISSING_KEY",
                ),
            },
        )
        plan = _plan_with_models(routing)
        res = preflight.check(plan, require_gateway=False)
        key_errors = [e for e in res.errors if "SHARED_MISSING_KEY" in e]
        assert len(key_errors) == 1  # deduplicated

    def test_no_model_config_skips_model_checks(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
        )
        plan = _plan_with_models(routing)
        res = preflight.check(plan, require_gateway=False)
        assert res.ok


# --------------------------------------------------------------------------- #
# Validators — model reference checks                                         #
# --------------------------------------------------------------------------- #


class TestValidatorModelChecks:
    def test_valid_profile_models_pass(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": FIREWORKS_IMPL,
                "reviewer": FIREWORKS_REV,
            },
        )
        errors = validators.validate_routing(routing, [])
        assert not any("model" in e for e in errors)

    def test_empty_model_identifier_in_profile_fails(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(provider="fireworks", model=""),
            },
        )
        errors = validators.validate_routing(routing, [])
        assert any("no model identifier" in e for e in errors)

    def test_unknown_provider_in_profile_fails(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(provider="acme-llm", model="v1"),
            },
        )
        errors = validators.validate_routing(routing, [])
        assert any("acme-llm" in e and "known set" in e for e in errors)

    def test_temperature_out_of_range_fails(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(
                    provider="fireworks", model="m", temperature=5.0,
                ),
            },
        )
        errors = validators.validate_routing(routing, [])
        assert any("temperature" in e and "out of range" in e for e in errors)

    def test_negative_temperature_fails(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(
                    provider="fireworks", model="m", temperature=-0.1,
                ),
            },
        )
        errors = validators.validate_routing(routing, [])
        assert any("temperature" in e and "out of range" in e for e in errors)

    def test_zero_temperature_passes(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(
                    provider="fireworks", model="m", temperature=0.0,
                ),
            },
        )
        errors = validators.validate_routing(routing, [])
        assert not any("temperature" in e for e in errors)

    def test_max_tokens_zero_fails(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(
                    provider="fireworks", model="m", max_tokens=0,
                ),
            },
        )
        errors = validators.validate_routing(routing, [])
        assert any("max_tokens" in e for e in errors)

    def test_max_tokens_negative_fails(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            profile_models={
                "implementer": ProfileModel(
                    provider="fireworks", model="m", max_tokens=-100,
                ),
            },
        )
        errors = validators.validate_routing(routing, [])
        assert any("max_tokens" in e for e in errors)

    def test_default_model_validated_too(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            default_model=ProfileModel(provider="acme-llm", model=""),
        )
        errors = validators.validate_routing(routing, [])
        assert any("default_model" in e and "no model identifier" in e for e in errors)
        assert any("default_model" in e and "acme-llm" in e for e in errors)

    def test_default_model_temperature_out_of_range(self):
        routing = Routing(
            default_implementer="implementer",
            default_reviewer="reviewer",
            default_integrator="integrator",
            resolver="conflict-resolver",
            default_model=ProfileModel(provider="openai", model="gpt-4o", temperature=3.0),
        )
        errors = validators.validate_routing(routing, [])
        assert any("default_model" in e and "temperature" in e for e in errors)

    def test_known_providers_pass(self):
        for provider in ("fireworks", "openai", "anthropic", "google", "mistral", "together", "deepseek", "local"):
            routing = Routing(
                default_implementer="implementer",
                default_reviewer="reviewer",
                default_integrator="integrator",
                resolver="conflict-resolver",
                profile_models={
                    "implementer": ProfileModel(provider=provider, model="m"),
                },
            )
            errors = validators.validate_routing(routing, [])
            assert not any("known set" in e for e in errors), f"provider {provider!r} should be known"


# --------------------------------------------------------------------------- #
# Config.yaml parsing sanity                                                   #
# --------------------------------------------------------------------------- #


class TestConfigYamlModels:
    def test_config_yaml_has_models_default(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent.parent / "src" / "scientia" / "references" / "config.yaml"
        cfg = yaml.safe_load(config_path.read_text())
        assert "models" in cfg["hermes"]
        default = cfg["hermes"]["models"]["default"]
        assert default["provider"] == "fireworks"
        assert default["model"] != ""
        assert "base_url" in default
        assert default["api_key_env"] == "FIREWORKS_API_KEY"

    def test_config_yaml_has_per_profile_models(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent.parent / "src" / "scientia" / "references" / "config.yaml"
        cfg = yaml.safe_load(config_path.read_text())
        profiles = cfg["hermes"]["profiles"]
        for name in ("implementer", "reviewer", "integrator", "conflict-resolver"):
            assert name in profiles, f"profile {name!r} missing from config"
            assert "model" in profiles[name], f"profile {name!r} has no model config"
            model = profiles[name]["model"]
            assert model["provider"] == "fireworks", f"profile {name!r} should default to fireworks"
            assert model["model"] != "", f"profile {name!r} has empty model"

    def test_config_yaml_implementer_uses_larger_max_tokens(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent.parent / "src" / "scientia" / "references" / "config.yaml"
        cfg = yaml.safe_load(config_path.read_text())
        impl_model = cfg["hermes"]["profiles"]["implementer"]["model"]
        assert impl_model["max_tokens"] >= 4096, "implementer should have generous max_tokens for code gen"

    def test_config_yaml_profiles_have_descriptions(self):
        import yaml
        config_path = Path(__file__).resolve().parent.parent.parent / "src" / "scientia" / "references" / "config.yaml"
        cfg = yaml.safe_load(config_path.read_text())
        profiles = cfg["hermes"]["profiles"]
        for name, prof in profiles.items():
            assert "description" in prof, f"profile {name!r} should have a description"
