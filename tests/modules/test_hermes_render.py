"""Tests for scientia.hermes.render (AC-14 reassign, AC-15 REST shape)."""

from pathlib import Path

from scientia.hermes import parse, render
from scientia.hermes.plan import PlanOptions, Routing, build_plan
from scientia.hermes.render import task_payload, to_cli, to_rest

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"
ROUTING = Routing(
    default_implementer="implementer", default_reviewer="reviewer",
    default_integrator="integrator", resolver="conflict-resolver",
    tenant="2026-05-28-rag-replacement",
)


def _plan(**opts):
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    return build_plan("2026-05-28-rag-replacement", tasks, c4, cm, contracts, ROUTING, PlanOptions(**opts))


def _id_for(plan):
    keys = ([plan.epic.key] if plan.epic else []) + [c.key for c in plan.cards]
    table = {k: f"H{i}" for i, k in enumerate(keys)}
    return lambda k: table.get(k)


def test_to_rest_creates_then_links_all_through_kanban_routes():
    plan = _plan()
    ops = render.to_rest(plan, _id_for(plan))
    creates = [o for o in ops if o["path"] == "/tasks"]
    links = [o for o in ops if o["path"] == "/links"]
    # epic + 12 stage cards = 13 creates
    assert len(creates) == 13
    # every create carries its key as the idempotency key (AC-15 idempotency seam)
    assert all(o["json"]["idempotency_key"] == o["key"] for o in creates)
    # all creates precede all links
    assert ops.index(creates[-1]) < ops.index(links[0])
    # links reference resolved ids
    assert all(isinstance(o["json"]["parent"], str) and isinstance(o["json"]["child"], str) for o in links)


def test_to_rest_link_count_matches_total_parent_edges():
    plan = _plan()
    cards = [plan.epic] + list(plan.cards) if plan.epic else list(plan.cards)
    expected = sum(len(c.parents) for c in cards)
    links = [o for o in render.to_rest(plan, _id_for(plan)) if o["path"] == "/links"]
    assert len(links) == expected


def test_epic_create_has_no_assignee_field_when_unassigned():
    plan = _plan()
    epic_op = render.to_rest(plan, _id_for(plan))[0]
    assert epic_op["json"]["idempotency_key"] == plan.epic.key
    assert "assignee" not in epic_op["json"]  # epic is informational, not dispatched


def test_to_cli_mirrors_rest_with_kanban_argv():
    plan = _plan(pipeline="single", emit_epic=False)
    argv = render.to_cli(plan, _id_for(plan))
    creates = [a for a in argv if a[:4] == ["hermes", "kanban", "task", "create"]]
    assert len(creates) == 4
    assert all("--idempotency-key" in a for a in creates)


def test_reassign_op_targets_the_resolver_not_a_block():
    op = render.reassign_op("H7", "conflict-resolver")
    assert op["method"] == "PATCH"
    assert op["path"] == "/tasks/H7"
    assert op["json"] == {"assignee": "conflict-resolver"}


def test_integrate_body_instructs_reassign_to_resolver_not_human_block():
    plan = _plan()
    integ = next(c for c in plan.cards if c.stage == "integrate")
    assert "conflict-resolver" in integ.body
    assert "reassign" in integ.body.lower()
    assert "do not block for a human" in integ.body.lower()


def test_archive_ops_patch_status_archived():
    ops = render.archive_ops(["H1", "H2"])
    assert ops == [
        {"method": "PATCH", "path": "/tasks/H1", "json": {"status": "archived"}},
        {"method": "PATCH", "path": "/tasks/H2", "json": {"status": "archived"}},
    ]


def _board_plan(board):
    tasks = parse.parse_tasks((FIX / "tasks.md").read_text())
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    routing = Routing(
        default_implementer="implementer", default_reviewer="reviewer",
        default_integrator="integrator", resolver="conflict-resolver",
        tenant="2026-05-28-rag-replacement", board=board,
    )
    return build_plan("2026-05-28-rag-replacement", tasks, c4, cm, contracts, routing, PlanOptions())


def test_resolved_board_is_threaded_into_payloads_and_argv():
    # No board -> the field is omitted (back-compat with the Hermes default board).
    assert "board" not in task_payload(next(iter(_plan().cards)))
    # board set on the plan -> sent on every create (REST body + --board CLI flag).
    plan = _board_plan("acme-service")
    assert task_payload(next(iter(plan.cards)), plan.board)["board"] == "acme-service"
    rest_creates = [o["json"] for o in to_rest(plan, _id_for(plan)) if o["path"] == "/tasks"]
    assert rest_creates and all(p["board"] == "acme-service" for p in rest_creates)
    cli_creates = [
        a for a in to_cli(plan, _id_for(plan)) if a[:4] == ["hermes", "kanban", "task", "create"]
    ]
    assert cli_creates and all(
        "--board" in a and a[a.index("--board") + 1] == "acme-service" for a in cli_creates
    )
