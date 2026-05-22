#!/usr/bin/env python3
"""apply_profile_models.py — push per-profile Hermes model config.

Reads `hermes.profiles` from development/config.yaml and applies each
declared leaf to the corresponding `~/.hermes/profiles/<name>/config.yaml`
via `hermes -p <name> config set <dotted.key> <value>`. Authoritative:
scientia config wins; re-running converges. No rollback — partial
application is acceptable because the next run reconciles.

Used by scientia-kanban-init step 3b. Idempotent: keys whose effective
value already matches the declared value are not re-set.

Stdlib only. Re-uses helpers from scientia-kanban-emit/scripts/ since
both skills ship in the same bundle.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


# Resolve the sibling kanban-emit scripts/ directory so we can import
# the shared profile_models + YAML-subset helpers.
_THIS = Path(__file__).resolve()
_BUNDLE_SKILLS = _THIS.parent.parent.parent  # …/skills/
_EMIT_SCRIPTS = _BUNDLE_SKILLS / "scientia-kanban-emit" / "scripts"
sys.path.insert(0, str(_EMIT_SCRIPTS))

from profile_models import (  # noqa: E402
    ProfileConfigError,
    collect_custom_provider_refs,
    flatten_profile,
    propagate_custom_providers_to_profile,
    read_effective_profile_config,
    read_host_custom_providers,
    resolve_profile_name,
    validate_profiles,
)
from emit import _parse_yaml_subset  # noqa: E402


# ---------------------------------------------------------------------------
# Apply one profile
# ---------------------------------------------------------------------------


def apply_one_profile(
    *,
    role: str,
    profile_name: str,
    declared: Dict[str, str],
    runner: Callable = subprocess.run,
) -> Tuple[int, int, List[str]]:
    """Apply declared dotted-key map to `profile_name` via hermes config set.

    Returns (applied_count, unchanged_count, error_lines). When error_lines
    is non-empty, at least one `config set` failed; the caller should abort.
    """
    effective = read_effective_profile_config(profile_name, runner=runner)
    applied = 0
    unchanged = 0
    errors: List[str] = []
    for dotted_key, value in sorted(declared.items()):
        current = effective.get(dotted_key)
        if current == value:
            unchanged += 1
            continue
        proc = runner(
            ["hermes", "-p", profile_name, "config", "set", dotted_key, value],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            errors.append(
                f"role={role} profile={profile_name} key={dotted_key}: "
                f"{proc.stderr.strip() or 'no stderr'}"
            )
            return applied, unchanged, errors
        applied += 1
    return applied, unchanged, errors


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_log(repo_root: Path, line: str) -> None:
    log_path = repo_root / "development" / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def apply_all(
    *,
    config: dict,
    repo_root: Path,
    runner: Callable = subprocess.run,
    profiles_root: Optional[Path] = None,
) -> Dict[str, dict]:
    """Apply hermes.profiles to every declared role. Returns a summary dict.

    Raises ProfileConfigError on schema violations; raises RuntimeError on
    the first `hermes config set` failure with the failing key + stderr.
    Roles that are absent from `hermes.profiles` are reported as `skipped`.

    When a role's declared block references one or more `custom:<name>`
    providers, the matching host-level `custom_providers` entries are
    propagated into the profile's own `~/.hermes/profiles/<name>/config.yaml`.
    Profiles are independent Hermes homes — without their own
    `custom_providers:` block, workers crash with `Unknown provider 'custom:<name>'`.
    """
    hermes_cfg = config.get("hermes", {}) or {}
    profiles_block = hermes_cfg.get("profiles")
    profile_names = hermes_cfg.get("profile_names")

    declared_profiles = validate_profiles(profiles_block)

    summary: Dict[str, dict] = {}
    if not declared_profiles:
        _append_log(
            repo_root,
            f"- {_iso_now()} — scientia-kanban-init — model-config-skipped "
            "— — reason=hermes.profiles-absent",
        )
        return summary

    # Lazy host-config read — only when any role references a custom provider.
    host_providers_cache: Optional[List[dict]] = None

    def _get_host_providers() -> List[dict]:
        nonlocal host_providers_cache
        if host_providers_cache is None:
            host_providers_cache = read_host_custom_providers(runner=runner)
        return host_providers_cache

    for role, block in declared_profiles.items():
        profile_name = resolve_profile_name(role, profile_names)
        if not block:
            summary[role] = {
                "profile": profile_name,
                "applied": 0,
                "unchanged": 0,
                "skipped": True,
                "propagated_custom_providers": [],
            }
            continue
        declared = flatten_profile(block)
        if not declared:
            summary[role] = {
                "profile": profile_name,
                "applied": 0,
                "unchanged": 0,
                "skipped": True,
                "propagated_custom_providers": [],
            }
            continue

        # 1) Propagate custom_providers BEFORE setting model leaves —
        # otherwise `hermes -p <name> config show --json` may fail to resolve
        # the provider when reading the profile's effective config.
        needed = collect_custom_provider_refs(block)
        propagated: List[str] = []
        already_present: List[str] = []
        if needed:
            propagated, already_present = propagate_custom_providers_to_profile(
                profile_name=profile_name,
                needed_names=needed,
                host_providers=_get_host_providers(),
                profiles_root=profiles_root,
            )
            if propagated:
                _append_log(
                    repo_root,
                    f"- {_iso_now()} — scientia-kanban-init — "
                    f"custom-providers-propagated — — profile={role}({profile_name}) "
                    f"providers={','.join(propagated)}",
                )
            if already_present:
                _append_log(
                    repo_root,
                    f"- {_iso_now()} — scientia-kanban-init — "
                    f"custom-providers-already-present — — profile={role}({profile_name}) "
                    f"providers={','.join(already_present)}",
                )

        # 2) Apply the declared scalar leaves.
        applied, unchanged, errors = apply_one_profile(
            role=role,
            profile_name=profile_name,
            declared=declared,
            runner=runner,
        )
        summary[role] = {
            "profile": profile_name,
            "applied": applied,
            "unchanged": unchanged,
            "skipped": False,
            "propagated_custom_providers": propagated,
        }
        _append_log(
            repo_root,
            f"- {_iso_now()} — scientia-kanban-init — "
            f"model-config-applied — — profile={role}({profile_name}) "
            f"applied={applied} unchanged={unchanged}",
        )
        if errors:
            raise RuntimeError(
                "hermes config set failed:\n  " + "\n  ".join(errors)
            )
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="scientia-kanban-init-apply-profile-models",
        description=(
            "Apply development/config.yaml's hermes.profiles block to each "
            "Hermes profile via `hermes -p <name> config set`."
        ),
    )
    p.add_argument(
        "--repo-root", type=Path, default=Path.cwd(),
        help="Repo root (default: cwd).",
    )
    p.add_argument(
        "--config", type=Path, default=None,
        help="Path to development/config.yaml (default: <repo-root>/development/config.yaml).",
    )
    args = p.parse_args(argv)

    repo_root = args.repo_root.resolve()
    config_path = args.config or (repo_root / "development" / "config.yaml")
    if not config_path.is_file():
        print(f"refusing: {config_path} not found", file=sys.stderr)
        return 2

    config = _parse_yaml_subset(config_path.read_text(encoding="utf-8"))

    try:
        summary = apply_all(
            config=config, repo_root=repo_root, runner=subprocess.run,
        )
    except ProfileConfigError as e:
        print(f"hermes.profiles schema error: {e}", file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 3

    if not summary:
        print("hermes.profiles absent — no model config applied (hands-off).")
        return 0

    for role, info in summary.items():
        if info["skipped"]:
            print(f"role={role} profile={info['profile']}: skipped (empty block)")
        else:
            print(
                f"role={role} profile={info['profile']}: "
                f"applied={info['applied']} unchanged={info['unchanged']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
