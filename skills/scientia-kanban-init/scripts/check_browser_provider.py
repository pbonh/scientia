#!/usr/bin/env python3
"""check_browser_provider.py — preflight the job-hunt browser provider.

The optional job-hunt sub-loop drives a browser via Hermes' browser
toolset. Before workers can run, the configured provider must be reachable:

- `cdp` (default) — attach to an already-running Chrome over the DevTools
  Protocol. We verify the endpoint answers (GET <endpoint>/json/version,
  TCP fallback). Refuse with a hint to launch Chrome with
  `--remote-debugging-port` if it doesn't.
- `camofox` / `browserbase` / `browser_use` / `firecrawl` (cloud/local
  managed) — verify the provider's API-key env var is reachable from worker
  context (process env, `~/.hermes/.env`, or the profile's own `.env`),
  mirroring check_env_keys.py for custom providers.

Returns None (exit 0) when the feature is OFF (no `jobhunt:` block) or the
provider is reachable. Refuses (exit 1) otherwise.

Used by scientia-kanban-init (when jobhunt is enabled) and as a
scientia-jobhunt-emit preflight gate. Stdlib only.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Optional
from urllib.parse import urlparse

# Reuse the bundle's tested YAML-subset parser and env helpers.
_THIS = Path(__file__).resolve()
_BUNDLE_SKILLS = _THIS.parent.parent.parent  # …/skills/
sys.path.insert(0, str(_BUNDLE_SKILLS / "scientia-kanban-emit" / "scripts"))
sys.path.insert(0, str(_THIS.parent))  # this dir, for check_env_keys

from emit import _parse_yaml_subset  # noqa: E402
from profile_models import resolve_profile_name  # noqa: E402
from check_env_keys import (  # noqa: E402
    read_dotenv_keys,
    _host_dotenv_path,
    _profile_dotenv_path,
)

DEFAULT_CDP_ENDPOINT = "http://127.0.0.1:9222"

# Provider -> default key_env when the config doesn't override it.
PROVIDER_DEFAULT_KEY_ENV = {
    "browserbase": "BROWSERBASE_API_KEY",
    "browser_use": "BROWSER_USE_API_KEY",
    "firecrawl": "FIRECRAWL_API_KEY",
    "camofox": "CAMOFOX_URL",
}
CDP_PROVIDERS = {"cdp"}


def _default_endpoint_reachable(endpoint: str, timeout: float = 3.0) -> bool:
    """True if a CDP endpoint answers. Tries the HTTP version probe first,
    then a bare TCP connect to host:port."""
    url = endpoint.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        pass
    parsed = urlparse(endpoint)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_browser_provider(
    *,
    config: dict,
    environ: Optional[Dict[str, str]] = None,
    hermes_home: Optional[Path] = None,
    profiles_root: Optional[Path] = None,
    endpoint_reachable: Callable[[str], bool] = _default_endpoint_reachable,
) -> Optional[str]:
    """Refuse-style gate. None when OFF or reachable; refusal string else."""
    jobhunt = config.get("jobhunt")
    if not isinstance(jobhunt, dict):
        return None  # feature OFF — nothing to check.

    browser = jobhunt.get("browser") or {}
    provider = (browser.get("provider") or "cdp").strip()

    if provider in CDP_PROVIDERS:
        endpoint = (browser.get("cdp_endpoint") or DEFAULT_CDP_ENDPOINT).strip()
        if endpoint_reachable(endpoint):
            return None
        return (
            f"job-hunt browser provider `cdp` cannot reach {endpoint}.\n"
            "Fix: launch Chrome with remote debugging, e.g.\n"
            "  google-chrome --remote-debugging-port=9222 "
            "--user-data-dir=\"$HOME/.cache/jobhunt-chrome\"\n"
            "then re-run. Set jobhunt.browser.cdp_endpoint in "
            "development/config.yaml if you use a non-default host/port."
        )

    # Managed provider — verify the API-key env var is reachable.
    key_env = browser.get("key_env") or PROVIDER_DEFAULT_KEY_ENV.get(provider)
    if not key_env:
        return (
            f"job-hunt browser provider {provider!r} is not a known provider "
            "and declares no jobhunt.browser.key_env. Expected one of "
            f"cdp, {', '.join(sorted(PROVIDER_DEFAULT_KEY_ENV))}."
        )

    env = environ if environ is not None else dict(os.environ)
    if key_env in env:
        return None
    if key_env in read_dotenv_keys(_host_dotenv_path(hermes_home)):
        return None
    hermes_cfg = config.get("hermes") or {}
    profile_name = resolve_profile_name("jobhunt", hermes_cfg.get("profile_names"))
    if key_env in read_dotenv_keys(
        _profile_dotenv_path(profile_name, profiles_root=profiles_root)
    ):
        return None
    return (
        f"job-hunt browser provider {provider!r} needs the env var {key_env}, "
        "which is not set in the process env, ~/.hermes/.env, or "
        f"~/.hermes/profiles/{profile_name}/.env.\n"
        "Fix: set it in one of those locations. scientia does not manage "
        "secrets — this write is yours to make."
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="scientia-check-browser-provider",
        description="Preflight the job-hunt browser provider reachability.",
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

    reason = check_browser_provider(config=config)
    if reason is None:
        if config.get("jobhunt") is None:
            print("browser provider: jobhunt feature OFF — nothing to check")
        else:
            print("browser provider OK")
        return 0
    print(reason, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
