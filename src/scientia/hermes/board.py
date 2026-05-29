"""scientia.hermes.board — resolve the Kanban board name (config + project).

The board a change is emitted onto defaults to the **current project's name**, so
a Hermes install shared across projects keeps each project's cards on its own
board instead of piling them onto one shared default. An explicit ``board:`` slug
in the ``hermes:`` config block overrides this; an empty or absent ``board:``
resolves to the project name.

Both :doc:`scientia-hermes-init <scientia-hermes-init/SKILL>` (which *provisions*
the board) and :doc:`scientia-hermes-emit <scientia-hermes-emit/SKILL>` (which
*routes onto* it) call :func:`resolve_board`, so the two phases can never disagree
on the name — init never creates a board that emit then misses.

This is config resolution, not part of the pure plan seam: by default it reads
the project name from the environment (cwd / ``SCIENTIA_ROOT``). Pass ``project``
explicitly to keep it deterministic in tests.
"""

from __future__ import annotations

import re
from typing import Optional

from scientia import paths

__all__ = ["slugify", "resolve_board"]


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
