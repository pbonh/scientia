"""scientia.hermes.parse — pure parsers for the formats being bridged.

This module turns the two scientia authoring artifacts into typed, immutable
values with **no I/O of its own** (callers read the files and pass text). It is
the upstream end of the emit seam: everything downstream — keys, waves,
ratification, the plan — is computed from these dataclasses.

Two artifacts are parsed:

* ``tasks.md`` -> :func:`parse_tasks` -> ``list[Task]``. Each ``- [ ] **N.**``
  checklist item becomes one :class:`Task`. The trace + ownership HTML comments
  that *immediately precede* (or trail, inline) a task attach to it; a task with
  no markers is tolerated (the prevention layer simply no-ops for it).
* ``design.md`` -> :func:`parse_design` -> ``([C4Diagram], ComponentMap,
  [Contract])``. The C4 mermaid blocks are captured verbatim (so the epic can
  carry them byte-for-byte), and the optional ``## Component Map`` /
  ``## Shared Contracts`` sections (the 0.2 prevention inputs) are parsed when
  present.

All parsing is deliberately lenient: absent markers degrade to defaults rather
than raising, because the gate that *requires* the markers is a validator
(:mod:`scientia.validators`), not the parser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional

__all__ = [
    "Task",
    "ComponentMap",
    "Contract",
    "C4Diagram",
    "parse_tasks",
    "parse_design",
]


# --------------------------------------------------------------------------- #
# Types                                                                       #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Task:
    """One ``tasks.md`` checklist item, with its trace + ownership markers.

    ``number`` is the author's ``**N.**`` index (intrinsic identity — stable
    under reordering the file). The ``*_contracts`` / ``touches`` / ``spec_refs``
    tuples are normalized (de-duplicated, order-preserving) so cosmetic churn in
    the markers does not change a task's identity hash (:mod:`.idempotency`).
    """

    number: int
    title: str
    spec_refs: tuple[str, ...] = ()
    adr_ref: Optional[str] = None
    depends_on: tuple[int, ...] = ()
    component: Optional[str] = None
    touches: tuple[str, ...] = ()
    produces_contracts: tuple[str, ...] = ()
    uses_contracts: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentMap:
    """C4 component id -> the path globs that component owns."""

    owned: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def globs_for(self, component: Optional[str]) -> tuple[str, ...]:
        if component is None:
            return ()
        return tuple(self.owned.get(component, ()))


@dataclass(frozen=True)
class Contract:
    """A cross-component shared interface, pinned to its owning component."""

    name: str
    owner: str
    ratified_by: Optional[str] = None  # ADR id, or None when unratified


@dataclass(frozen=True)
class C4Diagram:
    """A single C4 mermaid block captured verbatim from ``design.md``."""

    level: str  # "C4Context" | "C4Container" | "C4Component" | ...
    title: Optional[str]
    mermaid: str  # the block body, verbatim (no fence)


# --------------------------------------------------------------------------- #
# Regexes                                                                     #
# --------------------------------------------------------------------------- #
_TASK_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*\*\*(\d+)\.\*\*\s*(.*)$")
_COMMENT_RE = re.compile(r"<!--\s*([a-z][a-z0-9-]*)\s*:\s*(.*?)\s*-->")
_COMMENT_ONLY_RE = re.compile(r"^\s*(?:<!--\s*[a-z][a-z0-9-]*\s*:.*?-->\s*)+$")
_DEPENDS_RE = re.compile(r"\(depends on\s+([^)]*)\)", re.IGNORECASE)
_NUM_RE = re.compile(r"#(\d+)")
_C4_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
_C4_LEVEL_RE = re.compile(r"\b(C4Context|C4Container|C4Component|C4Dynamic|C4Deployment)\b")
_C4_TITLE_RE = re.compile(r"^\s*title\s+(.+?)\s*$", re.MULTILINE)


def _dedupe(items) -> tuple[str, ...]:
    """Order-preserving de-duplication of stripped, non-empty strings."""
    seen: list[str] = []
    for raw in items:
        s = raw.strip()
        if s and s not in seen:
            seen.append(s)
    return tuple(seen)


def _csv(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


# --------------------------------------------------------------------------- #
# tasks.md                                                                     #
# --------------------------------------------------------------------------- #
def _build_task(number: int, title: str, markers: list[tuple[str, str]]) -> Task:
    spec_refs: list[str] = []
    touches: list[str] = []
    produces: list[str] = []
    uses: list[str] = []
    adr_ref: Optional[str] = None
    component: Optional[str] = None
    for key, value in markers:
        if key == "traces-spec":
            spec_refs.extend(_csv(value))
        elif key == "traces-adr":
            adr_ref = adr_ref or value.strip() or None
        elif key == "component":
            component = component or value.strip() or None
        elif key == "touches":
            touches.extend(_csv(value))
        elif key == "produces-contract":
            produces.extend(_csv(value))
        elif key == "uses-contract":
            uses.extend(_csv(value))
        # unknown keys are tolerated and ignored (forward-compatible)

    depends: list[int] = []
    for clause in _DEPENDS_RE.findall(title):
        depends.extend(int(n) for n in _NUM_RE.findall(clause))

    clean_title = _COMMENT_RE.sub("", title).strip()
    return Task(
        number=number,
        title=clean_title,
        spec_refs=_dedupe(spec_refs),
        adr_ref=adr_ref,
        depends_on=tuple(dict.fromkeys(depends)),  # ordered, de-duped
        component=component,
        touches=_dedupe(touches),
        produces_contracts=_dedupe(produces),
        uses_contracts=_dedupe(uses),
    )


def parse_tasks(text: str) -> list[Task]:
    """Parse ``tasks.md`` into a list of :class:`Task`.

    The *nearest preceding* run of trace/ownership comment lines (allowing blank
    lines between them and the task) attaches to a task, as do any comments
    inline on the task line itself. A comment block separated from a task by
    other prose does not attach (it is reset at the intervening content).
    """
    tasks: list[Task] = []
    pending: list[tuple[str, str]] = []
    for line in text.splitlines():
        task_m = _TASK_RE.match(line)
        if task_m:
            inline = _COMMENT_RE.findall(line)
            markers = pending + inline
            tasks.append(_build_task(int(task_m.group(1)), task_m.group(2), markers))
            pending = []
            continue
        if _COMMENT_ONLY_RE.match(line):
            pending.extend(_COMMENT_RE.findall(line))
            continue
        if not line.strip():
            continue  # blank lines keep the pending comment block alive
        pending = []  # any other content breaks the "nearest preceding" run
    return tasks


# --------------------------------------------------------------------------- #
# design.md                                                                    #
# --------------------------------------------------------------------------- #
def _section(text: str, heading: str) -> Optional[str]:
    """Return the body of a ``## <heading>`` section (until the next ``##``)."""
    want = heading.lower().rstrip(":")
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        m = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if m and m.group(1).lower().rstrip(":") == want:
            start = i + 1
            break
    if start is None:
        return None
    out: list[str] = []
    for line in lines[start:]:
        if re.match(r"^#{1,6}\s+", line):
            break
        out.append(line)
    return "\n".join(out)


