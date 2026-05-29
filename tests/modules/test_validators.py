"""Tests for scientia.validators (spec: pipeline-tooling; ADR-0007)."""

from pathlib import Path

from scientia import validators

PROPOSAL_OK = """---
change-id: c
---
# Why
x
## Context (from KG)
x
## Prior Art (from KG)
x
## Candidate Problems
x
## Constraints (from KG)
x
## Proposed Change
x
## Open Questions
x
"""


def _skill(tmp_path, dirname, name, description="d" ):
    d = tmp_path / dirname
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# body\n", encoding="utf-8"
    )
    return d / "SKILL.md"


def test_conforming_proposal_validates_clean(tmp_path):
    p = tmp_path / "proposal.md"
    p.write_text(PROPOSAL_OK, encoding="utf-8")
    assert validators.validate_proposal(p) == []


def test_non_conforming_proposal_reports_missing_section(tmp_path):
    p = tmp_path / "proposal.md"
    p.write_text(PROPOSAL_OK.replace("# Why\nx\n", ""), encoding="utf-8")
    errors = validators.validate_proposal(p)
    assert any("Why" in e for e in errors)


def test_skill_md_name_matches_directory(tmp_path):
    ok = _skill(tmp_path, "seed-proposal", "seed-proposal")
    assert validators.validate_skill_md(ok) == []


def test_flag_skill_md_whose_name_mismatches_its_directory(tmp_path):
    bad = _skill(tmp_path, "seed-proposal", "seed_proposal")
    errors = validators.validate_skill_md(bad)
    assert any("does not match" in e for e in errors)
    # 'seed_proposal' also violates kebab-case.
    assert any("kebab-case" in e for e in errors)


def test_skill_md_description_length_cap(tmp_path):
    bad = _skill(tmp_path, "x", "x", description="z" * 1100)
    assert any("1024" in e for e in validators.validate_skill_md(bad))


def test_invalid_yaml_frontmatter_is_reported(tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    sk = d / "SKILL.md"
    sk.write_text('---\nname: x\ndescription: has a "bad: colon" inline\n---\n', encoding="utf-8")
    assert any("not valid YAML" in e for e in validators.validate_skill_md(sk))


def test_design_requires_c4container(tmp_path):
    d = tmp_path / "design.md"
    d.write_text("# Design\n```mermaid\nflowchart TB\nA-->B\n```\n", encoding="utf-8")
    assert any("C4Container" in e for e in validators.validate_design(d))
    d.write_text("# Design\n```mermaid\nC4Container\nContainer(a, \"A\")\n```\n", encoding="utf-8")
    assert validators.validate_design(d) == []


def test_tasks_requires_checkboxes_and_traces(tmp_path):
    t = tmp_path / "tasks.md"
    t.write_text("# Tasks\n- [ ] do it <!-- traces-spec: cap#s1 -->\n", encoding="utf-8")
    assert validators.validate_tasks(t) == []
    t.write_text("# Tasks\nno checkboxes here\n", encoding="utf-8")
    assert validators.validate_tasks(t)


def test_design_prevention_gate_requires_component_map_and_contracts(tmp_path):
    d = tmp_path / "design.md"
    base = "# Design\n```mermaid\nC4Container\nContainer(a, \"A\")\n```\n"
    d.write_text(base)
    # Off by default: a plain C4 design is fine (backward compatible / AC-16).
    assert validators.validate_design(d) == []
    # On: the Component Map + Shared Contracts sections become mandatory.
    errors = validators.validate_design(d, require_prevention=True)
    assert any("Component Map" in e for e in errors)
    assert any("Shared Contracts" in e for e in errors)
    full = base + "\n## Component Map\n- c: a.py\n\n## Shared Contracts\n- c.X — owner: c\n"
    d.write_text(full)
    assert validators.validate_design(d, require_prevention=True) == []


def test_tasks_prevention_gate_requires_ownership_markers(tmp_path):
    t = tmp_path / "tasks.md"
    bare = "# Tasks\n- [ ] **1.** do it <!-- traces-spec: cap#s1 -->\n"
    t.write_text(bare)
    # Off by default: still clean (AC-16).
    assert validators.validate_tasks(t) == []
    # On: the task needs component + touches markers.
    errors = validators.validate_tasks(t, require_prevention=True)
    assert any("component" in e for e in errors)
    assert any("touches" in e for e in errors)
    owned = (
        "# Tasks\n<!-- traces-spec: cap#s1 -->\n<!-- component: c -->\n"
        "<!-- touches: a.py -->\n- [ ] **1.** do it\n"
    )
    t.write_text(owned)
    assert validators.validate_tasks(t, require_prevention=True) == []


def test_grill_blocks_while_unaddressed(tmp_path):
    g = tmp_path / "grill.md"
    body = (
        "# Grill\n## Open Questions\n<!-- entry\nid: q1\naddressed: false\n-->\n"
        "## Counter-Claims\n_none_\n## Hidden-Assumption Challenges\n_none_\n"
        "## Failure-Pattern Warnings\n_none_\n## Responses\npending\n"
    )
    g.write_text(body, encoding="utf-8")
    assert any("unaddressed" in e for e in validators.validate_grill(g))
    g.write_text(body.replace("addressed: false", "addressed: true"), encoding="utf-8")
    assert validators.validate_grill(g) == []
