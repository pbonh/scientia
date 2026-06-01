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


def test_to_rest_creates_carry_parents_no_separate_link_pass():
    plan = _plan()
    ops = render.to_rest(plan, _id_for(plan))
    creates = [o for o in ops if o["path"] == "/tasks"]
    links = [o for o in ops if o["path"] == "/links"]
    # epic + 12 stage cards = 13 creates
    assert len(creates) == 13
    # every create carries its key as the idempotency key (AC-15 idempotency seam)
    assert all(o["json"]["idempotency_key"] == o["key"] for o in creates)
    # parents are wired AT CREATE (friction F-1) -> there is no /links pass
    assert links == []
    # a card with parents carries resolved string ids in its create payload
    with_parents = [o for o in creates if o["json"].get("parents")]
    assert with_parents
    assert all(isinstance(p, str) for o in with_parents for p in o["json"]["parents"])


def test_to_rest_parent_count_matches_total_parent_edges():
    plan = _plan()
    cards = [plan.epic] + list(plan.cards) if plan.epic else list(plan.cards)
    expected = sum(len(c.parents) for c in cards)
    creates = [o for o in render.to_rest(plan, _id_for(plan)) if o["path"] == "/tasks"]
    wired = sum(len(o["json"].get("parents", [])) for o in creates)
    assert wired == expected


def test_epic_create_has_no_assignee_field_when_unassigned():
    plan = _plan()
    epic_op = render.to_rest(plan, _id_for(plan))[0]
    assert epic_op["json"]["idempotency_key"] == plan.epic.key
    assert "assignee" not in epic_op["json"]  # epic is informational, not dispatched


def _cli_creates(argv):
    return [a for a in argv if "create" in a and "--idempotency-key" in a]


def test_to_cli_mirrors_rest_with_kanban_argv():
    plan = _plan(pipeline="single", emit_epic=False)
    argv = render.to_cli(plan, _id_for(plan))
    creates = _cli_creates(argv)
    assert len(creates) == 4
    assert all("--idempotency-key" in a for a in creates)


def test_to_cli_uses_v0_15_grammar_not_the_legacy_task_subcommand():
    # v0.15.1: `hermes kanban create <title> …` — no `task` subcommand, title is
    # positional, and there is no `--status` flag on create.
    plan = _plan(pipeline="single", emit_epic=False)
    creates = _cli_creates(render.to_cli(plan, _id_for(plan)))
    for cmd in creates:
        assert cmd[:3] == ["hermes", "kanban", "create"]   # no "task" token
        assert "task" not in cmd
        assert "--title" not in cmd and "--status" not in cmd
        assert cmd[3].startswith("[")                      # positional title (e.g. "[single] #1 …")
        assert "--model-provider" not in cmd               # model is profile-level on the CLI backend


def test_to_cli_wires_parents_at_create_no_link_pass():
    plan = _plan()  # impl-review-integrate -> intra-task parent edges exist
    argv = render.to_cli(plan, _id_for(plan))
    # parents ride on create (friction F-1); there is no separate `link` pass
    assert not any(a[:3] == ["hermes", "kanban", "link"] for a in argv)
    cards = [plan.epic] + list(plan.cards) if plan.epic else list(plan.cards)
    expected = sum(len(c.parents) for c in cards)
    parent_flags = sum(a.count("--parent") for a in argv)
    assert parent_flags == expected and expected > 0


def test_archive_argv_uses_archive_verb():
    assert render.archive_argv(["t_1", "t_2"]) == [
        ["hermes", "kanban", "archive", "t_1"],
        ["hermes", "kanban", "archive", "t_2"],
    ]


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
    cli_creates = _cli_creates(to_cli(plan, _id_for(plan)))
    assert cli_creates and all(
        "--board" in a and a[a.index("--board") + 1] == "acme-service" for a in cli_creates
    )
    # --board is group-level: it precedes the `create` verb, not after it.
    assert all(a.index("--board") < a.index("create") for a in cli_creates)
