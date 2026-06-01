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

Each card now carries an optional :class:`ProfileModel` describing which LLM
provider and model the assignee profile should use. The model is resolved at
plan-build time from the routing's ``profile_models`` map (itself sourced from
the ``hermes.profiles.<name>.model`` config block), so the rest of the pipeline
— render, apply, preflight — can treat it as a simple attached value. Profiles
without an explicit model fall through to the routing-level ``default_model``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from scientia import templates
from scientia.hermes import conflict, idempotency
from scientia.hermes.parse import C4Diagram, ComponentMap, Contract, Task

__all__ = [
    "ProfileModel",
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
class ProfileModel:
    """Per-profile LLM provider and model configuration.

    Sourced from the ``hermes.profiles.<name>.model`` config block.  Each
    profile can target a different vendor/model pair (e.g. Fireworks for the
    implementer, Anthropic for the reviewer).  Profiles without an explicit
    model fall through to the routing-level ``default_model``.

    ``provider`` is a short vendor slug (``fireworks``, ``openai``,
    ``anthropic``, etc.).  ``model`` is the provider-specific model identifier.
    ``base_url`` overrides the provider's default API endpoint (useful for
    Fireworks' OpenAI-compatible endpoint or local proxies).  ``api_key_env``
    names the environment variable that holds the API key; preflight checks
    that it is set when the profile requires a model.
    """

    provider: str = "fireworks"
    model: str = ""
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


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
    profile_models: Mapping[str, ProfileModel] = field(default_factory=dict)
    default_model: Optional[ProfileModel] = None


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
    model: Optional[ProfileModel] = None
    base_sha: Optional[str] = None   # trunk HEAD at emit time — prevents lineage divergence
    wave: Optional[int] = None       # file-collision wave index — scheduling hint + audit trail


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


def _instructions(task: Task, stage: str, resolver: str, base_sha: Optional[str] = None, branch: Optional[str] = None) -> str:
    if stage in ("impl", "single"):
        base = (
            f"Implement task #{task.number} — {task.title} — in an isolated "
            f"workspace. Write the code and its tests; keep edits within the "
            f"task's touched paths."
        )
        if base_sha:
            base += f" Branch from commit `{base_sha}`. If that commit is no longer on trunk, rebase onto current trunk but verify your touches still apply."
        if branch:
            base += (
                f" Commit your work to the branch `{branch}`. This is THIS "
                f"board's ref namespace — do NOT push to a bare "
                f"`<change-id>/task-N` ref, which sibling boards sharing this "
                f"repo also write to (cross-board branch collision corrupts trunk)."
            )
        commit_line = (
            f"- Your work is committed to branch `{branch}`, and your handoff "
            f"reports its exact `branch` name and final `commit` SHA\n"
            if branch else ""
        )
        base += (
            "\n\n## Completion Criteria\n"
            "Complete (do NOT block for review) when ALL of:\n"
            "- Every spec scenario traced above has a passing test\n"
            "- `cargo test` passes (or the verification command in the handoff)\n"
            "- `cargo clippy` passes with no warnings\n"
            "- All edits are within the declared touches paths\n"
            f"{commit_line}"
            "\n"
            "Do NOT self-block for review — the next card in this pipeline is a "
            "dedicated reviewer. If you have a design concern, note it in the "
            "handoff `residual_risk` field and complete anyway."
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
        expected = f"`{branch}`" if branch else f"`<change-id>/task-{task.number}`"
        return (
            f"Merge task #{task.number}'s reviewed work to trunk. Merge the EXACT "
            f"branch and commit SHA the implementer reported in its handoff "
            f"(authoritative) — do NOT reconstruct a branch name by convention. "
            f"The expected branch is {expected}; sibling boards in this repo also "
            f"write `<change-id>/task-N` refs, so a reconstructed name can merge "
            f"another board's work into this trunk. Confirm the branch tip is the "
            f"reviewed commit before merging.\n\n"
            f"**Attempt `git merge <handoff-commit>` first.** Only if git reports "
            f"conflicts (exit code 1, conflict markers in files) do you hand the "
            f"card to the `{resolver}` profile — and you MUST actually reassign it: "
            f"change the card's assignee to `{resolver}` (a board reassign event), "
            f"not merely comment that you reassigned. After reassigning, re-read "
            f"the card and verify its assignee is `{resolver}`; otherwise the "
            f"resolver never sees it. Comment the two branch heads — do not block "
            f"for a human. File overlap alone is NOT a conflict; you must actually "
            f"attempt the merge.\n\n"
            f"Before completing, verify the worker's actual edits match its "
            f"declared touches: run `git diff --name-only <base>..<branch_head>` "
            f"and flag any file outside the touches set as an undeclared edit "
            f"in your handoff metadata."
        )
    return task.title


def compose_body(task: Task, stage: str, change_id: str, resolver: str, base_sha: Optional[str] = None, branch: Optional[str] = None) -> str:
    """Render one work card's body from the shared templates (byte-stable).

    ``branch`` is the task's board-namespaced worker branch. It is named in the
    impl instructions (commit here) and the integrate instructions (merge this
    exact ref, not a reconstructed `<change-id>/task-N` convention that sibling
    boards in the same repo also write to).
    """
    handoff = templates.render("hermes-handoff")
    body = templates.render(
        "hermes-card",
        title=task.title,
        change_id=change_id,
        number=task.number,
        stage=stage,
        traces=_trace_block(task),
        instructions=_instructions(task, stage, resolver, base_sha=base_sha, branch=branch),
        handoff=handoff,
    )
    # Append touches and wave metadata as a machine-readable block for the
    # integrator and conflict-resolver to audit against.
    if task.touches:
        body += f"\n<!-- declared-touches: {', '.join(task.touches)} -->\n"
    return body


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
    base_sha: Optional[str] = None,
) -> EmitPlan:
    """Expand tasks into a fully-wired, topologically-ordered :class:`EmitPlan`.

    Raises :class:`scientia.hermes.conflict.ContractError` if prevention is on and
    a consumed contract is unpinned, and :class:`CycleError` if the edges form a
    cycle. Pure: no I/O beyond reading the packaged body templates.

    ``base_sha`` is the trunk HEAD at emit time. When provided, it is embedded
    in each impl/single card body so workers branch from a known commit rather
    than whatever HEAD is current at dispatch time — preventing lineage
    divergence (friction point #1 from the circuit-solver-beta analysis).
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

    # Model resolution: per-profile override, else routing-level default.
    def _model_for(assignee: str) -> Optional[ProfileModel]:
        """Look up the model config for a profile; fall through to default."""
        if assignee in routing.profile_models:
            pm = routing.profile_models[assignee]
            # A profile entry with an empty model string means "use default".
            if pm.model:
                return pm
        return routing.default_model

    cards: list[CardSpec] = []
    for task in sorted(tasks, key=lambda t: t.number):
        tr = routing.per_task.get(task.number, TaskRouting())
        workspace = tr.workspace or options.workspace
        # Branch names live in the trunk repo's ref namespace. Several boards
        # (lanes) can target the SAME change_id inside ONE git repo — e.g.
        # parallel `circuit-solver-{beta,gamma,delta}` worktrees that share an
        # object store. Without a per-board qualifier, every lane's integrator
        # resolves the same `<change_id>/task-N` ref and merges a sibling
        # board's work into its own trunk (the delta trunk-corruption failure).
        # Prefix with the board slug so each lane owns a disjoint ref space.
        board_prefix = f"{routing.board}/" if routing.board else ""
        branch = f"{board_prefix}{change_id}/task-{task.number}"
        cross_keys = tuple(
            sorted(tkey(m, terminal) for m in sorted(cross[task.number]))
        )

        def mk(stage: str, assignee: str, parents: tuple[str, ...], br: Optional[str]) -> CardSpec:
            task_wave = waves.get(task.number) if options.conflict_prevention else None
            return CardSpec(
                key=tkey(task.number, stage),
                title=f"[{stage}] #{task.number} {task.title}",
                body=compose_body(task, stage, change_id, routing.resolver, base_sha=base_sha, branch=branch),
                assignee=assignee,
                parents=parents,
                tenant=routing.tenant,
                workspace=workspace,
                branch=br,
                skills=tr.skills,
                priority=options.priority,
                stage=stage,
                model=_model_for(assignee),
                base_sha=base_sha if stage in ("impl", "single") else None,
                wave=task_wave if stage in ("impl", "single") else None,
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
        epic_model = _model_for(routing.epic_assignee) if routing.epic_assignee else routing.default_model
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
            model=epic_model,
        )

    ordered = _toposort(cards)
    return EmitPlan(change_id=change_id, board=routing.board, epic=epic, cards=tuple(ordered))
