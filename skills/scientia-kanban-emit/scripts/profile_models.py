#!/usr/bin/env python3
"""profile_models.py — per-profile Hermes model configuration helpers.

Used by both `scientia-kanban-init` (to apply the user's `hermes.profiles`
block to each profile's `~/.hermes/profiles/<name>/config.yaml` via
`hermes -p <name> config set`) and `scientia-kanban-emit` (to refuse on
drift between the declared config and Hermes' effective config).

Stdlib only. The schema mirrors Hermes' per-profile config.yaml 1:1 so
users can copy/paste examples from
https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


# Logical scientia roles. Keys allowed under `hermes.profiles:` in
# development/config.yaml. The role -> hermes profile name lookup
# happens via `hermes.profile_names` (see _resolve_profile_name).
ROLES = frozenset({"implementer", "reviewer", "integrator", "aggregator"})

# Per-role top-level keys, mirroring Hermes' per-profile config.yaml.
ROLE_TOP_KEYS = frozenset({"model", "auxiliary", "model_aliases"})

# Keys allowed under `model:` (Hermes' main-model block).
MODEL_KEYS = frozenset({"provider", "default", "base_url", "api_mode"})

# Auxiliary task names per the Hermes docs (configuring-models page).
AUXILIARY_TASKS = frozenset({
    "compression",
    "vision",
    "web_summary",
    "approval_scoring",
    "mcp_routing",
    "session_titles",
    "skill_search",
})

# Keys allowed under `auxiliary.<task>:`.
AUXILIARY_TASK_KEYS = frozenset({
    "provider",
    "model",
    "base_url",
    "api_key",
    "timeout",
    "extra_body",
    "download_timeout",
})

# `model_aliases.<alias>` requires these two keys, both as scalars.
MODEL_ALIAS_KEYS = frozenset({"model", "provider"})


class ProfileConfigError(ValueError):
    """Raised when the `hermes.profiles` block fails validation."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_profiles(profiles_block: Optional[dict]) -> Dict[str, dict]:
    """Validate the `hermes.profiles` block.

    Returns the same block unchanged on success; raises ProfileConfigError
    with a precise message on the first failure. None or {} returns {}.
    """
    if profiles_block is None:
        return {}
    if not isinstance(profiles_block, dict):
        raise ProfileConfigError(
            "hermes.profiles must be a mapping of role -> config, "
            f"got {type(profiles_block).__name__}"
        )

    for role, block in profiles_block.items():
        if role not in ROLES:
            raise ProfileConfigError(
                f"hermes.profiles: unknown role {role!r}; "
                f"expected one of {sorted(ROLES)}"
            )
        if block is None:
            continue
        if not isinstance(block, dict):
            raise ProfileConfigError(
                f"hermes.profiles.{role} must be a mapping, "
                f"got {type(block).__name__}"
            )
        _validate_role_block(role, block)
    return profiles_block


def _validate_role_block(role: str, block: dict) -> None:
    for top_key, sub in block.items():
        if top_key not in ROLE_TOP_KEYS:
            raise ProfileConfigError(
                f"hermes.profiles.{role}: unknown key {top_key!r}; "
                f"expected one of {sorted(ROLE_TOP_KEYS)}"
            )
        if sub is None:
            continue
        if not isinstance(sub, dict):
            raise ProfileConfigError(
                f"hermes.profiles.{role}.{top_key} must be a mapping, "
                f"got {type(sub).__name__}"
            )
        if top_key == "model":
            _validate_model_block(role, sub)
        elif top_key == "auxiliary":
            _validate_auxiliary_block(role, sub)
        else:  # model_aliases
            _validate_model_aliases_block(role, sub)


def _validate_model_block(role: str, block: dict) -> None:
    for key in block:
        if key not in MODEL_KEYS:
            raise ProfileConfigError(
                f"hermes.profiles.{role}.model: unknown key {key!r}; "
                f"expected one of {sorted(MODEL_KEYS)}"
            )


