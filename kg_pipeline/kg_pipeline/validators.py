"""kg_pipeline.validators — deterministic artifact validators (ADR-0007).

Each ``validate_*`` function returns a list of human-readable error strings; an
empty list means the artifact conforms. This error list is the deterministic
guardrail the controller gates on: :mod:`kg_pipeline.advance` writes a stage's
advance marker only when the matching validator returns no errors, so the
controller cannot advance past a failing stage (ADR-0006).

Validation is structural, not semantic: it checks that required sections,
headings, traceability markers, and SKILL.md frontmatter constraints are
present. It never judges prose quality — that is a skill's job.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

__all__ = [
    "validate_skill_md",
    "validate_proposal",
    "validate_grill",
    "validate_specs",
    "validate_design",
    "validate_adrs",
    "validate_tasks",
]

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)


# --------------------------------------------------------------------------- #
# Small shared helpers                                                        #
# --------------------------------------------------------------------------- #
def _read(path: Path) -> Optional[str]:
    path = Path(path)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> Optional[dict]:
    """Parse leading YAML frontmatter. Returns {} when absent, the parsed dict
    when present, or ``None`` when the frontmatter block is not valid YAML."""
    if not text.startswith("---"):
        return {}
    lines = text.split("\n")
    if lines[0] != "---":
        return {}
    for i in range(1, len(lines)):
        if lines[i] == "---":
            try:
                parsed = yaml.safe_load("\n".join(lines[1:i])) or {}
            except yaml.YAMLError:
                return None
            return parsed if isinstance(parsed, dict) else {}
    return {}


def _headings(text: str) -> set[str]:
    return {m.strip() for m in _HEADING_RE.findall(text)}


def _require_headings(text: str, required: list[str], errors: list[str]) -> None:
    present = _headings(text)
    # Match case-insensitively and ignore trailing punctuation.
    norm = {h.lower().rstrip(":") for h in present}
    for want in required:
        if want.lower().rstrip(":") not in norm:
            errors.append(f"missing required section: {want!r}")


# --------------------------------------------------------------------------- #
# SKILL.md (agentskills.io compliance)                                        #
# --------------------------------------------------------------------------- #
def validate_skill_md(path: Path) -> list[str]:
    """Validate a ``SKILL.md`` against agentskills.io frontmatter rules.

    Checks: ``name`` present, kebab-case, ≤64 chars, and equal to the parent
    directory name; ``description`` present and ≤1024 chars.
    """
    path = Path(path)
    errors: list[str] = []
    text = _read(path)
    if text is None:
        return [f"SKILL.md not found: {path}"]
    fm = _frontmatter(text)
    if fm is None:
        return [f"SKILL.md frontmatter is not valid YAML: {path}"]

    name = fm.get("name")
    if not name:
        errors.append("SKILL.md frontmatter is missing required field 'name'")
    else:
        name = str(name)
        if len(name) > 64:
            errors.append(f"'name' exceeds 64 characters ({len(name)})")
        if not _NAME_RE.match(name):
            errors.append(
                f"'name' {name!r} is not kebab-case "
                f"(lowercase a-z/0-9, hyphen-separated, no leading/trailing/double hyphens)"
            )
        dir_name = path.parent.name
        if name != dir_name:
            errors.append(
                f"'name' {name!r} does not match its directory {dir_name!r}"
            )

    description = fm.get("description")
    if not description:
        errors.append("SKILL.md frontmatter is missing required field 'description'")
    elif len(str(description)) > 1024:
        errors.append(f"'description' exceeds 1024 characters ({len(str(description))})")

    return errors


# --------------------------------------------------------------------------- #
# Pipeline artifacts                                                          #
# --------------------------------------------------------------------------- #
def validate_proposal(path: Path) -> list[str]:
    text = _read(path)
    if text is None:
        return [f"proposal.md not found: {path}"]
    errors: list[str] = []
    _require_headings(
        text,
        [
            "Why",
            "Context (from KG)",
            "Prior Art (from KG)",
            "Candidate Problems",
            "Constraints (from KG)",
            "Proposed Change",
            "Open Questions",
        ],
        errors,
    )
    return errors


def validate_grill(path: Path) -> list[str]:
    text = _read(path)
    if text is None:
        return [f"grill.md not found: {path}"]
    errors: list[str] = []
    _require_headings(
        text,
        [
            "Open Questions",
            "Counter-Claims",
            "Hidden-Assumption Challenges",
            "Failure-Pattern Warnings",
            "Responses",
        ],
        errors,
    )
    # The proposal cannot advance while any grill entry is unaddressed. Count
    # only real entry flags (a line that *starts* with `addressed:`), so prose
    # or examples mentioning the flag inline are not miscounted.
    unaddressed = len(re.findall(r"(?im)^addressed:\s*false\b", text))
    if unaddressed:
        errors.append(
            f"{unaddressed} grill entr{'y is' if unaddressed == 1 else 'ies are'} "
            f"unaddressed (addressed: false); resolve before advancing"
        )
    return errors


def validate_specs(specs_dir: Path) -> list[str]:
    specs_dir = Path(specs_dir)
    errors: list[str] = []
    if not specs_dir.is_dir():
        return [f"specs directory not found: {specs_dir}"]
    spec_files = sorted(specs_dir.rglob("*.md"))
    if not spec_files:
        errors.append(f"no spec files found under {specs_dir}")
    for spec in spec_files:
        text = spec.read_text(encoding="utf-8")
        if "Feature" not in text and "Scenario" not in text:
            errors.append(f"{spec.name}: no Feature/Scenario found")
        # One observable When per scenario (write-specs discipline / gherkin).
        scenarios = re.split(r"^#{2,4}\s+Scenario", text, flags=re.MULTILINE)[1:]
        for idx, block in enumerate(scenarios, start=1):
            whens = len(re.findall(r"(?m)^\s*When\b", block))
            if whens != 1:
                errors.append(
                    f"{spec.name}: scenario {idx} has {whens} 'When' steps (expected exactly 1)"
                )
    return errors


def validate_design(path: Path) -> list[str]:
    text = _read(path)
    if text is None:
        return [f"design.md not found: {path}"]
    errors: list[str] = []
    has_mermaid = "```mermaid" in text
    has_c4_container = "C4Container" in text
    if not (has_mermaid and has_c4_container):
        errors.append(
            "design.md must contain at least one mermaid C4Container diagram"
        )
    return errors


def validate_adrs(adrs_dir: Path) -> list[str]:
    adrs_dir = Path(adrs_dir)
    errors: list[str] = []
    if not adrs_dir.is_dir():
        return [f"adrs directory not found: {adrs_dir}"]
    adr_files = sorted(adrs_dir.glob("*.md"))
    if not adr_files:
        errors.append(f"no ADR files found under {adrs_dir}")
    for adr in adr_files:
        text = adr.read_text(encoding="utf-8")
        present = {h.lower().rstrip(":") for h in _headings(text)}
        for want in ("status", "context", "decision", "consequences"):
            if not any(want in h for h in present):
                errors.append(f"{adr.name}: missing '{want.title()}' section")
    return errors


def validate_tasks(path: Path) -> list[str]:
    text = _read(path)
    if text is None:
        return [f"tasks.md not found: {path}"]
    errors: list[str] = []
    checkboxes = re.findall(r"(?m)^\s*-\s*\[[ xX]\]", text)
    if not checkboxes:
        errors.append("tasks.md contains no checklist items ('- [ ]')")
    if "traces-spec" not in text:
        errors.append("tasks.md has no 'traces-spec' traceability markers")
    return errors
