"""AC-10: the deterministic core imports and runs with no Hermes and no network.

Two guards: (1) a static check that the pure modules never import network/process
machinery, and (2) an end-to-end run of parse -> build_plan -> render that touches
neither preflight nor apply.
"""

from pathlib import Path

from scientia.hermes import parse, render
from scientia.hermes.plan import PlanOptions, Routing, build_plan

PKG = Path(__file__).resolve().parent.parent.parent / "src" / "scientia" / "hermes"
PURE = ["parse", "idempotency", "conflict", "plan", "render", "validators", "ledger"]
FORBIDDEN = ("import socket", "import subprocess", "import urllib", "urllib.request")
FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"


def test_pure_modules_do_no_network_or_process_io():
    for mod in PURE:
        src = (PKG / f"{mod}.py").read_text()
        for needle in FORBIDDEN:
            assert needle not in src, f"{mod}.py must stay pure (found {needle!r})"


def test_only_apply_and_preflight_are_impure():
    assert "import socket" in (PKG / "preflight.py").read_text()
    assert "import urllib.request" in (PKG / "apply.py").read_text()


def test_pure_pipeline_runs_offline():
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    routing = Routing(
        default_implementer="implementer", default_reviewer="reviewer",
        default_integrator="integrator", resolver="conflict-resolver",
    )
    plan = build_plan("cid", tasks, c4, cm, contracts, routing, PlanOptions())
    ops = render.to_rest(plan, lambda k: "id:" + k)
    assert ops and all(o["path"] in ("/tasks", "/links") for o in ops)
