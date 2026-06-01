"""Tests for scientia.hermes.preflight (AC-7 gateway gate, §12 loopback guard).

The gateway probe is injected so these run with no Hermes present (AC-10).
"""

from pathlib import Path

from scientia.hermes import parse, preflight
from scientia.hermes.parse import ComponentMap
from scientia.hermes.plan import PlanOptions, Routing, build_plan

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"
ROUTING = Routing(
    default_implementer="implementer", default_reviewer="reviewer",
    default_integrator="integrator", resolver="conflict-resolver",
)


def _plan(workspace="worktree"):
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    return build_plan("cid", tasks, c4, cm, contracts, ROUTING,
                      PlanOptions(workspace=workspace))


_UP = lambda h, p: True
_DOWN = lambda h, p: False


def test_clean_plan_passes_when_gateway_up():
    res = preflight.check(_plan(), gateway_probe=_UP)
    assert res.ok and res.errors == []


def test_refuses_when_gateway_down():
    res = preflight.check(_plan(), require_gateway=True, gateway_probe=_DOWN)
    assert not res.ok and any("gateway not reachable" in e for e in res.errors)


def test_gateway_check_skipped_when_not_required():
    res = preflight.check(_plan(), require_gateway=False, gateway_probe=_DOWN)
    assert res.ok


def test_refuses_non_loopback_rest_base():
    res = preflight.check(
        _plan(), require_gateway=False, rest_base="http://10.0.0.5:8787/api/plugins/kanban"
    )
    assert not res.ok and any("loopback" in e for e in res.errors)


def test_allow_remote_overrides_loopback_guard():
    res = preflight.check(
        _plan(), require_gateway=False, allow_remote=True,
        rest_base="http://10.0.0.5:8787/api/plugins/kanban",
    )
    assert res.ok


def test_refuses_relative_dir_workspace():
    res = preflight.check(_plan(workspace="dir:relative/path"), require_gateway=False)
    assert not res.ok and any("absolute path" in e for e in res.errors)


def test_accepts_absolute_dir_workspace():
    res = preflight.check(_plan(workspace="dir:/abs/path"), require_gateway=False)
    assert res.ok


def test_refuses_unknown_assignee_against_provisioned_profiles():
    res = preflight.check(
        _plan(), require_gateway=False, known_profiles={"implementer"}
    )
    assert not res.ok and any("scientia-hermes-init" in e for e in res.errors)


def test_cli_backend_checks_cli_presence_not_http_port():
    # No HTTP probe for the cli backend; a present CLI passes with a dispatcher warning.
    res = preflight.check(
        _plan(), backend="cli", require_gateway=True,
        gateway_probe=_DOWN,            # would fail the rest backend; ignored for cli
        cli_probe=lambda: True,
    )
    assert res.ok and res.errors == []
    assert any("dispatcher" in w for w in res.warnings)


def test_cli_backend_errors_when_hermes_cli_absent():
    res = preflight.check(
        _plan(), backend="cli", require_gateway=True, cli_probe=lambda: False
    )
    assert not res.ok and any("`hermes` CLI" in e for e in res.errors)


def test_cli_backend_ignores_non_loopback_rest_base():
    # rest_base is unused for the cli backend, so the loopback guard must not fire.
    res = preflight.check(
        _plan(), backend="cli", require_gateway=False,
        rest_base="http://10.0.0.5:8787/api/plugins/kanban", cli_probe=lambda: True,
    )
    assert res.ok and res.errors == []


# --------------------------------------------------------------------------- #
# repo_reality_check (git-grounded: shared change-id + Component Map vs trunk)  #
# --------------------------------------------------------------------------- #
def _board_plan(board):
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    routing = Routing(
        default_implementer="implementer", default_reviewer="reviewer",
        default_integrator="integrator", resolver="conflict-resolver", board=board,
    )
    return build_plan("cid", tasks, c4, cm, contracts, routing, PlanOptions())


def test_reality_warns_on_namespaced_sibling_lane():
    plan = _board_plan("circuit-solver-delta")
    branches = lambda: ["main", "circuit-solver-gamma/cid/task-1",
                        "circuit-solver-delta/cid/task-1"]
    res = preflight.repo_reality_check(plan, branch_probe=branches)
    assert res.ok and res.errors == []
    assert any("sibling lane" in w and "circuit-solver-gamma" in w for w in res.warnings)


def test_reality_errors_on_bare_emit_in_multilane_repo():
    plan = _board_plan(None)  # this emit would produce bare cid/task-N refs
    branches = lambda: ["circuit-solver-gamma/cid/task-1", "circuit-solver-beta/cid/task-2"]
    res = preflight.repo_reality_check(plan, branch_probe=branches)
    assert not res.ok and any("no board set" in e for e in res.errors)


def test_reality_quiet_on_idempotent_reemit_same_lane():
    plan = _board_plan("circuit-solver-delta")
    branches = lambda: ["circuit-solver-delta/cid/task-1", "circuit-solver-delta/cid/task-2"]
    res = preflight.repo_reality_check(plan, branch_probe=branches)
    assert res.ok and res.warnings == []


def test_reality_warns_on_absent_component_root():
    plan = _board_plan("circuit-solver-delta")
    cm = ComponentMap({"netlist": ("project/src/netlist/**",)})
    res = preflight.repo_reality_check(
        plan, comp_map=cm, base_sha="abc123",
        branch_probe=lambda: ["main"],
        tree_probe=lambda sha: ["project/.gitkeep", "crates/digital-kernel/src/lib.rs"],
    )
    assert res.ok  # warning, not error
    assert any("blank workspace" in w and "netlist" in w for w in res.warnings)


def test_reality_clean_when_no_siblings_and_root_present():
    plan = _board_plan("circuit-solver-delta")
    cm = ComponentMap({"netlist": ("project/src/netlist/**",)})
    res = preflight.repo_reality_check(
        plan, comp_map=cm, base_sha="abc123",
        branch_probe=lambda: ["main", "circuit-solver-delta/cid/task-1"],
        tree_probe=lambda sha: ["project/src/netlist/graph.rs"],
    )
    assert res.ok and res.errors == [] and res.warnings == []


def test_reality_never_raises_with_default_probes():
    # Default probes shell out to git; even outside a repo they must degrade
    # to no findings rather than raise.
    plan = _board_plan("circuit-solver-delta")
    res = preflight.repo_reality_check(plan)  # no base_sha/comp_map -> reality skipped
    assert isinstance(res, preflight.PreflightResult)
