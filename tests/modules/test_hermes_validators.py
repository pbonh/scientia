"""Tests for scientia.hermes.validators (AC-5 assignees, ownership smells)."""

from pathlib import Path

from scientia.hermes import parse, validators
from scientia.hermes.parse import ComponentMap, Task
from scientia.hermes.plan import PlanOptions, Routing, build_plan

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"
ROUTING = Routing(
    default_implementer="implementer", default_reviewer="reviewer",
    default_integrator="integrator", resolver="conflict-resolver",
)


def _plan():
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    return build_plan("cid", tasks, c4, cm, contracts, ROUTING, PlanOptions())


def test_clean_plan_validates():
    assert validators.validate_plan(_plan()) == []


def test_validate_plan_flags_unknown_assignee_against_known_profiles():
    errors = validators.validate_plan(_plan(), known_profiles={"implementer", "reviewer"})
    # integrator is referenced but not in the known set
    assert any("integrator" in e for e in errors)


def test_validate_plan_accepts_full_known_profile_set():
    known = {"implementer", "reviewer", "integrator", "conflict-resolver"}
    assert validators.validate_plan(_plan(), known_profiles=known) == []


def test_validate_routing_requires_resolver_for_three_stage():
    bad = Routing(default_implementer="i", default_reviewer="r",
                  default_integrator="g", resolver="")
    errors = validators.validate_routing(bad, [], pipeline="impl-review-integrate")
    assert any("resolver" in e for e in errors)


def test_validate_routing_flags_unknown_referenced_profile():
    routing = Routing(default_implementer="i", default_reviewer="r",
                      default_integrator="g", resolver="cr")
    errors = validators.validate_routing(routing, [], known_profiles={"i", "r", "g"})
    assert any("cr" in e for e in errors)


def test_ownership_smell_for_touch_outside_owned_globs():
    comp_map = ComponentMap({"confidence": ("src/scientia/confidence.py",)})
    tasks = [Task(number=1, title="t", component="confidence",
                  touches=("src/scientia/wiki/__init__.py",))]
    smells = validators.ownership_smells(tasks, comp_map)
    assert len(smells) == 1 and "outside component" in smells[0]


def test_no_smell_when_touch_matches_glob():
    comp_map = ComponentMap({"wiki": ("src/scientia/wiki/**",)})
    tasks = [Task(number=1, title="t", component="wiki",
                  touches=("src/scientia/wiki/__init__.py",))]
    assert validators.ownership_smells(tasks, comp_map) == []


def test_smell_when_component_absent_from_map():
    tasks = [Task(number=1, title="t", component="ghost", touches=("x.py",))]
    smells = validators.ownership_smells(tasks, ComponentMap({}))
    assert len(smells) == 1 and "no owned paths" in smells[0]


# --------------------------------------------------------------------------- #
# verify_touches (execution-time audit)                                        #
# --------------------------------------------------------------------------- #
def test_verify_touches_empty_when_all_declared():
    declared = ["src/a.py", "src/b.rs"]
    actual = ["src/a.py", "src/b.rs"]
    assert validators.verify_touches(declared, actual) == []


def test_verify_touches_flags_undeclared_files():
    declared = ["src/a.py"]
    actual = ["src/a.py", "Cargo.toml", "src/c.rs"]
    result = validators.verify_touches(declared, actual)
    assert result == ["Cargo.toml", "src/c.rs"]


def test_verify_touches_ok_when_actual_is_subset_of_declared():
    declared = ["src/a.py", "src/b.py", "src/c.py"]
    actual = ["src/a.py"]
    assert validators.verify_touches(declared, actual) == []


# --------------------------------------------------------------------------- #
# touches_overlap_warnings (undeclared contract duplication)                    #
# --------------------------------------------------------------------------- #
def test_no_overlap_warning_when_single_task_touches_path():
    tasks = [Task(number=1, title="t", touches=("src/a.py",))]
    assert validators.touches_overlap_warnings(tasks) == []


def test_overlap_warning_when_two_tasks_share_path_no_contract():
    tasks = [
        Task(number=1, title="t1", touches=("src/shared.py",)),
        Task(number=2, title="t2", touches=("src/shared.py",)),
    ]
    warnings = validators.touches_overlap_warnings(tasks)
    assert len(warnings) == 1 and "no shared contract" in warnings[0]


