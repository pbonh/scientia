"""scientia.hermes.board — resolve the Kanban board name and profile names.

The board a change is emitted onto defaults to the **current project's name**, so
a Hermes install shared across projects keeps each project's cards on their own
board instead of piling them onto one shared default. An explicit ``board:`` slug
in the ``hermes:`` config block overrides this; an empty or absent ``board:``
resolves to the project name.

Profile names are **automatically** prefixed with the board slug so different
boards have different execution profiles — each carrying its own project-specific
system prompt (SOUL.md). No configuration is needed: the prefix defaults to the
board slug (itself defaulting to the project name). An explicit
``profile_prefix:`` in the ``hermes:`` config block overrides the default. An
empty string (``profile_prefix: ""``) disables prefixing for backward
compatibility with pre-0.3 setups.

Both :doc:`scientia-hermes-init <scientia-hermes-init/SKILL>` (which *provisions*
the board and profiles) and :doc:`scientia-hermes-emit <scientia-hermes-emit/SKILL>`
(which *routes onto* it) call :func:`resolve_board` and :func:`prefixed_profile`,
so the two phases can never disagree on the name — init never creates a board
or profile that emit then misses.

This is config resolution, not part of the pure plan seam: by default it reads
the project name from the environment (cwd / ``SCIENTIA_ROOT``). Pass ``project``
explicitly to keep it deterministic in tests.
"""

from __future__ import annotations

import re
from typing import Optional

from scientia import paths

__all__ = ["slugify", "resolve_board", "resolve_profile_prefix", "prefixed_profile"]


def slugify(name: str) -> str:
    """Lowercase, hyphen-separated slug safe for a Hermes board name.

    Runs of non-alphanumerics collapse to a single ``-`` and leading/trailing
    hyphens are trimmed (``"Scientia KG"`` -> ``"scientia-kg"``).
    """
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def resolve_board(configured: Optional[str], *, project: Optional[str] = None) -> str:
    """Resolve the board name from the ``hermes.board`` config value.

    An explicit, non-empty ``configured`` slug wins (returned trimmed, as-is);
    an empty string or ``None`` falls back to the slug of the current project
    name. ``project`` overrides the project-name source (default:
    :func:`scientia.paths.project_name`), so callers/tests can resolve a board
    without touching the working directory.
    """
    if configured and configured.strip():
        return configured.strip()
    return slugify(project if project is not None else paths.project_name())


def resolve_profile_prefix(
    configured: Optional[str],
    *,
    board: Optional[str] = None,
    project: Optional[str] = None,
) -> str:
    """Resolve the profile-name prefix from the ``hermes.profile_prefix`` config value.

    **The default is automatic prefixing.** When ``configured`` is ``None`` (key
    absent from config), the prefix defaults to the board slug — which itself
    defaults to the slug of the current project name. This means a project
    called "Circuit Solver Beta" automatically gets profiles named
    ``circuit-solver-beta-implementer``, ``circuit-solver-beta-reviewer``, etc.
    with zero configuration.

    An explicit non-empty ``configured`` prefix wins (returned trimmed).
    An empty string (``profile_prefix: ""``) explicitly *disables* prefixing
    for backward compatibility with pre-0.3 setups.

    The resolved prefix is used by :func:`prefixed_profile` to construct
    project-scoped profile names, so each board's agents carry their
    own project-specific system prompt.

    ``board`` and ``project`` mirrors :func:`resolve_board` overrides for tests.
    """
    if configured is not None and configured.strip() == "":
        return ""  # explicit empty = no prefix (backward compat)
    if configured and configured.strip():
        return configured.strip()
    # Default: use the board slug as the prefix.
    return resolve_board(None, project=project) if board is None else board


def prefixed_profile(prefix: str, role: str) -> str:
    """Construct a prefixed profile name: ``<prefix>-<role>``.

    When ``prefix`` is empty, returns ``role`` unchanged (backward compatibility
    with unprefixed profile names like ``implementer``). When ``prefix`` is set,
    returns ``<prefix>-<role>`` (e.g. ``circuit-solver-beta-implementer``).

    ``role`` is one of the canonical role names: ``implementer``, ``reviewer``,
    ``integrator``, ``conflict-resolver``. The function is generic and does not
    enforce this — any role string works.
    """
    if not prefix:
        return role
    return f"{prefix}-{role}"
