"""scientia.hermes.plan — the emit seam (pure).

:func:`build_plan` is the heart of the layer: it folds tasks, the C4
architecture, the prevention edges, and the LLM-supplied :class:`Routing` into a
single immutable, JSON-serializable :class:`EmitPlan` describing the *entire*
board mutation — with no Hermes and no network. The plan is the unit of
golden-file testing.

For ``pipeline = impl-review-integrate`` every task expands into a three-card
chain (``review`` parented on ``impl``; ``integrate`` parented on ``review``).
Cross-task edges — a ``(depends on #M)`` clause, a wave-serialization edge, or a
producer->consumer contract edge — all attach to the *downstream* task's first
stage and point at the *upstream* task's terminal stage (its ``integrate``), so
work always starts from a trunk that already contains what it depends on. The
``single`` pipeline collapses the chain to one card per task.

Card bodies are composed deterministically (from the ``hermes-card`` /
``hermes-handoff`` templates) so the golden suite is byte-stable; the skill's
judgment is exercised earlier, in choosing the :class:`Routing`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from scientia import templates
from scientia.hermes import conflict, idempotency
from scientia.hermes.parse import C4Diagram, ComponentMap, Contract, Task

__all__ = [
    "TaskRouting",
    "Routing",
    "PlanOptions",
    "CardSpec",
    "EmitPlan",
    "CycleError",
    "build_plan",
    "compose_body",
    "compose_epic_body",
]


# --------------------------------------------------------------------------- #
# Inputs                                                                       #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TaskRouting:
    """Per-task overrides of the default per-stage assignees (LLM judgment)."""

    implementer: Optional[str] = None
    reviewer: Optional[str] = None
    integrator: Optional[str] = None
    skills: tuple[str, ...] = ()
    workspace: Optional[str] = None


@dataclass(frozen=True)
class Routing:
    """The complete task->profile routing (the LLM-judgment input to a plan)."""

    default_implementer: str
    default_reviewer: str
    default_integrator: str
    resolver: str
    per_task: Mapping[int, TaskRouting] = field(default_factory=dict)
    epic_assignee: Optional[str] = None
    board: Optional[str] = None
    tenant: Optional[str] = None


@dataclass(frozen=True)
class PlanOptions:
    """The deterministic knobs (mirror the ``hermes:`` config block)."""

    pipeline: str = "impl-review-integrate"  # or "single"
    emit_epic: bool = True
    workspace: str = "worktree"
    max_parallel_per_file_group: int = 2
    conflict_prevention: bool = True
    adr_contracts: frozenset = frozenset()  # contract names ratified by accepted ADRs
    priority: Optional[int] = None


# --------------------------------------------------------------------------- #
# Outputs                                                                      #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CardSpec:
    """One Hermes card to create. ``parents`` holds parent card *keys*, resolved
    to live ids at render time."""

    key: str
    title: str
    body: str
    assignee: str
    parents: tuple[str, ...]
    tenant: Optional[str]
    workspace: str
    branch: Optional[str]
    skills: tuple[str, ...]
    priority: Optional[int]
    stage: str  # "impl" | "review" | "integrate" | "epic" | "single"


@dataclass(frozen=True)
class EmitPlan:
    """A pure description of the whole board mutation, topologically ordered."""

    change_id: str
    board: Optional[str]
    epic: Optional[CardSpec]
    cards: tuple[CardSpec, ...]  # parents always precede children


class CycleError(ValueError):
    """Raised when the dependency graph (incl. wave/contract edges) has a cycle."""


_STAGE_RANK = {"impl": 0, "single": 0, "review": 1, "integrate": 2}


# --------------------------------------------------------------------------- #
# Body composition (deterministic)                                            #
# --------------------------------------------------------------------------- #
def _trace_block(task: Task) -> str:
    lines: list[str] = []
    for ref in task.spec_refs:
        lines.append(f"- Spec scenario: `{ref}`")
    if task.adr_ref:
        lines.append(f"- ADR: {task.adr_ref}")
    if task.component:
        lines.append(f"- Component: `{task.component}`")
    if task.touches:
        lines.append(f"- Touches: {', '.join(task.touches)}")
    for name in task.uses_contracts:
        lines.append(f"- Consumes contract: `{name}`")
    for name in task.produces_contracts:
        lines.append(f"- Produces contract: `{name}`")
    return "\n".join(lines) if lines else "- _(no traceability markers)_"


def _instructions(task: Task, stage: str, resolver: str) -> str:
    if stage in ("impl", "single"):
        base = (
            f"Implement task #{task.number} — {task.title} — in an isolated "
            f"workspace. Write the code and its tests; keep edits within the "
            f"task's touched paths."
        )
        if stage == "single":
            base += (
                " Then self-review against the spec scenario above and merge to "
                "trunk when green."
            )
        return base
    if stage == "review":
        return (
            f"Review the completed implementation branch for task #{task.number} "
            f"against the spec scenario(s) above. Approve only if every scenario "
            f"is satisfied and its tests pass; otherwise return it for revision."
        )
    if stage == "integrate":
        return (
            f"Merge the approved worker branch for task #{task.number} to trunk. "
            f"If the merge is clean, complete. If it conflicts, **reassign this "
            f"card to the `{resolver}` profile** and comment the two branch heads "
            f"— do not block for a human."
        )
    return task.title


def compose_body(task: Task, stage: str, change_id: str, resolver: str) -> str:
    """Render one work card's body from the shared templates (byte-stable)."""
    handoff = templates.render("hermes-handoff")
    return templates.render(
        "hermes-card",
        title=task.title,
        change_id=change_id,
        number=task.number,
        stage=stage,
        traces=_trace_block(task),
        instructions=_instructions(task, stage, resolver),
        handoff=handoff,
    )


