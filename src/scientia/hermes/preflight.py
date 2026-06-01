"""scientia.hermes.preflight — environment checks before emit (IMPURE).

Emit must never silently no-op, so this gate runs first. It is one of the only
two impure modules in the layer (the other is :mod:`.apply`): it inspects the
``dir:`` workspaces, refuses a non-loopback ``rest_base`` for the ``rest``
backend (those kanban routes are unauthenticated — §12), and — when
``require_gateway`` — checks that the board is actually reachable, since
``ready`` tasks sit forever otherwise.

The reachability check is **backend-aware**. For ``backend="rest"`` it probes
the gateway's HTTP port. For ``backend="cli"`` there is no HTTP endpoint (plain
``hermes gateway`` is the *messaging* gateway and serves no kanban API), so it
instead verifies the ``hermes`` CLI is on PATH and warns that a dispatcher (the
gateway service or a ``hermes kanban dispatch`` loop) must be running.

When profiles carry a :class:`~scientia.hermes.plan.ProfileModel`, preflight
also checks that every referenced ``api_key_env`` variable is actually present
in the environment.  A missing key would cause a runtime failure deep in a
worker — far better to catch it at the gate.

The probe is injectable (``gateway_probe``) so the deterministic suite can run
this module with no Hermes present.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional, Sequence
from urllib.parse import urlsplit

from scientia.hermes.plan import EmitPlan

if TYPE_CHECKING:  # annotations only — avoids any import-time coupling
    from scientia.hermes.parse import ComponentMap, Task

__all__ = ["PreflightResult", "check", "gateway_check", "repo_reality_check"]

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", ""}
_DASHBOARD_DEFAULT_PORT = 9119


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


def _default_dashboard_probe(port: int = _DASHBOARD_DEFAULT_PORT) -> bool:
    """Probe whether the Hermes dashboard is listening on its default port."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def _default_cli_probe() -> bool:
    return shutil.which("hermes") is not None


def _run_git(args: list[str]) -> list[str]:
    """Run a read-only git command in the cwd; return stripped output lines.

    Returns ``[]`` on any failure (git absent, non-zero exit, timeout) so the
    git-grounded guards degrade to "no findings" rather than raising at the gate.
    """
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _default_branch_probe() -> list[str]:
    """Every local branch short-ref in the current repo."""
    return _run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads"])


def _default_tree_probe(base_sha: str) -> list[str]:
    """Every tracked path in the trunk tree at ``base_sha``."""
    return _run_git(["ls-tree", "-r", "--name-only", base_sha])


def check(
    plan: Optional[EmitPlan],
    *,
    require_gateway: bool = True,
    backend: str = "rest",
    rest_base: str = "http://127.0.0.1:8787/api/plugins/kanban",
    known_profiles: Optional[set[str]] = None,
    allow_remote: bool = False,
    gateway_probe: Optional[Callable[[str, int], bool]] = None,
    cli_probe: Optional[Callable[[], bool]] = None,
) -> PreflightResult:
    """Validate the runtime can actually accept this plan's mutations.

    ``plan`` may be ``None`` for a gateway-only reachability probe — all
    card-level checks (workspace, assignee, profile, model) are skipped.
    Pass a real ``EmitPlan`` before emit to get the full validation.
    """
    errors: list[str] = []
    warnings: list[str] = []

    split = urlsplit(rest_base)
    host = split.hostname or ""
    port = split.port or (443 if split.scheme == "https" else 80)
    # The loopback guard only applies to the REST backend — `rest_base` is unused
    # for the CLI backend, which talks to the SQLite board directly.
    if backend == "rest" and host not in _LOOPBACK_HOSTS and not allow_remote:
        errors.append(
            f"rest_base host {host!r} is not loopback; the kanban routes are "
            f"unauthenticated — keep it on 127.0.0.1 or pass allow_remote"
        )

    cards = []
    if plan is not None:
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
        if backend == "cli":
            # No HTTP endpoint to probe; the board is reached through the CLI.
            if not (cli_probe or _default_cli_probe)():
                errors.append(
                    "the `hermes` CLI is not on PATH; install Hermes or the cli "
                    "backend cannot reach the board"
                )
            else:
                # Board-scoped dispatch recommendation (friction point #6)
                board_slug = (plan.board if plan is not None else None) or "<board-slug>"
                warnings.append(
                    "backend=cli: ensure a dispatcher is running — use "
                    f"`hermes kanban --board {board_slug} daemon --interval 60` "
                    f"for board-scoped dispatch rather than the gateway's "
                    f"embedded dispatcher (which is board-unscoped and may "
                    f"spawn workers on unrelated boards). "
                    f"CRITICAL: run this command from the project root directory — "
                    f"Hermes creates worker worktrees relative to the daemon's cwd; "
                    f"starting from the wrong repo lands all workers in that repo's "
                    f"worktrees instead (use `cd <project-root>` first or set "
                    f"`SCIENTIA_ROOT` before starting the daemon)"
                )
        else:
            probe = gateway_probe or _default_gateway_probe
            if not probe(host, port):
                # Dashboard port mismatch diagnostic (friction point #6)
                dashboard_probe = _default_dashboard_probe
                if dashboard_probe():
                    errors.append(
                        f"Hermes gateway not reachable at {host}:{port}, but the "
                        f"dashboard IS running on port {_DASHBOARD_DEFAULT_PORT}. "
                        f"Start with `hermes dashboard --port {port}` or update "
                        f"`rest_base` to http://127.0.0.1:{_DASHBOARD_DEFAULT_PORT}/api/plugins/kanban"
                    )
                else:
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


