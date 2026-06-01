"""scientia.paths — the single source of file-layout truth (ADR-0005).

Every skill and module MUST resolve filesystem locations through this module
rather than hard-coding a literal path. The produced pipeline uses the brief's
flat ``proposals/<change-id>/`` tree — deliberately *not* OpenSpec's
``openspec/changes/`` + ``development/manifests/`` shape — because portability
forbids coupling produced artifacts to OpenSpec's directory contract (ADR-0005,
ADR-0011).

The project root defaults to the current working directory and can be overridden
with the ``SCIENTIA_ROOT`` environment variable, which keeps the helpers pure
(no global mutable state) and makes them trivially testable: point the env var
at a temp dir and every path follows.

Layout produced under the root::

    <root>/
    ├── references/                 # config.yaml + *.md.tmpl (bundle defaults)
    ├── sources/                    # raw inputs
    ├── wiki/                       # the typed-node knowledge graph
    └── proposals/<change-id>/
        ├── proposal.md
        ├── grill.md
        ├── decisions-log.md        # autonomous-mode entries
        ├── question-for-operator.md# pause_and_ask halt artifact
        ├── specs/
        ├── design.md
        ├── adrs/
        ├── tasks.md
        └── .advance/<stage>.ok     # package-owned stage-advance markers
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "project_root",
    "project_name",
    "references_dir",
    "config_path",
    "wiki_dir",
    "sources_dir",
    "proposals_dir",
    "change_dir",
    "proposal_path",
    "grill_path",
    "decisions_log_path",
    "question_for_operator_path",
    "specs_dir",
    "design_path",
    "adrs_dir",
    "tasks_path",
    "advance_dir",
    "advance_marker_path",
    "hermes_dir",
    "emit_ledger_path",
    "evidence_path",
]


def project_root() -> Path:
    """Return the project root.

    ``SCIENTIA_ROOT`` wins when set; otherwise the current working directory.
    """
    env = os.environ.get("SCIENTIA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd()


def project_name() -> str:
    """The current project's name — the basename of :func:`project_root`.

    Defaults the Hermes board name so each project's cards land on their own
    board rather than a shared default (see
    :func:`scientia.hermes.board.resolve_board`).
    """
    return project_root().name


def references_dir() -> Path:
    """Return the ``references/`` directory holding templates and ``config.yaml``.

    Prefers a project-local ``references/`` (so an operator can override the
    shipped defaults); otherwise falls back to the packaged ``references/`` that
    ships inside this package.
    """
    local = project_root() / "references"
    if local.is_dir():
        return local
    return Path(__file__).resolve().parent / "references"


def config_path() -> Path:
    """Path to ``config.yaml`` (confidence weights, thresholds, audit, modes)."""
    return references_dir() / "config.yaml"


def wiki_dir() -> Path:
    """Path to the typed-node knowledge-graph directory."""
    return project_root() / "wiki"


def sources_dir() -> Path:
    """Path to the raw-source inputs directory."""
    return project_root() / "sources"


def proposals_dir() -> Path:
    """Path to the root of all produced changes."""
    return project_root() / "proposals"


def change_dir(change_id: str) -> Path:
    """Path to a single change's directory: ``proposals/<change-id>/``."""
    return proposals_dir() / change_id


def proposal_path(change_id: str) -> Path:
    return change_dir(change_id) / "proposal.md"


def grill_path(change_id: str) -> Path:
    return change_dir(change_id) / "grill.md"


def decisions_log_path(change_id: str) -> Path:
    """Autonomous-mode low-confidence picks are appended here (ADR-0010)."""
    return change_dir(change_id) / "decisions-log.md"


def question_for_operator_path(change_id: str) -> Path:
    """A ``pause_and_ask`` stage emits this and halts until it is resolved."""
    return change_dir(change_id) / "question-for-operator.md"


def specs_dir(change_id: str) -> Path:
    return change_dir(change_id) / "specs"


def design_path(change_id: str) -> Path:
    return change_dir(change_id) / "design.md"


def adrs_dir(change_id: str) -> Path:
    """ADRs are scoped to the change (ADR-0005) — not a top-level ``adr/``."""
    return change_dir(change_id) / "adrs"


def tasks_path(change_id: str) -> Path:
    return change_dir(change_id) / "tasks.md"


def advance_dir(change_id: str) -> Path:
    """Directory holding the package-owned stage-advance markers (ADR-0006)."""
    return change_dir(change_id) / ".advance"


def advance_marker_path(change_id: str, stage: str) -> Path:
    """Path to the ``<stage>.ok`` marker that gates advancement past ``stage``."""
    return advance_dir(change_id) / f"{stage}.ok"


def hermes_dir(change_id: str) -> Path:
    """Directory holding the Hermes execution-layer artifacts for a change."""
    return change_dir(change_id) / "hermes"


def emit_ledger_path(change_id: str) -> Path:
    """The local key->id index written by ``scientia.hermes.apply`` (not truth;
    Hermes owns truth in its SQLite DB)."""
    return hermes_dir(change_id) / "emit-ledger.json"


def evidence_path(change_id: str) -> Path:
    """The neutral closed-loop sync artifact (M3): synthesized worker handoffs,
    deliberately *not* the wiki."""
    return change_dir(change_id) / "implementation-evidence.md"
