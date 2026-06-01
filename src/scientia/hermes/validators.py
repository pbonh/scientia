"""scientia.hermes.validators — deterministic plan/routing guards (pure).

Mirrors :mod:`scientia.validators`: each function returns a list of
human-readable error strings (empty == clean). These back the emit-time refusals
in §11 — a plan must be acyclic with every parent resolvable and every work card
assigned to a known profile before :mod:`.apply` may touch the board.

:func:`ownership_smells` is the softer, *warning* counterpart used by the emit
skill: a task whose ``touches`` stray outside its component's owned globs is a
decomposition smell to surface, not a hard error.
"""

from __future__ import annotations

import fnmatch
import re
from collections import defaultdict
from typing import Optional, Sequence

from scientia.hermes import idempotency
from scientia.hermes.parse import ComponentMap, Task
from scientia.hermes.plan import EmitPlan, ProfileModel, Routing

__all__ = [
    "validate_plan",
    "validate_routing",
    "ownership_smells",
    "verify_touches",
    "touches_overlap_warnings",
    "cross_lane_task_branches",
    "component_map_reality",
]


def _all_cards(plan: EmitPlan):
    return ([plan.epic] + list(plan.cards)) if plan.epic is not None else list(plan.cards)


def validate_plan(plan: EmitPlan, *, known_profiles: Optional[set[str]] = None) -> list[str]:
    """Check a plan is acyclic, fully wired, and (optionally) fully assignable."""
    errors: list[str] = []
    cards = _all_cards(plan)
    keys = {c.key for c in cards}

    # parents resolvable
    for card in cards:
        for parent in card.parents:
            if parent not in keys:
                errors.append(
                    f"card {card.key!r} references unknown parent {parent!r}"
                )

    # acyclic (Kahn over parent->child)
    indeg = {c.key: 0 for c in cards}
    children: dict[str, list[str]] = defaultdict(list)
    for card in cards:
        for parent in card.parents:
            if parent in indeg:
                indeg[card.key] += 1
                children[parent].append(card.key)
    ready = [k for k, d in indeg.items() if d == 0]
    seen = 0
    while ready:
        k = ready.pop()
        seen += 1
        for ch in children[k]:
            indeg[ch] -= 1
            if indeg[ch] == 0:
                ready.append(ch)
    if seen != len(cards):
        errors.append("plan contains a dependency cycle")

    # assignees
    for card in cards:
        if card.stage == "epic":
            continue
        if not card.assignee:
            errors.append(f"work card {card.key!r} has no assignee")
        elif known_profiles is not None and card.assignee not in known_profiles:
            errors.append(
                f"card {card.key!r} assignee {card.assignee!r} is not a known profile"
            )
    return errors


def validate_routing(
    routing: Routing,
    tasks: Sequence[Task],
    *,
    known_profiles: Optional[set[str]] = None,
    pipeline: str = "impl-review-integrate",
) -> list[str]:
    """Check the routing names real defaults, a resolver, and known profiles."""
    errors: list[str] = []
    if not routing.default_implementer:
        errors.append("routing has no default_implementer")
    if pipeline == "impl-review-integrate":
        if not routing.default_reviewer:
            errors.append("routing has no default_reviewer")
        if not routing.default_integrator:
            errors.append("routing has no default_integrator")
        if not routing.resolver:
            errors.append("routing has no resolver (conflict-resolver) profile")

    referenced: set[str] = {
        routing.default_implementer,
        routing.default_reviewer,
        routing.default_integrator,
        routing.resolver,
    }
    if routing.epic_assignee:
        referenced.add(routing.epic_assignee)
    for tr in routing.per_task.values():
        referenced.update(filter(None, (tr.implementer, tr.reviewer, tr.integrator)))
    referenced.discard("")

    if known_profiles is not None:
        for name in sorted(referenced):
            if name not in known_profiles:
                errors.append(f"routing references unknown profile {name!r}")

    # Validate profile model configs: every model must have a provider and a
    # non-empty model identifier.  Unknown providers are warned (not errored)
    # because the set of valid providers is open-ended.
    _KNOWN_PROVIDERS = {"fireworks", "openai", "anthropic", "google", "mistral", "together", "deepseek", "local"}
    for pname, pm in routing.profile_models.items():
        if not pm.model:
            errors.append(f"profile {pname!r} has a model config but no model identifier")
        if pm.provider not in _KNOWN_PROVIDERS:
            errors.append(
                f"profile {pname!r} model provider {pm.provider!r} is not "
                f"in the known set {{'fireworks', 'openai', 'anthropic', ...}}"
            )
        if pm.temperature is not None and not (0.0 <= pm.temperature <= 2.0):
            errors.append(
                f"profile {pname!r} temperature {pm.temperature} is out of range [0, 2]"
            )
        if pm.max_tokens is not None and pm.max_tokens <= 0:
            errors.append(f"profile {pname!r} max_tokens must be positive, got {pm.max_tokens}")
    if routing.default_model is not None:
        dm = routing.default_model
        if not dm.model:
            errors.append("routing default_model has no model identifier")
        if dm.provider not in _KNOWN_PROVIDERS:
            errors.append(
                f"routing default_model provider {dm.provider!r} is not "
                f"in the known set {{'fireworks', 'openai', 'anthropic', ...}}"
            )
        if dm.temperature is not None and not (0.0 <= dm.temperature <= 2.0):
            errors.append(
                f"routing default_model temperature {dm.temperature} is out of range [0, 2]"
            )
        if dm.max_tokens is not None and dm.max_tokens <= 0:
            errors.append(f"routing default_model max_tokens must be positive, got {dm.max_tokens}")

    return errors