def gateway_check(
    *,
    backend: str = "rest",
    rest_base: str = "http://127.0.0.1:8787/api/plugins/kanban",
    board: Optional[str] = None,
    allow_remote: bool = False,
    gateway_probe: Optional[Callable[[str, int], bool]] = None,
    cli_probe: Optional[Callable[[], bool]] = None,
) -> PreflightResult:
    """Convenience wrapper: run only gateway and CLI reachability checks.

    Use this during ``scientia-hermes-init`` before a plan exists — it runs
    the same backend-aware gateway checks as :func:`check` but skips all
    card-level validation (workspace, assignee, profile, model).
    """
    from scientia.hermes.plan import EmitPlan  # local import avoids cycle

    dummy = EmitPlan(
        change_id="__probe__",
        board=board or "",
        epic=None,
        cards=(),
    )
    return check(
        dummy,
        require_gateway=True,
        backend=backend,
        rest_base=rest_base,
        allow_remote=allow_remote,
        gateway_probe=gateway_probe,
        cli_probe=cli_probe,
    )


def repo_reality_check(
    plan: EmitPlan,
    *,
    comp_map: Optional["ComponentMap"] = None,
    tasks: Sequence["Task"] = (),
    base_sha: Optional[str] = None,
    branch_probe: Optional[Callable[[], list[str]]] = None,
    tree_probe: Optional[Callable[[str], list[str]]] = None,
) -> PreflightResult:
    """Git-grounded guards that catch a plan detached from the repo it will run in.

    Two checks, both deterministic given their injected probes (so the
    deterministic suite runs them with no git present):

    1. **Cross-lane branch collision.** Several boards can target the SAME
       ``change_id`` inside ONE git repo (a shared object store / branch
       namespace). If sibling-lane task branches for this ``change_id`` already
       exist, an integrator that reconstructs ``<change-id>/task-N`` merges the
       wrong lane's work — the failure that corrupted circuit-solver-delta's
       trunk. An **unset board** (which produces bare, collision-prone refs while
       sibling lanes exist) is an ERROR; a **set board** (namespaced refs) is a
       WARNING so the operator knows the repo is shared.

    2. **Component Map vs trunk.** Owned-glob roots with no presence on trunk @
       ``base_sha`` are surfaced as WARNINGS — workers will otherwise improvise a
       layout the touches/wave/contract math never modeled.

    Each check is skipped cleanly when its inputs are absent. Probes default to
    shelling out to ``git`` in the cwd and return empty on any failure, so this
    never raises. Run it at emit step 7, alongside :func:`check`.
    """
    from scientia.hermes import validators  # local import keeps module load light

    errors: list[str] = []
    warnings: list[str] = []

    bp = branch_probe or _default_branch_probe
    sibling = validators.cross_lane_task_branches(plan.change_id, plan.board, bp())
    if sibling:
        lanes_desc = "; ".join(
            f"{lane or '(bare, no board prefix)'}: {len(refs)} branch(es)"
            for lane, refs in sibling.items()
        )
        if not (plan.board or "").strip():
            errors.append(
                f"change-id {plan.change_id!r} already has task branches from "
                f"other lane(s) in this git repo [{lanes_desc}], but this emit "
                f"has no board set — it would produce bare `<change-id>/task-N` "
                f"refs in a repo already shared by other lanes, where an "
                f"integrator cannot tell them apart. Set `hermes.board` so this "
                f"lane's branches are namespaced like the others "
                f"(`<board>/<change-id>/task-N`)."
            )
        else:
            warnings.append(
                f"change-id {plan.change_id!r} also has task branches in sibling "
                f"lane(s) sharing this git repo [{lanes_desc}]. This lane's "
                f"branches are namespaced under `{plan.board}/` so they will not "
                f"collide, but integrators must merge the handed-off branch/SHA, "
                f"never a reconstructed `<change-id>/task-N` (which resolves to a "
                f"sibling lane's work)."
            )

    if comp_map is not None and base_sha:
        tp = tree_probe or _default_tree_probe
        warnings.extend(validators.component_map_reality(comp_map, tasks, tp(base_sha)))

    return PreflightResult(ok=not errors, errors=errors, warnings=warnings)
