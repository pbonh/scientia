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