def _parse_c4(text: str) -> list[C4Diagram]:
    diagrams: list[C4Diagram] = []
    for body in _C4_BLOCK_RE.findall(text):
        level_m = _C4_LEVEL_RE.search(body)
        if not level_m:
            continue  # a plain (non-C4) mermaid block is not a C4 diagram
        title_m = _C4_TITLE_RE.search(body)
        diagrams.append(
            C4Diagram(
                level=level_m.group(1),
                title=title_m.group(1).strip() if title_m else None,
                mermaid=body.rstrip("\n"),
            )
        )
    return diagrams


def _parse_component_map(text: str) -> ComponentMap:
    body = _section(text, "Component Map")
    if body is None:
        return ComponentMap(owned={})
    owned: dict[str, tuple[str, ...]] = {}
    for line in body.splitlines():
        m = re.match(r"^\s*-\s*([A-Za-z0-9_.-]+)\s*:\s*(.+)$", line)
        if m:
            owned[m.group(1).strip()] = _dedupe(_csv(m.group(2)))
    return ComponentMap(owned=owned)


def _parse_contracts(text: str) -> list[Contract]:
    body = _section(text, "Shared Contracts")
    if body is None:
        return []
    contracts: list[Contract] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped[1:].strip()
        if not item:
            continue
        # name is the first token; owner / ratified-by are pulled by key
        # regardless of the separator used between fields.
        name = re.split(r"\s|—|--", item, maxsplit=1)[0].strip()
        owner_m = re.search(r"owner:\s*([A-Za-z0-9_.-]+)", item)
        rat_m = re.search(r"ratified-by:\s*([A-Za-z0-9_.-]+)", item)
        rat = rat_m.group(1).strip() if rat_m else None
        if rat is not None and rat.lower() in ("none", "tbd", "-"):
            rat = None
        if name:
            contracts.append(
                Contract(
                    name=name,
                    owner=owner_m.group(1).strip() if owner_m else "",
                    ratified_by=rat,
                )
            )
    return contracts


def parse_design(design_text: str) -> tuple[list[C4Diagram], ComponentMap, list[Contract]]:
    """Extract the C4 diagrams, the Component Map, and the Shared Contracts.

    The Component Map and Shared Contracts sections are optional (the 0.2
    prevention inputs); absent, they parse to an empty map / empty list and the
    prevention layer no-ops.
    """
    return (
        _parse_c4(design_text),
        _parse_component_map(design_text),
        _parse_contracts(design_text),
    )
