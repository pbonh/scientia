"""Tests for scientia.hermes.board — board-name resolution, profile prefix, and
prefixed-profile construction."""

from __future__ import annotations

import importlib

import scientia.paths as paths
from scientia.hermes import board


def test_explicit_board_slug_wins():
    assert board.resolve_board("my-team-board", project="scientia") == "my-team-board"
    # surrounding whitespace is trimmed, but the slug is otherwise taken as-is
    assert board.resolve_board("  spaced  ", project="scientia") == "spaced"


def test_empty_or_absent_board_falls_back_to_project_name():
    assert board.resolve_board("", project="scientia") == "scientia"
    assert board.resolve_board(None, project="Scientia KG") == "scientia-kg"


def test_resolve_board_uses_current_project_name_by_default(tmp_path, monkeypatch):
    root = tmp_path / "My Project"
    root.mkdir()
    monkeypatch.setenv("SCIENTIA_ROOT", str(root))
    importlib.reload(paths)
    importlib.reload(board)
    assert board.resolve_board("") == "my-project"
    # cleanup: reload without the env override so other tests see defaults
    monkeypatch.delenv("SCIENTIA_ROOT", raising=False)
    importlib.reload(paths)
    importlib.reload(board)


def test_slugify():
    assert board.slugify("Scientia KG") == "scientia-kg"
    assert board.slugify("  Mixed_Case/Name  ") == "mixed-case-name"
    assert board.slugify("already-a-slug") == "already-a-slug"


# --------------------------------------------------------------------------- #
# resolve_profile_prefix                                                       #
# --------------------------------------------------------------------------- #


def test_profile_prefix_explicit_nonempty_wins():
    assert board.resolve_profile_prefix("my-prefix", board="circuit-solver-beta") == "my-prefix"
    assert board.resolve_profile_prefix("  csb  ", board="circuit-solver-beta") == "csb"


def test_profile_prefix_empty_string_disables_prefixing():
    """An explicit empty string means 'no prefix' (backward compat)."""
    assert board.resolve_profile_prefix("", board="circuit-solver-beta") == ""


def test_profile_prefix_none_defaults_to_board_slug():
    """Absent config (None) defaults to the board slug."""
    assert board.resolve_profile_prefix(None, board="circuit-solver-beta") == "circuit-solver-beta"


def test_profile_prefix_none_defaults_to_project_name_when_no_board():
    """When no board is given either, falls back to project name slug."""
    assert board.resolve_profile_prefix(None, project="Circuit Solver Beta") == "circuit-solver-beta"


def test_profile_prefix_whitespace_only_treated_as_empty():
    """A whitespace-only string is treated as empty (disables prefixing)."""
    assert board.resolve_profile_prefix("   ", board="circuit-solver-beta") == ""


# --------------------------------------------------------------------------- #
# prefixed_profile                                                            #
# --------------------------------------------------------------------------- #


def test_prefixed_profile_with_prefix():
    assert board.prefixed_profile("circuit-solver-beta", "implementer") == "circuit-solver-beta-implementer"
    assert board.prefixed_profile("circuit-solver-beta", "reviewer") == "circuit-solver-beta-reviewer"
    assert board.prefixed_profile("circuit-solver-beta", "integrator") == "circuit-solver-beta-integrator"
    assert board.prefixed_profile("circuit-solver-beta", "conflict-resolver") == "circuit-solver-beta-conflict-resolver"


def test_prefixed_profile_empty_prefix_returns_role_unchanged():
    """Empty prefix = backward compat (just 'implementer', not '-implementer')."""
    assert board.prefixed_profile("", "implementer") == "implementer"
    assert board.prefixed_profile("", "reviewer") == "reviewer"
    assert board.prefixed_profile("", "conflict-resolver") == "conflict-resolver"


def test_prefixed_profile_custom_short_prefix():
    assert board.prefixed_profile("csb", "implementer") == "csb-implementer"
    assert board.prefixed_profile("csb", "conflict-resolver") == "csb-conflict-resolver"


def test_prefixed_profile_is_pure_string_construction():
    """The function is generic — any role name works."""
    assert board.prefixed_profile("proj", "custom-role") == "proj-custom-role"


# --------------------------------------------------------------------------- #
# Integration: board + prefix + profile                                      #
# --------------------------------------------------------------------------- #


def test_full_resolution_chain_default():
    """The default chain: no board config, no prefix config → project name as both.
    This is the zero-config experience: just run init/emit and profiles are
    automatically prefixed with the project name."""
    board_name = board.resolve_board(None, project="Circuit Solver Beta")
    prefix = board.resolve_profile_prefix(None, board=board_name)
    assert prefix == "circuit-solver-beta"
    assert board.prefixed_profile(prefix, "implementer") == "circuit-solver-beta-implementer"
    assert board.prefixed_profile(prefix, "reviewer") == "circuit-solver-beta-reviewer"
    assert board.prefixed_profile(prefix, "conflict-resolver") == "circuit-solver-beta-conflict-resolver"


def test_full_resolution_chain_explicit_board_no_prefix():
    """Explicit board, no prefix config → board slug as prefix."""
    board_name = board.resolve_board("my-board")
    prefix = board.resolve_profile_prefix(None, board=board_name)
    assert prefix == "my-board"
    assert board.prefixed_profile(prefix, "reviewer") == "my-board-reviewer"


def test_full_resolution_chain_prefix_disabled():
    """Explicit empty profile_prefix disables prefixing."""
    board_name = board.resolve_board("my-board")
    prefix = board.resolve_profile_prefix("", board=board_name)
    assert prefix == ""
    assert board.prefixed_profile(prefix, "implementer") == "implementer"


def test_full_resolution_chain_custom_prefix():
    """Explicit custom prefix overrides the board default."""
    board_name = board.resolve_board("my-board")
    prefix = board.resolve_profile_prefix("custom", board=board_name)
    assert prefix == "custom"
    assert board.prefixed_profile(prefix, "integrator") == "custom-integrator"
