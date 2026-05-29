"""scientia.hermes.preflight — environment checks before emit (IMPURE).

Emit must never silently no-op, so this gate runs first. It is one of the only
two impure modules in the layer (the other is :mod:`.apply`): it inspects the
``dir:`` workspaces, refuses a non-loopback ``rest_base`` (the kanban routes are
unauthenticated — §12), and — when ``require_gateway`` — probes that the Hermes
gateway is actually accepting connections, since ``ready`` tasks sit forever
without it.

When profiles carry a :class:`~scientia.hermes.plan.ProfileModel`, preflight
also checks that every referenced ``api_key_env`` variable is actually present
in the environment.  A missing key would cause a runtime failure deep in a
worker — far better to catch it at the gate.

The probe is injectable (``gateway_probe``) so the deterministic suite can run
this module with no Hermes present.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urlsplit

from scientia.hermes.plan import EmitPlan

__all__ = ["PreflightResult", "check"]

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", ""}


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _default_gateway_probe(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host or "127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def check(
    plan: EmitPlan,
    *,
    require_gateway: bool = True,
    rest_base: str = "http://127.0.0.1:8787/api/plugins/kanban",
    known_profiles: Optional[set[str]] = None,
    allow_remote: bool = False,
    gateway_probe: Optional[Callable[[str, int], bool]] = None,
) -> PreflightResult:
    """Validate the runtime can actually accept this plan's mutations."""
    errors: list[str] = []
    warnings: list[str] = []

    split = urlsplit(rest_base)
    host = split.hostname or ""
    port = split.port or (443 if split.scheme == "https" else 80)
    if host not in _LOOPBACK_HOSTS and not allow_remote:
        errors.append(
            f"rest_base host {host!r} is not loopback; the kanban routes are "
            f"unauthenticated — keep it on 127.0.0.1 or pass allow_remote"
        )

    cards = ([plan.epic] + list(plan.cards)) if plan.epic is not None else list(plan.cards)
    for card in cards:
        if card.workspace.startswith("dir:"):
            target = card.workspace[len("dir:"):]
            if not target.startswith("/"):
                errors.append(
                    f"card {card.key!r} workspace {card.workspace!r} is not an "
                    f"absolute path (confused-deputy guard)"
                )
        if card.stage != "epic" and not card.assignee:
            errors.append(f"work card {card.key!r} has no assignee")
        elif (
            known_profiles is not None
            and card.assignee
            and card.assignee not in known_profiles
        ):
            errors.append(
                f"card {card.key!r} assignee {card.assignee!r} is not a provisioned "
                f"profile — run scientia-hermes-init"
            )

    if require_gateway:
        probe = gateway_probe or _default_gateway_probe
        if not probe(host, port):
            errors.append(
                f"Hermes gateway not reachable at {host}:{port}; start it "
                f"(`hermes gateway start`) or ready tasks will sit forever"
            )

    # Model config gate: every card with a ProfileModel that names an api_key_env
    # must find that variable set in the environment.
    _KNOWN_PROVIDERS = {"fireworks", "openai", "anthropic", "google", "mistral", "together", "deepseek", "local"}
    seen_envs: set[str] = set()
    for card in cards:
        if card.model is None:
            continue
        if card.model.provider not in _KNOWN_PROVIDERS:
            warnings.append(
                f"card {card.key!r} model provider {card.model.provider!r} is not "
                f"in the known set {{'fireworks', 'openai', 'anthropic', ...}}; "
                f"ensure the Hermes backend supports it"
            )
        if not card.model.model:
            errors.append(
                f"card {card.key!r} has a model config but no model identifier"
            )
        if card.model.api_key_env:
            env_name = card.model.api_key_env
            if env_name not in seen_envs:
                seen_envs.add(env_name)
                if env_name not in os.environ:
                    errors.append(
                        f"card {card.key!r} model requires env var {env_name!r} "
                        f"but it is not set; export it before emit"
                    )

    return PreflightResult(ok=not errors, errors=errors, warnings=warnings)
