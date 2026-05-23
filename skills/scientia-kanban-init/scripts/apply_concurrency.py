#!/usr/bin/env python3
"""apply_concurrency.py — propagate the per-repo concurrency cap.

scientia's `hermes.max_concurrent_children` maps to Hermes'
`delegation.max_concurrent_children`. Because Hermes profiles are
independent home directories
(https://hermes-agent.nousresearch.com/docs/user-guide/profiles),
writing the cap only to `~/.hermes/config.yaml` does **not** apply it
to profile workers. Sub-delegations from a worker (e.g., the
integrator spawning a fixup) use the worker's own profile config —
which defaults to 3 if never set, silently overriding the host value.

This script writes the declared cap to:
  1. `~/.hermes/config.yaml`             (host CLI invocations)
  2. each scientia profile's config.yaml (workers that sub-delegate)

Idempotent: reads each target's effective value via
`hermes [-p <name>] config show --json` and skips writes that already
match. Per-target log lines go to `development/log.md`.

Used by scientia-kanban-init step 6. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# Resolve the sibling kanban-emit scripts/ directory so we can reuse the
# shared profile helpers (ROLES, resolve_profile_name, YAML reader).
_THIS = Path(__file__).resolve()
_BUNDLE_SKILLS = _THIS.parent.parent.parent  # …/skills/
_EMIT_SCRIPTS = _BUNDLE_SKILLS / "scientia-kanban-emit" / "scripts"
sys.path.insert(0, str(_EMIT_SCRIPTS))

from profile_models import (  # noqa: E402
    ROLES,
    resolve_profile_name,
)
from emit import _parse_yaml_subset  # noqa: E402


# ---------------------------------------------------------------------------
# Effective-value reader / writer
# ---------------------------------------------------------------------------


def read_effective_delegation_cap(
    *,
    profile: Optional[str] = None,
    runner: Callable = subprocess.run,
) -> Optional[int]:
    """Read `delegation.max_concurrent_children` from host or profile.

    Returns the integer value when set, or None when the key is absent
    from the effective config. Raises RuntimeError when the hermes call
    itself fails.
    """
    argv = ["hermes"]
    if profile:
        argv += ["-p", profile]
    argv += ["config", "show", "--json"]
    proc = runner(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(argv)}` failed: "
            f"{proc.stderr.strip() or 'no stderr'}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"`{' '.join(argv)}` returned invalid JSON: {e}"
        )
    deleg = data.get("delegation") or {}
    value = deleg.get("max_concurrent_children")
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int in Python — reject explicitly.
        raise RuntimeError(
            f"unexpected boolean for delegation.max_concurrent_children "
            f"in {profile or 'host'}: {value!r}"
        )
    if not isinstance(value, int):
        raise RuntimeError(
            f"unexpected non-integer for "
            f"delegation.max_concurrent_children in {profile or 'host'}: "
            f"{value!r}"
        )
    return value


def set_delegation_cap(
    *,
    profile: Optional[str],
    value: int,
    runner: Callable = subprocess.run,
) -> None:
    """Write `delegation.max_concurrent_children = <value>`.

    `profile=None` targets the host; otherwise the named profile.
    Raises RuntimeError on non-zero exit, surfacing Hermes' stderr.
    """
    argv = ["hermes"]
    if profile:
        argv += ["-p", profile]
    argv += ["config", "set", "delegation.max_concurrent_children", str(value)]
    proc = runner(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(argv)}` failed: "
            f"{proc.stderr.strip() or 'no stderr'}"
        )


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


def apply_concurrency(
    *,
    config: dict,
    repo_root: Path,
    runner: Callable = subprocess.run,
) -> Dict[str, Dict[str, Any]]:
    """Apply the per-repo cap to host + each scientia profile.

    Returns a summary mapping each target (`"host"`, role name) to a dict
    describing the action: `value`, `previous`, `action` (`applied` /
    `already-set`), and `profile` for role entries.

    Raises ValueError when the declared cap is not a positive integer.
    Raises RuntimeError on the first set/read failure.
    """
    hermes_cfg = config.get("hermes") or {}
    cap = hermes_cfg.get("max_concurrent_children", 3)
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError(
            "hermes.max_concurrent_children must be a positive integer, "
            f"got {cap!r}"
        )
    profile_names = hermes_cfg.get("profile_names")

    summary: Dict[str, Dict[str, Any]] = {}

    # 1) Host
    current = read_effective_delegation_cap(runner=runner)
    if current == cap:
        summary["host"] = {"value": cap, "action": "already-set"}
        _append_log(
            repo_root,
            f"- {_iso_now()} — scientia-kanban-init — "
            f"concurrency-already-set — — target=host N={cap}",
        )
    else:
        set_delegation_cap(profile=None, value=cap, runner=runner)
        summary["host"] = {
            "value": cap, "previous": current, "action": "applied",
        }
        _append_log(
            repo_root,
            f"- {_iso_now()} — scientia-kanban-init — "
            f"concurrency-applied — — target=host N={cap} "
            f"previous={current}",
        )

    # 2) Each scientia profile
    for role in sorted(ROLES):
        name = resolve_profile_name(role, profile_names)
        current = read_effective_delegation_cap(profile=name, runner=runner)
        if current == cap:
            summary[role] = {
                "profile": name, "value": cap, "action": "already-set",
            }
            _append_log(
                repo_root,
                f"- {_iso_now()} — scientia-kanban-init — "
                f"concurrency-already-set — — target={role}({name}) N={cap}",
            )
        else:
            set_delegation_cap(profile=name, value=cap, runner=runner)
            summary[role] = {
                "profile": name,
                "value": cap,
                "previous": current,
                "action": "applied",
            }
            _append_log(
                repo_root,
                f"- {_iso_now()} — scientia-kanban-init — "
                f"concurrency-applied — — target={role}({name}) N={cap} "
                f"previous={current}",
            )

    return summary


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="scientia-kanban-init-apply-concurrency",
        description=(
            "Propagate development/config.yaml's "
            "hermes.max_concurrent_children to ~/.hermes/config.yaml "
            "AND each scientia profile's delegation.max_concurrent_children."
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
        summary = apply_concurrency(
            config=config, repo_root=repo_root, runner=subprocess.run,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 3

    for target, info in summary.items():
        line = f"{target}: {info['action']} N={info['value']}"
        if "profile" in info:
            line = f"{target}({info['profile']}): {info['action']} N={info['value']}"
        if info.get("previous") is not None:
            line += f" (was {info['previous']})"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
