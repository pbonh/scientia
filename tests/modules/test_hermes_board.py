"""Tests for scientia.hermes.board — board-name resolution (config + project)."""

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
