"""Tests for kg_pipeline.paths and the advance gate (ADR-0005, ADR-0006)."""

from pathlib import Path

import pytest

from kg_pipeline import advance, paths, templates


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("KG_PIPELINE_ROOT", str(tmp_path))
    return tmp_path


def test_paths_are_under_the_project_root(root):
    cid = "2026-05-28-demo"
    assert paths.project_root() == root
    assert paths.proposal_path(cid) == root / "proposals" / cid / "proposal.md"
    assert paths.grill_path(cid) == root / "proposals" / cid / "grill.md"
    assert paths.specs_dir(cid) == root / "proposals" / cid / "specs"
    assert paths.design_path(cid) == root / "proposals" / cid / "design.md"
    assert paths.adrs_dir(cid) == root / "proposals" / cid / "adrs"
    assert paths.tasks_path(cid) == root / "proposals" / cid / "tasks.md"
    assert paths.wiki_dir() == root / "wiki"
    assert paths.sources_dir() == root / "sources"


def test_references_dir_falls_back_to_bundle(root):
    # No project-local references/ -> the bundle's own references resolves.
    assert paths.references_dir().is_dir()
    assert (paths.references_dir() / "config.yaml").is_file()


def _render_proposal(cid):
    templates.render_to_file(
        "proposal", paths.proposal_path(cid), change_id=cid, topic="t", created="2026-05-28",
        why="w", context_from_kg="c", prior_art_from_kg="p", candidate_problems="cp",
        constraints_from_kg="cn", proposed_change="pc", open_questions="oq",
    )


def test_advance_writes_marker_only_when_validation_passes(root):
    cid = "2026-05-28-demo"
    paths.change_dir(cid).mkdir(parents=True)
    # No proposal yet -> validation fails -> no marker.
    res = advance.advance(cid, "proposal")
    assert res.ok is False and res.errors
    assert not advance.is_advanced(cid, "proposal")
    # Render a conforming proposal -> marker written.
    _render_proposal(cid)
    res = advance.advance(cid, "proposal")
    assert res.ok is True
    assert advance.is_advanced(cid, "proposal")
    assert paths.advance_marker_path(cid, "proposal").exists()


def test_advance_removes_a_stale_marker_when_a_stage_starts_failing(root):
    cid = "2026-05-28-demo"
    paths.change_dir(cid).mkdir(parents=True)
    _render_proposal(cid)
    assert advance.advance(cid, "proposal").ok
    # Corrupt the artifact -> the next advance must remove the marker.
    paths.proposal_path(cid).write_text("# nothing useful\n", encoding="utf-8")
    res = advance.advance(cid, "proposal")
    assert res.ok is False
    assert not advance.is_advanced(cid, "proposal")


def test_unknown_stage_raises(root):
    with pytest.raises(ValueError):
        advance.advance("c", "not-a-stage")
