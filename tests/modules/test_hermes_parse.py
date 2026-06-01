"""Tests for scientia.hermes.parse (AC-1, AC-16)."""

from pathlib import Path

from scientia.hermes import parse

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"


def test_one_task_per_checkbox_with_attached_markers():
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    assert [t.number for t in tasks] == [1, 2, 3, 4]
    t1 = tasks[0]
    assert t1.title == "Define the EffectiveScore contract"
    assert t1.spec_refs == ("confidence-math#effective-score",)
    assert t1.adr_ref == "ADR-0004"
    assert t1.component == "confidence"
    assert t1.touches == ("src/scientia/confidence.py",)
    assert t1.produces_contracts == ("confidence.EffectiveScore",)
    assert t1.uses_contracts == ()


def test_multi_id_depends_on_clause():
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    assert tasks[1].depends_on == (1,)
    assert tasks[3].depends_on == (1, 3)  # "(depends on #1, #3)"


def test_uses_contract_marker_attaches():
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    assert tasks[1].uses_contracts == ("confidence.EffectiveScore",)


def test_inline_trailing_comment_attaches_and_is_stripped_from_title():
    tasks = parse.parse_tasks("- [ ] **7.** Do it <!-- traces-spec: cap#s1 -->\n")
    assert tasks[0].title == "Do it"
    assert tasks[0].spec_refs == ("cap#s1",)


def test_absent_markers_tolerated():
    tasks = parse.parse_tasks("- [ ] **1.** bare task\n")
    t = tasks[0]
    assert t.component is None and t.adr_ref is None
    assert t.spec_refs == () and t.touches == () and t.depends_on == ()


def test_comment_block_separated_by_prose_does_not_attach():
    text = (
        "<!-- component: confidence -->\n"
        "Some intervening prose paragraph.\n"
        "- [ ] **1.** task\n"
    )
    assert parse.parse_tasks(text)[0].component is None


def test_blank_lines_between_comment_block_and_task_are_tolerated():
    text = "<!-- component: confidence -->\n\n\n- [ ] **1.** task\n"
    assert parse.parse_tasks(text)[0].component == "confidence"


def test_parse_design_extracts_c4_component_map_and_contracts():
    c4, comp_map, contracts = parse.parse_design((FIX / "design.md").read_text())
    assert len(c4) == 1
    assert c4[0].level == "C4Container"
    assert c4[0].title == "Containers — RAG replacement"
    assert "C4Container" in c4[0].mermaid  # captured verbatim
    assert comp_map.owned["confidence"] == (
        "src/scientia/confidence.py",
        "tests/modules/test_confidence.py",
    )
    assert comp_map.owned["wiki"] == ("src/scientia/wiki/**", "tests/modules/test_wiki.py")
    assert contracts == [
        parse.Contract(
            name="confidence.EffectiveScore", owner="confidence", ratified_by="ADR-0004"
        )
    ]


def test_parse_design_without_prevention_sections_degrades():
    text = "# Design\n```mermaid\nC4Container\nContainer(a, \"A\")\n```\n"
    c4, comp_map, contracts = parse.parse_design(text)
    assert len(c4) == 1 and comp_map.owned == {} and contracts == []


def test_non_c4_mermaid_block_is_not_a_c4_diagram():
    c4, _, _ = parse.parse_design("```mermaid\nflowchart TB\nA-->B\n```\n")
    assert c4 == []
