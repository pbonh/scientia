#!/usr/bin/env python3
"""apply_browser_toolset.py — enable Hermes' browser toolset on the jobhunt profile.

When development/config.yaml declares a `jobhunt:` block, the
`scientia-jobhunt-agent` profile must have Hermes' **browser** toolset
enabled so the worker can call `browser_navigate`, `browser_snapshot`, etc.
Per the Hermes docs, the browser toolset is enabled by including `browser`
in the profile config's `toolsets` list.

This script:
  1. Reads the profile's effective config via `hermes -p <name> config show --json`.
  2. If `browser` is already in `toolsets`, it's a no-op (idempotent).
  3. Otherwise it appends `browser` to the list via
     `hermes -p <name> config set toolsets '<json>'`.
  4. On failure it refuses, surfacing Hermes' stderr plus the manual
     remediation (`hermes setup tools` / `hermes -p <name> tools`).

Scope note (deliberate): scientia only ensures the *toolset* is enabled.
Which browser backend it uses and its credentials (a logged-in Chrome over
CDP, a Browserbase key, a Camofox URL) are the user's to configure via
`hermes setup tools` and `~/.hermes/.env`, exactly as scientia leaves
`custom_providers`/`.env` to the user. The per-task CDP endpoint reaches the
worker through the task body's `## Browser Plan` (emitted by
scientia-jobhunt-emit), not through persistent profile config — so this
script does not invent unverified `browser.*` config keys.

⚠ VERIFY AT RUNTIME: the exact `toolsets` shape is read back from
`hermes -p <name> config show --json`; if a future Hermes renames the key
or expects a different set syntax, this script fails loudly (it never
silently mis-writes) and the SKILL.md documents the manual fallback.

Used by scientia-kanban-init (only when jobhunt is enabled). Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent.parent / "scientia-kanban-emit" / "scripts"))

from emit import _parse_yaml_subset  # noqa: E402
from profile_models import resolve_profile_name  # noqa: E402

BROWSER_TOOLSET = "browser"


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_toolsets(profile_name: str, runner: Callable) -> list:
    proc = runner(
        ["hermes", "-p", profile_name, "config", "show", "--json"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"`hermes -p {profile_name} config show --json` failed: "
            f"{proc.stderr.strip() or 'no stderr'}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"config show returned invalid JSON: {e}")
    toolsets = data.get("toolsets") or []
    if not isinstance(toolsets, list):
        raise RuntimeError(
            f"profile {profile_name} `toolsets` is not a list "
            f"(got {type(toolsets).__name__})"
        )
    return toolsets


def ensure_browser_toolset(
    *,
    config: dict,
    runner: Callable = subprocess.run,
) -> dict:
    """Ensure `browser` is in the jobhunt profile's toolsets.

    Returns a result dict: {profile, already, enabled, error}. `error` is
    None on success. No-op (returns {'skipped': True}) when jobhunt is OFF.
    """
    jobhunt = config.get("jobhunt")
    if not isinstance(jobhunt, dict):
        return {"skipped": True}

    hermes_cfg = config.get("hermes") or {}
    profile_name = resolve_profile_name("jobhunt", hermes_cfg.get("profile_names"))

    toolsets = _read_toolsets(profile_name, runner)
    if BROWSER_TOOLSET in toolsets:
        return {"profile": profile_name, "already": True,
                "enabled": False, "error": None}

    new_list = [*toolsets, BROWSER_TOOLSET]
    proc = runner(
        ["hermes", "-p", profile_name, "config", "set",
         "toolsets", json.dumps(new_list)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return {
            "profile": profile_name, "already": False, "enabled": False,
            "error": (
                f"could not enable the browser toolset on {profile_name}: "
                f"{proc.stderr.strip() or 'no stderr'}\n"
                f"Fix: enable it manually, e.g.\n"
                f"  hermes setup tools        # interactive: choose Browser Automation\n"
                f"  hermes -p {profile_name} config show --json   # confirm 'browser' in toolsets\n"
                f"then re-run scientia-kanban-init."
            ),
        }
    return {"profile": profile_name, "already": False,
            "enabled": True, "error": None}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="scientia-apply-browser-toolset",
        description="Enable Hermes' browser toolset on the jobhunt profile.",
    )
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args(argv)

    repo_root = args.repo_root.resolve()
    config_path = args.config or (repo_root / "development" / "config.yaml")
    if not config_path.is_file():
        print(f"refusing: {config_path} not found", file=sys.stderr)
        return 2
    config = _parse_yaml_subset(config_path.read_text(encoding="utf-8"))

    try:
        result = ensure_browser_toolset(config=config)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 3

    if result.get("skipped"):
        print("browser toolset: jobhunt feature OFF — nothing to do")
        return 0

    log = repo_root / "development" / "log.md"
    profile = result["profile"]
    if result["error"]:
        print(result["error"], file=sys.stderr)
        return 1
    if result["already"]:
        verb = "browser-toolset-already-enabled"
        print(f"browser toolset already enabled on {profile}")
    else:
        verb = "browser-toolset-enabled"
        print(f"enabled browser toolset on {profile}")
    if log.exists():
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"- {_iso_now()} — scientia-kanban-init — {verb} — — "
                     f"profile={profile}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