def compose_epic_body(
    change_id: str,
    c4: Sequence[C4Diagram],
    comp_map: ComponentMap,
    contracts: Sequence[Contract],
) -> str:
    """Compose the epic body: the C4 blocks **verbatim** plus the ownership map.

    The C4 mermaid is reproduced exactly (AC-8) so a worker reads the same
    architecture the design recorded.
    """
    parts: list[str] = [f"# Architecture — {change_id}", ""]
    parts.append("The C4 model and component ownership for this change. This epic")
    parts.append("groups the work; it never blocks a work card.")
    parts.append("")
    for diagram in c4:
        heading = diagram.title or diagram.level
        parts.append(f"## {heading}")
        parts.append("")
        parts.append("```mermaid")
        parts.append(diagram.mermaid)
        parts.append("```")
        parts.append("")
    if comp_map.owned:
        parts.append("## Component Map")
        parts.append("")
        for name in sorted(comp_map.owned):
            parts.append(f"- {name}: {', '.join(comp_map.owned[name])}")
        parts.append("")
    if contracts:
        parts.append("## Shared Contracts")
        parts.append("")
        for c in contracts:
            rat = c.ratified_by or "unratified"
            parts.append(f"- {c.name} — owner: {c.owner} — ratified-by: {rat}")
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


# --------------------------------------------------------------------------- #
# Plan construction                                                            #
# --------------------------------------------------------------------------- #
def _toposort(cards: list[CardSpec]) -> list[CardSpec]:
    by_key = {c.key: c for c in cards}
    indeg = {c.key: 0 for c in cards}
    children: dict[str, list[str]] = defaultdict(list)
    for card in cards:
        for parent in card.parents:
            if parent not in by_key:
                raise ValueError(
                    f"card {card.key!r} references unknown parent {parent!r}"
                )
            indeg[card.key] += 1
            children[parent].append(card.key)

    def order_key(key: str) -> tuple:
        card = by_key[key]
        info = idempotency.parse_card_key(key)
        num = info["task_number"] if info["task_number"] is not None else -1
        return (num, _STAGE_RANK.get(card.stage, 9), key)

    ready = sorted((k for k, d in indeg.items() if d == 0), key=order_key)
    out: list[CardSpec] = []
    while ready:
        key = ready.pop(0)
        out.append(by_key[key])
        newly = []
        for child in children[key]:
            indeg[child] -= 1
            if indeg[child] == 0:
                newly.append(child)
        if newly:
            ready.extend(newly)
            ready.sort(key=order_key)
    if len(out) != len(cards):
        stuck = sorted(k for k in indeg if indeg[k] > 0)
        raise CycleError(
            f"dependency cycle among cards: {', '.join(stuck)}"
        )
    return out


