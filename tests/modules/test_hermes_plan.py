"""Tests for scientia.hermes.plan — the emit seam (AC-2, AC-6, AC-8, AC-11..13, AC-16).

The golden file is a *projection* of the plan (bodies elided to a content hash)
so it stays compact and stable while still catching body drift. Structural
properties are asserted directly too, so the golden is not a blind snapshot.
"""

import hashlib
import json
from pathlib import Path

import pytest

from scientia.hermes import conflict, parse
from scientia.hermes.plan import (
    CycleError,
    PlanOptions,
    Routing,
    TaskRouting,
    build_plan,
)

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"
GOLDEN = FIX.parent / "hermes-plan.expected.json"

ROUTING = Routing(
    default_implementer="implementer",
    default_reviewer="reviewer",
    default_integrator="integrator",
    resolver="conflict-resolver",
    epic_assignee=None,
    board=None,
    tenant="2026-05-28-rag-replacement",
)
CID = "2026-05-28-rag-replacement"


def _load_fixture():
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    c4, comp_map, contracts = parse.parse_design((FIX / "design.md").read_text())
    return tasks, c4, comp_map, contracts


def _plan(options=None):
    tasks, c4, comp_map, contracts = _load_fixture()
    return build_plan(CID, tasks, c4, comp_map, contracts, ROUTING, options or PlanOptions())


def _body_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _project(plan):
    def card(c):
        return {
            "key": c.key,
            "stage": c.stage,
            "assignee": c.assignee,
            "parents": sorted(c.parents),
            "branch": c.branch,
            "workspace": c.workspace,
            "tenant": c.tenant,
            "priority": c.priority,
            "skills": list(c.skills),
            "body_sha": _body_sha(c.body),
        }
    return {
        "change_id": plan.change_id,
        "board": plan.board,
        "epic": card(plan.epic) if plan.epic else None,
        "cards": [card(c) for c in plan.cards],
    }


# --------------------------------------------------------------------------- #
# Structure                                                                    #
# --------------------------------------------------------------------------- #
def test_three_stage_expansion_with_chain_links():
    plan = _plan()
    stages = [c.stage for c in plan.cards]
    assert stages.count("impl") == 4 and stages.count("review") == 4 and stages.count("integrate") == 4
    by_key = {c.key: c for c in plan.cards}
    for c in plan.cards:
        if c.stage == "review":
            (parent,) = c.parents
            assert by_key[parent].stage == "impl"
        if c.stage == "integrate":
            (parent,) = c.parents
            assert by_key[parent].stage == "review"


def test_dependency_maps_onto_upstream_integrate():
    plan = _plan()
    by_key = {c.key: c for c in plan.cards}
    impl2 = next(c for c in plan.cards if c.stage == "impl" and ":task:2:" in c.key)
    # task 2 depends on #1 -> its impl is parented on task 1's INTEGRATE
    assert any(by_key[p].stage == "integrate" and ":task:1:" in p for p in impl2.parents)


def test_synthetic_wave_edge_adds_a_nondependency_parent():
    # task 3 shares confidence.py with 1 and 2; cap 2 -> task 3 in wave 1, so it
    # gains synthetic parents on task 1's integrate even though it only *declares*
    # a dependency on #2.
    plan = _plan()
    impl3 = next(c for c in plan.cards if c.stage == "impl" and ":task:3:" in c.key)
    parented_tasks = {p.split(":")[2] for p in impl3.parents}
    assert {"1", "2"} <= parented_tasks


def test_epic_carries_every_c4_block_verbatim_and_blocks_nothing():
    plan = _plan()
    assert plan.epic is not None and plan.epic.stage == "epic"
    c4, _, _ = parse.parse_design((FIX / "design.md").read_text())
    for diagram in c4:
        assert diagram.mermaid in plan.epic.body
    # the epic is parent of no work card
    for c in plan.cards:
        assert plan.epic.key not in c.parents


def test_topological_order_parents_precede_children():
    plan = _plan()
    seen = set()
    for c in plan.cards:
        assert all(p in seen for p in c.parents), f"{c.key} emitted before a parent"
        seen.add(c.key)


def test_single_pipeline_collapses_to_one_card_per_task():
    plan = _plan(PlanOptions(pipeline="single"))
    assert all(c.stage == "single" for c in plan.cards)
    assert len(plan.cards) == 4


def test_conflict_prevention_off_drops_wave_and_contract_edges():
    # With prevention off, only explicit (depends on) edges remain.
    plan = _plan(PlanOptions(conflict_prevention=False))
    impl3 = next(c for c in plan.cards if c.stage == "impl" and ":task:3:" in c.key)
    parented_tasks = {p.split(":")[2] for p in impl3.parents}
    assert parented_tasks == {"2"}  # only the declared dependency, no synthetic #1


def test_prevention_off_needs_no_markers_at_all():
    # AC-16: a marker-free tasks.md still plans cleanly with prevention off.
    tasks = parse.parse_tasks("- [ ] **1.** a\n- [ ] **2.** b (depends on #1)\n")
    plan = build_plan(CID, tasks, [], parse.ComponentMap({}), [], ROUTING,
                      PlanOptions(conflict_prevention=False, emit_epic=False))
    assert len(plan.cards) == 6 and plan.epic is None


# --------------------------------------------------------------------------- #
# Failure modes                                                                #
# --------------------------------------------------------------------------- #
def test_cycle_raises_cycle_error():
    tasks = [
        parse.Task(number=1, title="a", depends_on=(2,)),
        parse.Task(number=2, title="b", depends_on=(1,)),
    ]
    with pytest.raises(CycleError):
        build_plan(CID, tasks, [], parse.ComponentMap({}), [], ROUTING,
                   PlanOptions(conflict_prevention=False, emit_epic=False))


def test_unknown_dependency_target_raises():
    tasks = [parse.Task(number=1, title="a", depends_on=(9,))]
    with pytest.raises(ValueError):
        build_plan(CID, tasks, [], parse.ComponentMap({}), [], ROUTING,
                   PlanOptions(conflict_prevention=False, emit_epic=False))


def test_unpinned_contract_raises_contract_error():
    tasks = [parse.Task(number=1, title="a", uses_contracts=("X",), touches=("a.py",))]
    with pytest.raises(conflict.ContractError):
        build_plan(CID, tasks, [], parse.ComponentMap({}), [], ROUTING, PlanOptions())


def test_per_task_routing_overrides_assignee():
    tasks = parse.parse_tasks("- [ ] **1.** a <!-- traces-spec: c#s -->\n")
    routing = Routing(
        default_implementer="implementer", default_reviewer="reviewer",
        default_integrator="integrator", resolver="conflict-resolver",
        per_task={1: TaskRouting(implementer="specialist")},
    )
    plan = build_plan(CID, tasks, [], parse.ComponentMap({}), [], routing,
                      PlanOptions(conflict_prevention=False, emit_epic=False))
    impl = next(c for c in plan.cards if c.stage == "impl")
    assert impl.assignee == "specialist"


# --------------------------------------------------------------------------- #
# Golden                                                                       #
# --------------------------------------------------------------------------- #
def test_golden_plan_projection_matches():
    actual = _project(_plan())
    expected = json.loads(GOLDEN.read_text())
    assert actual == expected
