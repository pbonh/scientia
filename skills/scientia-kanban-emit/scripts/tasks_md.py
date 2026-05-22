#!/usr/bin/env python3
"""tasks_md.py — parse `openspec/changes/<change>/tasks.md`.

The file is the canonical implementation plan for a scientia change.
Lines look like:

    - [ ] **N.** <imperative> — @spec: <cap>#<scenario> [@spec: ...]
                                @adr: ADR-NNNN
                                (depends on #M[, #M, ...])

Returns one TaskItem per `- [ ]`/`- [x]` line, in source order. Items
that don't match the canonical pattern are skipped (defensive — header
prose and blank lines).

Stdlib only.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# A task bullet starts with "- [ ]" or "- [x]" + "**N.**". Capture N and the
# rest of the line. The remainder is parsed separately to extract markers.
_BULLET_RE = re.compile(
    r"^\s*-\s+\[(?P<check>[ xX])\]\s+\*\*(?P<num>\d+)\.\*\*\s+(?P<body>.+?)\s*$"
)

# `@spec: <slug>#<scenario>` — capability is a kebab slug, scenario likewise.
_SPEC_RE = re.compile(
    r"@spec:\s*(?P<cap>[a-z0-9][a-z0-9\-]*)#(?P<scn>[a-z0-9][a-z0-9\-]*)"
)

_ADR_RE = re.compile(r"@adr:\s*(ADR-\d{3,5})", re.IGNORECASE)

# `(depends on #1, #2, #3)` — the inner list is one or more #N tokens.
_DEPENDS_RE = re.compile(
    r"\(depends on\s+(?P<list>#\d+(?:\s*,\s*#\d+)*)\s*\)",
    re.IGNORECASE,
)
_DEP_NUM_RE = re.compile(r"#(\d+)")

# Section heading inside tasks.md — `## Capability: <slug>` or `## Cross-Cutting...`
_SECTION_RE = re.compile(r"^##\s+(?P<heading>.+?)\s*$")

# `non-behavioral` marker (docs, CI, etc.) — used as a hint that the row should
# still be emitted, but it intentionally has no spec backlink.
_NON_BEHAVIORAL_RE = re.compile(r"\bnon-behavioral\b", re.IGNORECASE)


@dataclass(frozen=True)
class SpecRef:
    capability: str
    scenario_slug: str


@dataclass
class TaskItem:
    number: int                                # tasks.md "**N.**"
    title: str                                 # text before any @spec/@adr/(depends-on)
    section: str                               # nearest preceding "## ..." heading
    spec_refs: List[SpecRef] = field(default_factory=list)
    adr_refs: List[str] = field(default_factory=list)
    depends_on: List[int] = field(default_factory=list)
    non_behavioral: bool = False
    raw_line: str = ""                         # full source line, for hashing
    checked: bool = False                      # `- [x]` already done?

    @property
    def slug(self) -> str:
        # Stable, two-digit-zero-padded slug used in idempotency keys and titles.
        return f"task-{self.number:02d}"

    def hash(self) -> str:
        """sha256 of the raw line, used as the idempotency-key suffix.

        Stable across re-emits when this item's text is unchanged, even when
        other items in the same tasks.md churn.
        """
        return hashlib.sha256(self.raw_line.encode("utf-8")).hexdigest()


def _strip_markers(body: str) -> str:
    """Return the task title — body text with @spec/@adr/(depends on) removed."""
    text = _SPEC_RE.sub("", body)
    text = _ADR_RE.sub("", text)
    text = _DEPENDS_RE.sub("", text)
    # Collapse the em-dash separator that used to introduce markers, and any
    # double spaces left behind.
    text = re.sub(r"\s+—\s*$", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" —\t")


def parse_tasks_md(text: str) -> List[TaskItem]:
    """Return the ordered list of TaskItems found in `text`.

    Items are returned in source order. `depends_on` references items by their
    tasks.md number, NOT their list index — callers should resolve via a
    {number -> TaskItem} map.
    """
    items: List[TaskItem] = []
    current_section = ""

    for line in text.splitlines():
        section_match = _SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group("heading").strip()
            continue

        m = _BULLET_RE.match(line)
        if not m:
            continue

        number = int(m.group("num"))
        body = m.group("body")
        checked = m.group("check").lower() == "x"

        spec_refs = [
            SpecRef(capability=spec_m.group("cap"), scenario_slug=spec_m.group("scn"))
            for spec_m in _SPEC_RE.finditer(body)
        ]
        adr_refs = [adr_m.group(1).upper() for adr_m in _ADR_RE.finditer(body)]

        depends_on: List[int] = []
        dep_match = _DEPENDS_RE.search(body)
        if dep_match:
            for num_match in _DEP_NUM_RE.finditer(dep_match.group("list")):
                depends_on.append(int(num_match.group(1)))

        items.append(TaskItem(
            number=number,
            title=_strip_markers(body),
            section=current_section,
            spec_refs=spec_refs,
            adr_refs=adr_refs,
            depends_on=depends_on,
            non_behavioral=bool(_NON_BEHAVIORAL_RE.search(body)),
            raw_line=line,
            checked=checked,
        ))

    return items


def parse_tasks_file(path: Path) -> List[TaskItem]:
    """Convenience wrapper around `parse_tasks_md` taking a filesystem path."""
    return parse_tasks_md(path.read_text(encoding="utf-8"))


def topological_order(items: List[TaskItem]) -> List[TaskItem]:
    """Return `items` in topological order by `depends_on`.

    Stable: ties are broken by the original tasks.md number, so the result is
    deterministic across runs. Raises ValueError on a cycle.
    """
    by_number = {item.number: item for item in items}
    indegree = {item.number: 0 for item in items}
    children: dict[int, list[int]] = {item.number: [] for item in items}
    for item in items:
        for dep in item.depends_on:
            if dep not in by_number:
                # Dangling depends-on — ignore, the body validator surfaces it.
                continue
            indegree[item.number] += 1
            children[dep].append(item.number)

    ready = sorted([n for n, d in indegree.items() if d == 0])
    out: List[TaskItem] = []
    while ready:
        n = ready.pop(0)
        out.append(by_number[n])
        for child in children[n]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()

    if len(out) != len(items):
        cyclic = sorted(n for n, d in indegree.items() if d > 0)
        raise ValueError(f"tasks.md has a dependency cycle involving: {cyclic}")
    return out


def shared_infrastructure(items: List[TaskItem]) -> List[TaskItem]:
    """Return items that look like cross-cutting / shared infrastructure.

    Heuristic: any item with no `@spec:` marker. Callers typically narrow
    this further (e.g. only items with empty `depends_on`) when deciding
    which to wire as universal prereqs on every per-scenario impl row.

    Non-behavioral items (docs, CI, etc.) also have no `@spec:` marker; they
    appear here too. Callers that distinguish foundational scaffolding from
    trailing cross-cutting work should consult `depends_on` and
    `non_behavioral` on each item.
    """
    return [item for item in items if not item.spec_refs]


def items_for_scenario(
    items: List[TaskItem],
    capability: str,
    scenario_slug: str,
) -> List[TaskItem]:
    """Return tasks.md items whose `@spec` markers reference this scenario.

    Includes ALL transitively-required tasks (i.e. the closure under
    `depends_on`), since the scenario can't run until the whole prereq chain
    is integrated. Shared-infrastructure items (no spec ref) are NOT included
    here — callers pull those from `shared_infrastructure()` separately.
    """
    by_number = {item.number: item for item in items}
    target = SpecRef(capability=capability, scenario_slug=scenario_slug)

    seeds = [item for item in items if target in item.spec_refs]
    seen: set[int] = set()
    stack = list(seeds)
    while stack:
        item = stack.pop()
        if item.number in seen:
            continue
        seen.add(item.number)
        for dep in item.depends_on:
            if dep in by_number and dep not in seen:
                stack.append(by_number[dep])

    return [item for item in items if item.number in seen]
