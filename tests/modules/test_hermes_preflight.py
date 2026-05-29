"""Tests for scientia.hermes.preflight (AC-7 gateway gate, §12 loopback guard).

The gateway probe is injected so these run with no Hermes present (AC-10).
"""

from pathlib import Path

from scientia.hermes import parse, preflight
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
