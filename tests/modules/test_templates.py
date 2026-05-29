"""Tests for scientia.templates (spec: pipeline-tooling; ADR-0008)."""

from pathlib import Path

import pytest

from scientia import templates


@pytest.fixture
def refs_root(tmp_path, monkeypatch):
    """A project root with a tiny references/ dir, isolated via env var."""
    refs = tmp_path / "references"
    refs.mkdir()
    monkeypatch.setenv("SCIENTIA_ROOT", str(tmp_path))
    return refs


def test_render_by_flat_dict_substitution(refs_root):
    (refs_root / "demo.md.tmpl").write_text("id is {change_id}\n", encoding="utf-8")
    assert templates.render("demo", change_id="2026-05-28-x") == "id is 2026-05-28-x\n"


def test_literal_braces_are_doubled(refs_root):
    (refs_root / "demo.md.tmpl").write_text("literal {{x}} and var {v}\n", encoding="utf-8")
    assert templates.render("demo", v="V") == "literal {x} and var V\n"


def test_missing_placeholder_raises_template_error(refs_root):
    (refs_root / "demo.md.tmpl").write_text("{present} {absent}\n", encoding="utf-8")
    with pytest.raises(templates.TemplateError) as exc:
        templates.render("demo", present="p")
    assert "absent" in str(exc.value)


def test_unknown_template_raises(refs_root):
    with pytest.raises(templates.TemplateError):
        templates.render("does-not-exist")


def test_render_to_file_is_idempotent(refs_root, tmp_path):
    (refs_root / "demo.md.tmpl").write_text("hello {who}\n", encoding="utf-8")
    out = tmp_path / "out.md"
    templates.render_to_file("demo", out, who="world")
    first = out.read_bytes()
    templates.render_to_file("demo", out, who="world")
    assert out.read_bytes() == first


def test_shipped_templates_all_resolve(monkeypatch):
    # With no project-local references/, the bundle's own templates resolve.
    monkeypatch.delenv("SCIENTIA_ROOT", raising=False)
    for name in ("proposal", "grill", "gherkin-spec", "adr", "c4", "tasks", "wiki-page"):
        assert templates.template_path(name).is_file()