def ownership_smells(tasks: Sequence[Task], comp_map: ComponentMap) -> list[str]:
    """Warn when a task's ``touches`` stray outside its component's owned globs."""
    smells: list[str] = []
    for task in tasks:
        if task.component is None or not task.touches:
            continue
        globs = comp_map.globs_for(task.component)
        if not globs:
            smells.append(
                f"task #{task.number}: component {task.component!r} has no owned "
                f"paths in the Component Map"
            )
            continue
        for path in task.touches:
            if not any(fnmatch.fnmatch(path, g) for g in globs):
                smells.append(
                    f"task #{task.number}: touches {path!r} outside component "
                    f"{task.component!r} owned paths {list(globs)}"
                )
    return smells


def verify_touches(declared: Sequence[str], actual: Sequence[str]) -> list[str]:
    """Compare declared touches against actual edited files (post-impl audit).

    Returns a list of undeclared files — files that appear in ``actual`` but
    not in ``declared``. This is the execution-time counterpart of
    :func:`ownership_smells`: ownership_smells runs at emit time against
    *declared* paths; verify_touches runs at integrate time against *actual*
    git diffs.

    A non-empty result means the implementer edited files outside its declared
    touch-set, which is a drift signal and a collision risk. The integrator
    should flag these in the handoff metadata; the conflict-resolver should
    treat undeclared-edit collisions as higher-priority than declared ones.
    """
    declared_set = set(declared)
    undeclared: list[str] = []
    for path in sorted(actual):
        if path not in declared_set:
            undeclared.append(path)
    return undeclared


def touches_overlap_warnings(tasks: Sequence[Task]) -> list[str]:
    """Warn when two tasks touch the same path with no shared contract declared.

    This catches undeclared contract duplication (e.g. two tasks independently
    defining the same type without a produces-contract/uses-contract marker).
    It complements :func:`ownership_smells` which checks against the Component
    Map; this checks across tasks for overlapping touches with no contract
    coordination.
    """
    path_to_tasks: dict[str, list[int]] = defaultdict(list)
    for task in tasks:
        for p in task.touches:
            path_to_tasks[p].append(task.number)

    warnings: list[str] = []
    for path, task_nums in sorted(path_to_tasks.items()):
        if len(task_nums) < 2:
            continue
        # Check whether any of the sharing tasks produces/uses a contract
        # for this path
        has_contract = False
        for num in task_nums:
            t = next((t for t in tasks if t.number == num), None)
            if t is None:
                continue
            if t.produces_contracts or t.uses_contracts:
                has_contract = True
                break
        if not has_contract:
            warnings.append(
                f"tasks {task_nums} all touch {path!r} with no shared contract "
                f"declared — consider adding produces-contract/uses-contract "
                f"markers to prevent independent type invention"
            )
    return warnings