def _validate_auxiliary_block(role: str, block: dict) -> None:
    for task, task_cfg in block.items():
        if task not in AUXILIARY_TASKS:
            raise ProfileConfigError(
                f"hermes.profiles.{role}.auxiliary: unknown task {task!r}; "
                f"expected one of {sorted(AUXILIARY_TASKS)}"
            )
        if task_cfg is None:
            continue
        if not isinstance(task_cfg, dict):
            raise ProfileConfigError(
                f"hermes.profiles.{role}.auxiliary.{task} must be a mapping, "
                f"got {type(task_cfg).__name__}"
            )
        for key in task_cfg:
            if key not in AUXILIARY_TASK_KEYS:
                raise ProfileConfigError(
                    f"hermes.profiles.{role}.auxiliary.{task}: "
                    f"unknown key {key!r}; "
                    f"expected one of {sorted(AUXILIARY_TASK_KEYS)}"
                )


def _validate_model_aliases_block(role: str, block: dict) -> None:
    for alias, alias_cfg in block.items():
        if not isinstance(alias_cfg, dict):
            raise ProfileConfigError(
                f"hermes.profiles.{role}.model_aliases.{alias} must be a "
                f"mapping with keys model and provider"
            )
        missing = MODEL_ALIAS_KEYS - set(alias_cfg.keys())
        if missing:
            raise ProfileConfigError(
                f"hermes.profiles.{role}.model_aliases.{alias}: "
                f"missing required keys {sorted(missing)}"
            )
        extra = set(alias_cfg.keys()) - MODEL_ALIAS_KEYS
        if extra:
            raise ProfileConfigError(
                f"hermes.profiles.{role}.model_aliases.{alias}: "
                f"unknown keys {sorted(extra)}; "
                f"expected only {sorted(MODEL_ALIAS_KEYS)}"
            )


# ---------------------------------------------------------------------------
# Flatten
# ---------------------------------------------------------------------------


def flatten_profile(profile_block: dict) -> Dict[str, str]:
    """Flatten a single role's block to dotted-key -> stringified-value.

    `flatten_profile({"model": {"default": "claude-opus-4.7", ...}})` →
    `{"model.default": "claude-opus-4.7", ...}`.

    Values are converted to the string Hermes' `config set` expects:
    None → "''", booleans → "true"/"false", numbers → str(n).
    Nested dicts under any depth are flattened recursively.
    """
    out: Dict[str, str] = {}
    _flatten_into(profile_block, prefix="", out=out)
    return out


def _flatten_into(node: dict, *, prefix: str, out: Dict[str, str]) -> None:
    for key, value in node.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _flatten_into(value, prefix=dotted, out=out)
        else:
            out[dotted] = _stringify(value)


def _stringify(value) -> str:
    if value is None or value == "":
        return "''"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ---------------------------------------------------------------------------
# Profile name resolution
# ---------------------------------------------------------------------------


def resolve_profile_name(role: str, profile_names: Optional[dict]) -> str:
    """Look up the Hermes profile name for a scientia role.

    Defaults to `scientia-<role>` when not overridden. Mirrors the
    convention shipped in development/config.yaml.tmpl's
    `hermes.profile_names` block.
    """
    if role not in ROLES:
        raise ProfileConfigError(
            f"resolve_profile_name: unknown role {role!r}"
        )
    if profile_names and role in profile_names and profile_names[role]:
        return str(profile_names[role])
    return f"scientia-{role}"


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


# Hermes' `auto` provider sentinel: both 'auto' and '' should be treated as
# the "let Hermes pick" directive, so they compare equal across sides.
_AUTO_EQUIVALENTS = frozenset({"auto", "''", ""})


def _values_match(declared: str, effective: str) -> bool:
    if declared == effective:
        return True
    if declared in _AUTO_EQUIVALENTS and effective in _AUTO_EQUIVALENTS:
        return True
    return False