def build_plan(
    change_id: str,
    tasks: Sequence[Task],
    c4: Sequence[C4Diagram],
    comp_map: ComponentMap,
    contracts: Sequence[Contract],
    routing: Routing,
    options: PlanOptions,
) -> EmitPlan:
    """Expand tasks into a fully-wired, topologically-ordered :class:`EmitPlan`.

    Raises :class:`scientia.hermes.conflict.ContractError` if prevention is on and
    a consumed contract is unpinned, and :class:`CycleError` if the edges form a
    cycle. Pure: no I/O beyond reading the packaged body templates.
    """
    tasks = list(tasks)
    by_number = {t.number: t for t in tasks}
    for task in tasks:
        for dep in task.depends_on:
            if dep not in by_number:
                raise ValueError(
                    f"task #{task.number} depends on unknown task #{dep}"
                )

    # Cross-task parent edges: downstream first-stage -> upstream terminal stage.
    cross: dict[int, set[int]] = defaultdict(set)
    for task in tasks:
        cross[task.number].update(task.depends_on)
    if options.conflict_prevention:
        waves = conflict.compute_waves(
            tasks, max_parallel_per_file_group=options.max_parallel_per_file_group
        )
        for parent, child in conflict.synthetic_edges(tasks, waves):
            cross[child].add(parent)
        for producer, consumer in conflict.ratify_contracts(
            tasks, set(options.adr_contracts)
        ):
            cross[consumer].add(producer)

    shas = {t.number: idempotency.source_sha(t) for t in tasks}
    single = options.pipeline == "single"
    terminal = "single" if single else "integrate"

    def tkey(num: int, stage: str) -> str:
        return idempotency.card_key(change_id, number=num, sha=shas[num], stage=stage)

    cards: list[CardSpec] = []
    for task in sorted(tasks, key=lambda t: t.number):
        tr = routing.per_task.get(task.number, TaskRouting())
        workspace = tr.workspace or options.workspace
        branch = f"{change_id}/task-{task.number}"
        cross_keys = tuple(
            sorted(tkey(m, terminal) for m in sorted(cross[task.number]))
        )

        def mk(stage: str, assignee: str, parents: tuple[str, ...], br: Optional[str]) -> CardSpec:
            return CardSpec(
                key=tkey(task.number, stage),
                title=f"[{stage}] #{task.number} {task.title}",
                body=compose_body(task, stage, change_id, routing.resolver),
                assignee=assignee,
                parents=parents,
                tenant=routing.tenant,
                workspace=workspace,
                branch=br,
                skills=tr.skills,
                priority=options.priority,
                stage=stage,
            )

        if single:
            cards.append(
                mk("single", tr.implementer or routing.default_implementer, cross_keys, branch)
            )
        else:
            cards.append(
                mk("impl", tr.implementer or routing.default_implementer, cross_keys, branch)
            )
            cards.append(
                mk("review", tr.reviewer or routing.default_reviewer, (tkey(task.number, "impl"),), None)
            )
            cards.append(
                mk("integrate", tr.integrator or routing.default_integrator, (tkey(task.number, "review"),), None)
            )

    epic: Optional[CardSpec] = None
    if options.emit_epic and (c4 or comp_map.owned or contracts):
        epic = CardSpec(
            key=idempotency.epic_key(
                change_id, sha=idempotency.design_sha(c4, comp_map, contracts)
            ),
            title=f"[epic] {change_id}",
            body=compose_epic_body(change_id, c4, comp_map, contracts),
            assignee=routing.epic_assignee or "",
            parents=(),
            tenant=routing.tenant,
            workspace=options.workspace,
            branch=None,
            skills=(),
            priority=options.priority,
            stage="epic",
        )

    ordered = _toposort(cards)
    return EmitPlan(change_id=change_id, board=routing.board, epic=epic, cards=tuple(ordered))