def cross_lane_task_branches(
    change_id: str,
    board: Optional[str],
    existing_branches: Sequence[str],
) -> dict[str, list[str]]:
    """Group existing task branches for ``change_id`` by lane, excluding the current board.

    A task branch is ``[<lane>/]<change_id>/task-<N>``; the lane is everything
    before ``<change_id>/`` (``""`` for a bare ref). Several boards can target
    the SAME ``change_id`` inside ONE git repo (a shared object store / branch
    namespace — e.g. parallel ``circuit-solver-{beta,gamma,delta}`` worktrees),
    so any branch whose lane differs from ``board`` is a sibling lane sharing
    this ref namespace — the condition that merged a sibling's work into
    circuit-solver-delta's trunk.

    Returns ``{lane: [branches]}`` for those sibling lanes only (empty == this
    repo holds task branches for no lane but the current board). Pure: the caller
    supplies ``existing_branches`` (e.g. ``git for-each-ref refs/heads``).
    """
    pat = re.compile(rf"^(?:(?P<lane>.+)/)?{re.escape(change_id)}/task-\d+$")
    current = (board or "").strip("/")
    lanes: dict[str, list[str]] = defaultdict(list)
    for raw in existing_branches:
        ref = raw.strip()
        m = pat.match(ref)
        if not m:
            continue
        lane = (m.group("lane") or "").strip("/")
        if lane == current:
            continue
        lanes[lane].append(ref)
    return {lane: sorted(set(refs)) for lane, refs in sorted(lanes.items())}


def _glob_root(glob: str) -> str:
    """The literal directory prefix of a path glob, before the first wildcard.

    ``project/src/netlist/**`` -> ``project/src/netlist``;
    ``project/src/net*`` -> ``project/src`` (drops the partial segment);
    ``**/x`` -> ``""`` (wildcard-rooted: owns everything, nothing to check).
    """
    cut = len(glob)
    for i, ch in enumerate(glob):
        if ch in "*?[":
            cut = i
            break
    prefix = glob[:cut]
    if cut < len(glob) and not prefix.endswith("/"):
        # the cut fell mid-segment; keep only complete path segments
        prefix = prefix.rsplit("/", 1)[0] if "/" in prefix else ""
    return prefix.rstrip("/")


def component_map_reality(
    comp_map: ComponentMap,
    tasks: Sequence[Task],
    trunk_paths: Sequence[str],
) -> list[str]:
    """Warn when a Component Map owned-root has no presence in the trunk tree.

    Each owned glob (e.g. ``project/src/netlist/**``) has a literal root
    (``project/src/netlist``). If no tracked path in ``trunk_paths`` lives under
    that root, an implementer opening the workspace finds it blank and improvises
    a divergent layout — the friction that detached circuit-solver-delta's plan
    from its repo (the design owned ``project/src/**`` but trunk had only
    ``project/.gitkeep``; workers built a top-level ``crates/`` instead, and the
    touches/wave/contract machinery — all keyed on the declared paths — became
    moot for the code that actually shipped).

    Returns one message per absent root. These are warnings, not hard errors: a
    greenfield change legitimately scaffolds the whole tree from nothing. The
    emit skill decides whether to scaffold the skeleton, fix the Component Map,
    or proceed. Pure: the caller supplies ``trunk_paths`` (e.g.
    ``git ls-tree -r --name-only <base_sha>``).
    """
    paths = [p.strip() for p in trunk_paths if p.strip()]

    def _present(root: str) -> bool:
        if not root:
            return True  # wildcard-rooted glob owns everything; nothing to check
        return any(p == root or p.startswith(root + "/") for p in paths)

    warnings: list[str] = []
    for component in sorted(comp_map.owned):
        roots: list[str] = []
        for g in comp_map.owned[component]:
            r = _glob_root(g)
            if r and r not in roots:
                roots.append(r)
        for r in roots:
            if not _present(r):
                warnings.append(
                    f"component {component!r} owns {r!r} (from its Component Map "
                    f"globs) but no path under it exists on trunk @ base_sha — "
                    f"workers will find a blank workspace and may improvise a "
                    f"different layout. Scaffold the skeleton at emit or fix the "
                    f"Component Map before emitting."
                )
    return warnings