def read_effective_profile_config(
    profile_name: str,
    *,
    runner: Callable = subprocess.run,
) -> Dict[str, str]:
    """Read effective config for a Hermes profile as flat dotted-key map.

    Calls `hermes -p <name> config show --json` and flattens the result.
    Raises RuntimeError on non-zero exit, surfacing Hermes' stderr.
    """
    proc = runner(
        ["hermes", "-p", profile_name, "config", "show", "--json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"`hermes -p {profile_name} config show --json` failed: "
            f"{proc.stderr.strip() or 'no stderr'}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"`hermes -p {profile_name} config show --json` returned "
            f"invalid JSON: {e}"
        )
    if not isinstance(data, dict):
        raise RuntimeError(
            f"`hermes -p {profile_name} config show --json` returned "
            f"a non-object top-level value"
        )
    out: Dict[str, str] = {}
    _flatten_into(data, prefix="", out=out)
    return out


def detect_drift(
    *,
    declared: Dict[str, str],
    effective: Dict[str, str],
) -> List[Tuple[str, str, str]]:
    """Compare declared vs. effective flat configs.

    Returns a list of `(dotted_key, declared_value, effective_value)`
    tuples for every key in `declared` whose effective value differs.
    Keys absent from `effective` count as drift (effective="<missing>").
    """
    drift: List[Tuple[str, str, str]] = []
    for key, declared_v in declared.items():
        effective_v = effective.get(key, "<missing>")
        if not _values_match(declared_v, effective_v):
            drift.append((key, declared_v, effective_v))
    return drift


def format_drift_reason(
    *,
    role: str,
    profile_name: str,
    drift: List[Tuple[str, str, str]],
) -> str:
    """Render a drift report for one role into a one-line refusal reason."""
    head = (
        f"profile model config drift on {profile_name} (role={role}): "
    )
    parts = [f"{k}: scientia={d!r} hermes={e!r}" for (k, d, e) in drift]
    tail = (
        ". Fix: re-run scientia-kanban-init to converge, or update "
        "development/config.yaml hermes.profiles to match the intended state."
    )
    return head + "; ".join(parts) + tail


def check_profile_models_drift(
    *,
    profiles_block: Optional[dict],
    profile_names: Optional[dict],
    runner: Callable = subprocess.run,
) -> Optional[str]:
    """Preflight gate: refuse if any declared profile's effective config
    differs from `hermes.profiles`.

    Returns None when:
      - `hermes.profiles` is absent or empty (hands-off default), or
      - every declared key matches Hermes' effective value.

    Returns a multi-line refusal reason listing every drifted role/key
    otherwise.
    """
    profiles = validate_profiles(profiles_block)
    if not profiles:
        return None

    refusal_lines: List[str] = []
    for role, block in profiles.items():
        if not block:
            continue
        declared = flatten_profile(block)
        if not declared:
            continue
        profile_name = resolve_profile_name(role, profile_names)
        try:
            effective = read_effective_profile_config(
                profile_name, runner=runner
            )
        except RuntimeError as e:
            # Surface Hermes' failure so the user can fix it; drift check
            # cannot proceed past an unreadable profile.
            refusal_lines.append(
                f"profile model config: cannot read effective config "
                f"for {profile_name} (role={role}): {e}"
            )
            continue
        drift = detect_drift(declared=declared, effective=effective)
        if drift:
            refusal_lines.append(
                format_drift_reason(
                    role=role, profile_name=profile_name, drift=drift,
                )
            )
    if refusal_lines:
        return "\n".join(refusal_lines)
    return None


# ---------------------------------------------------------------------------
# Profile-existence detection (precedes drift detection)
# ---------------------------------------------------------------------------


def check_profiles_exist(
    *,
    profile_names: Optional[dict] = None,
    runner: Callable = subprocess.run,
) -> Optional[str]:
    """Preflight gate: refuse if any scientia profile is unknown to Hermes.

    For each role in ROLES, resolves the Hermes profile name (default
    `scientia-<role>`, or `hermes.profile_names.<role>` if overridden)
    and probes it with `hermes profile show <name>`. A non-zero exit
    means the profile is not registered — the dispatcher will park
    every emitted task as `skipped_nonspawnable` forever.

    Returns None when every required profile resolves. Returns a
    multi-line refusal listing the missing roles + resolved names
    otherwise, with a remediation hint pointing at
    scientia-kanban-init.

    Independent of `check_profile_models_drift`: a profile must exist
    before any model-config comparison is meaningful. If hermes is not
    on PATH at all, returns None and defers to `check_hermes_on_path`.
    """
    missing: List[Tuple[str, str]] = []  # (role, resolved_name)
    for role in sorted(ROLES):
        name = resolve_profile_name(role, profile_names)
        try:
            result = runner(
                ["hermes", "profile", "show", name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except FileNotFoundError:
            # hermes binary missing; the hermes-on-path gate will refuse.
            return None
        if result.returncode != 0:
            missing.append((role, name))
    if not missing:
        return None
    bullets = "\n".join(
        f"  - {name} (role={role})" for (role, name) in missing
    )
    return (
        "Required scientia profiles are not registered with Hermes:\n"
        + bullets
        + "\nFix: run `scientia-kanban-init` to create them."
    )
