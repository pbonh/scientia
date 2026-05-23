#!/usr/bin/env python3
"""check_env_keys.py — verify API keys for declared custom providers are reachable.

When a role in `hermes.profiles` references `custom:<name>`, the
matching host `custom_providers` entry has a `key_env` (e.g.,
`FIREWORKS_API_KEY`). For the spawned worker to authenticate, that var
must be set in at least one of the locations a Hermes worker reads:

  1. The current process environment (the gateway inherits this from
     the user's shell, and dispatched workers inherit from the gateway).
  2. `~/.hermes/.env` (host-level dotenv).
  3. The profile's own `~/.hermes/profiles/<resolved-name>/.env`.

This preflight collects every required `key_env` from the declared
block, scans each location, and returns a refusal string listing the
missing-everywhere keys with a remediation hint. Refusal text is None
when every required key is reachable from at least one location.

Used by scientia-kanban-init step 3b (right after apply_profile_models),
*before* workers can be dispatched against the new profile configs.
Stdlib only.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import subprocess


# Resolve the sibling kanban-emit scripts/ directory so we can reuse the
# shared profile helpers.
_THIS = Path(__file__).resolve()
_BUNDLE_SKILLS = _THIS.parent.parent.parent  # …/skills/
_EMIT_SCRIPTS = _BUNDLE_SKILLS / "scientia-kanban-emit" / "scripts"
sys.path.insert(0, str(_EMIT_SCRIPTS))

from profile_models import (  # noqa: E402
    collect_custom_provider_refs,
    read_host_custom_providers,
    resolve_profile_name,
    validate_profiles,
)
from emit import _parse_yaml_subset  # noqa: E402


# ---------------------------------------------------------------------------
# dotenv reader (key names only)
# ---------------------------------------------------------------------------


def read_dotenv_keys(path: Path) -> Set[str]:
    """Return the set of variable names defined in a `.env` file.

    Values are not parsed — we only need to know which keys are *set*.
    Lines that don't look like assignments are skipped. Returns an
    empty set when the file doesn't exist.
    """
    if not path.is_file():
        return set()
    keys: Set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


# ---------------------------------------------------------------------------
# Required-keys collection
# ---------------------------------------------------------------------------


def collect_required_env_keys(
    *,
    profiles_block: dict,
    profile_names: Optional[dict],
    host_providers: List[dict],
) -> Dict[str, List[str]]:
    """Return `{key_env: [resolved_profile_name, …]}` of required keys.

    Walks each role's declared block, finds `custom:<name>` references
    (across `model.provider`, `auxiliary.*.provider`, and
    `model_aliases.*.provider`), looks up each name's `key_env` in the
    host `custom_providers` list, and records which profile names need
    it. Names without a `key_env` (keyless local servers) are skipped.

    Returns an empty dict when nothing is required.
    """
    by_name = {
        p.get("name"): p
        for p in host_providers
        if isinstance(p, dict) and isinstance(p.get("name"), str)
    }
    out: Dict[str, List[str]] = {}
    for role, block in profiles_block.items():
        if not block:
            continue
        refs = collect_custom_provider_refs(block)
        if not refs:
            continue
        resolved = resolve_profile_name(role, profile_names)
        for ref in refs:
            entry = by_name.get(ref)
            if entry is None:
                # Unknown provider — propagation step will refuse loudly.
                # We skip here; that's not this gate's concern.
                continue
            key = entry.get("key_env")
            if not isinstance(key, str) or not key.strip():
                continue  # keyless endpoint
            out.setdefault(key, [])
            if resolved not in out[key]:
                out[key].append(resolved)
    return out


# ---------------------------------------------------------------------------
# Reachability check
# ---------------------------------------------------------------------------


def _profile_dotenv_path(
    profile_name: str,
    *,
    profiles_root: Optional[Path] = None,
) -> Path:
    root = profiles_root or (Path.home() / ".hermes" / "profiles")
    return root / profile_name / ".env"


def _host_dotenv_path(hermes_home: Optional[Path] = None) -> Path:
    base = hermes_home or (Path.home() / ".hermes")
    return base / ".env"


def check_env_keys(
    *,
    config: dict,
    runner: Callable = subprocess.run,
    environ: Optional[Dict[str, str]] = None,
    hermes_home: Optional[Path] = None,
    profiles_root: Optional[Path] = None,
) -> Optional[str]:
    """Refuse-style gate: None when every required key is reachable.

    Returns a multi-line refusal string when at least one declared
    `custom:<name>` provider's `key_env` is not present in **any** of:
    process env, host `.env`, or that profile's own `.env`.

    The `environ`, `hermes_home`, and `profiles_root` parameters are for
    tests; production calls default to `os.environ` / `~/.hermes/` /
    `~/.hermes/profiles/`.
    """
    hermes_cfg = config.get("hermes") or {}
    profiles_block = validate_profiles(hermes_cfg.get("profiles"))
    if not profiles_block:
        return None  # hands-off — nothing to check.

    profile_names = hermes_cfg.get("profile_names")
    host_providers = read_host_custom_providers(runner=runner)

    required = collect_required_env_keys(
        profiles_block=profiles_block,
        profile_names=profile_names,
        host_providers=host_providers,
    )
    if not required:
        return None

    env = environ if environ is not None else dict(os.environ)
    host_env_keys = read_dotenv_keys(_host_dotenv_path(hermes_home))

    # For each missing key, capture which profile(s) need it.
    missing: List[Tuple[str, List[str]]] = []
    for key_env, profile_list in required.items():
        if key_env in env:
            continue
        if key_env in host_env_keys:
            continue
        # Check each profile's own .env; the key is "reachable" if ANY
        # of the profiles needing it has it locally — but each profile
        # spawns independently, so we report missing per-profile.
        missing_for: List[str] = []
        for profile_name in profile_list:
            profile_keys = read_dotenv_keys(
                _profile_dotenv_path(profile_name, profiles_root=profiles_root)
            )
            if key_env not in profile_keys:
                missing_for.append(profile_name)
        if missing_for:
            missing.append((key_env, missing_for))

    if not missing:
        return None

    bullets: List[str] = []
    for key_env, profiles in missing:
        joined = ", ".join(sorted(profiles))
        bullets.append(f"  - {key_env} (needed by: {joined})")
    return (
        "Custom-provider API keys are not reachable from worker context.\n"
        "Each declared `custom:<name>` reference resolves through a "
        "`key_env` in the host `custom_providers` list; that env var must "
        "be set in the worker's process env, in `~/.hermes/.env`, or in "
        "the profile's own `.env`.\n\n"
        "Missing keys:\n"
        + "\n".join(bullets)
        + "\n\nFix: set each missing var in one of:\n"
        "  - your shell environment (so the gateway/CLI inherits it),\n"
        "  - `~/.hermes/.env` (loaded for every Hermes process), or\n"
        "  - `~/.hermes/profiles/<name>/.env` (per-profile only).\n"
        "scientia does not manage secrets — these writes are yours to make."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="scientia-kanban-init-check-env-keys",
        description=(
            "Verify that every `custom:<name>` provider declared under "
            "hermes.profiles has a reachable API key (process env, host "
            ".env, or profile .env)."
        ),
    )
    p.add_argument(
        "--repo-root", type=Path, default=Path.cwd(),
        help="Repo root (default: cwd).",
    )
    p.add_argument(
        "--config", type=Path, default=None,
        help=(
            "Path to development/config.yaml "
            "(default: <repo-root>/development/config.yaml)."
        ),
    )
    args = p.parse_args(argv)

    repo_root = args.repo_root.resolve()
    config_path = args.config or (repo_root / "development" / "config.yaml")
    if not config_path.is_file():
        print(f"refusing: {config_path} not found", file=sys.stderr)
        return 2

    config = _parse_yaml_subset(config_path.read_text(encoding="utf-8"))

    try:
        reason = check_env_keys(config=config, runner=subprocess.run)
    except Exception as e:  # noqa: BLE001
        print(f"check_env_keys failed: {e}", file=sys.stderr)
        return 3

    if reason is None:
        print("env keys OK")
        return 0
    print(reason, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