def test_no_overlap_warning_when_contract_declared():
    tasks = [
        Task(number=1, title="t1", touches=("src/shared.py",),
             produces_contracts=("Shared",)),
        Task(number=2, title="t2", touches=("src/shared.py",),
             uses_contracts=("Shared",)),
    ]
    assert validators.touches_overlap_warnings(tasks) == []


# --------------------------------------------------------------------------- #
# cross_lane_task_branches (shared change-id / shared repo)                    #
# --------------------------------------------------------------------------- #
CID = "2026-05-28-multidomain-solver-architecture"


def test_no_sibling_lanes_when_only_current_board_branches_exist():
    branches = ["main", f"circuit-solver-delta/{CID}/task-1",
                f"circuit-solver-delta/{CID}/task-2"]
    assert validators.cross_lane_task_branches(CID, "circuit-solver-delta", branches) == {}


def test_detects_namespaced_sibling_lane():
    branches = [f"circuit-solver-delta/{CID}/task-1",
                f"circuit-solver-gamma/{CID}/task-1",
                f"circuit-solver-beta/{CID}/task-11"]
    out = validators.cross_lane_task_branches(CID, "circuit-solver-delta", branches)
    assert set(out) == {"circuit-solver-beta", "circuit-solver-gamma"}
    assert out["circuit-solver-beta"] == [f"circuit-solver-beta/{CID}/task-11"]


def test_detects_bare_lane_as_empty_prefix():
    # a prior un-namespaced emit left bare <change-id>/task-N refs
    branches = [f"{CID}/task-1", f"{CID}/task-11", f"circuit-solver-delta/{CID}/task-1"]
    out = validators.cross_lane_task_branches(CID, "circuit-solver-delta", branches)
    assert set(out) == {""}
    assert out[""] == [f"{CID}/task-1", f"{CID}/task-11"]


def test_ignores_unrelated_change_ids_and_non_task_refs():
    branches = [f"other-change/{CID[:-1]}X/task-1", f"{CID}/feature-foo",
                f"{CID}/task-", "wt/t_abc123", f"{CID}/task-3"]
    out = validators.cross_lane_task_branches(CID, "circuit-solver-delta", branches)
    # only the well-formed bare task-3 counts
    assert out == {"": [f"{CID}/task-3"]}


def test_board_none_treats_bare_as_current_lane():
    branches = [f"{CID}/task-1", f"circuit-solver-delta/{CID}/task-1"]
    out = validators.cross_lane_task_branches(CID, None, branches)
    # current lane is "" (bare); only the namespaced delta lane is a sibling
    assert set(out) == {"circuit-solver-delta"}


# --------------------------------------------------------------------------- #
# component_map_reality (plan-vs-trunk skeleton)                               #
# --------------------------------------------------------------------------- #
def test_glob_root_extraction():
    assert validators._glob_root("project/src/netlist/**") == "project/src/netlist"
    assert validators._glob_root("project/src/net*") == "project/src"
    assert validators._glob_root("**/x") == ""
    assert validators._glob_root("project/Cargo.toml") == "project/Cargo.toml"


def test_reality_warns_when_owned_root_absent_from_trunk():
    cm = ComponentMap({"netlist": ("project/src/netlist/**", "project/tests/netlist/**")})
    # trunk only has a .gitkeep — the delta situation
    trunk = ["project/.gitkeep", "project/README.md", "crates/digital-kernel/src/lib.rs"]
    warnings = validators.component_map_reality(cm, [], trunk)
    assert len(warnings) == 2
    assert all("netlist" in w and "blank workspace" in w for w in warnings)


def test_reality_quiet_when_root_present():
    cm = ComponentMap({"netlist": ("project/src/netlist/**",)})
    trunk = ["project/src/netlist/graph.rs", "project/Cargo.toml"]
    assert validators.component_map_reality(cm, [], trunk) == []


def test_reality_quiet_for_wildcard_root_glob():
    cm = ComponentMap({"any": ("**/foo.rs",)})
    assert validators.component_map_reality(cm, [], []) == []
