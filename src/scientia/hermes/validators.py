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
from collections import defaultdict
from typing import Optional, Sequence

from scientia.hermes import idempotency
from scientia.hermes.parse import ComponentMap, Task
from scientia.hermes.plan import EmitPlan, ProfileModel, Routing

__all__ = ["validate_plan", "validate_routing", "ownership_smells"]


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
