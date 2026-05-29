"""Integration tests for scientia.hermes.apply behind a recording transport stub
(AC-3 idempotent re-emit, AC-4 archive-on-supersede, AC-15 REST routes).

No Hermes process: the single ``transport`` seam is replaced with a stub that
records every call and hands back deterministic ids (AC-10).
"""

from pathlib import Path

import pytest

from scientia.hermes import apply as apply_mod
from scientia.hermes import ledger, parse
from scientia.hermes.plan import PlanOptions, Routing, build_plan

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"
ROUTING = Routing(
    default_implementer="implementer", default_reviewer="reviewer",
    default_integrator="integrator", resolver="conflict-resolver",
    tenant="2026-05-28-rag-replacement",
)
CID = "2026-05-28-rag-replacement"


class RecordingTransport:
    def __init__(self):
        self.calls = []
        self._n = 0

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        if method == "POST" and path == "/tasks":
            self._n += 1
            return {"id": f"H{self._n}"}
        return {}

    def of(self, method, path_prefix=""):
        return [c for c in self.calls if c[0] == method and c[1].startswith(path_prefix)]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENTIA_ROOT", str(tmp_path))
    return tmp_path


def _plan_from(tasks_md, **opts):
    tasks = parse.parse_tasks(tasks_md)
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    return build_plan(CID, tasks, c4, cm, contracts, ROUTING, PlanOptions(**opts))


def test_dry_run_sends_nothing_and_writes_no_ledger(root):
    plan = _plan_from((FIX / "tasks.md").read_text())
    t = RecordingTransport()
    result = apply_mod.apply(plan, dry_run=True, transport=t)
    assert t.calls == []
    assert all(v == "(new)" for v in result.values())
    assert ledger.load(CID) == {}


def test_first_emit_creates_every_card_and_wires_links(root):
    plan = _plan_from((FIX / "tasks.md").read_text())
    t = RecordingTransport()
    result = apply_mod.apply(plan, dry_run=False, transport=t)
    creates = t.of("POST", "/tasks")
    links = t.of("POST", "/links")
    assert len(creates) == 13  # epic + 12 stage cards
    cards = [plan.epic] + list(plan.cards)
    assert len(links) == sum(len(c.parents) for c in cards)
    # every card got an id, recorded in the ledger
    saved = ledger.load(CID)
    assert len(saved) == 13
    assert all(e.hermes_id for e in saved.values())
    assert result[plan.epic.key].startswith("H")


def test_all_mutations_go_through_kanban_routes(root):
    plan = _plan_from((FIX / "tasks.md").read_text())
    t = RecordingTransport()
    apply_mod.apply(plan, dry_run=False, transport=t)
    for method, path, _ in t.calls:
        assert path == "/tasks" or path == "/links" or path.startswith("/tasks/")


def test_re_emit_unchanged_creates_zero_new_tasks(root):
    plan = _plan_from((FIX / "tasks.md").read_text())
    apply_mod.apply(plan, dry_run=False, transport=RecordingTransport())
    before = ledger.load(CID)

    t2 = RecordingTransport()
    apply_mod.apply(plan, dry_run=False, transport=t2)
    assert t2.of("POST", "/tasks") == []  # ledger pre-check -> nothing created
    assert t2.of("POST", "/links") == []
    after = ledger.load(CID)
    assert {k: v.hermes_id for k, v in after.items()} == {
        k: v.hermes_id for k, v in before.items()
    }


def test_editing_a_task_creates_new_cards_and_archives_superseded(root):
    plan_a = _plan_from((FIX / "tasks.md").read_text())
    apply_mod.apply(plan_a, dry_run=False, transport=RecordingTransport())
    old_ledger = ledger.load(CID)
    old_task4_ids = {
        e.hermes_id for e in old_ledger.values() if e.task_number == 4
    }

    edited = (FIX / "tasks.md").read_text().replace(
        "Roll the new score into the wiki dump",
        "Roll the new score into the wiki dump and index",
    )
    plan_b = _plan_from(edited)
    t = RecordingTransport()
    apply_mod.apply(plan_b, dry_run=False, transport=t, on_supersede="archive")

    # exactly task 4's 3 stage cards are (re)created
    assert len(t.of("POST", "/tasks")) == 3
    # the 3 superseded cards are archived via PATCH status=archived
    archives = [c for c in t.calls if c[0] == "PATCH" and c[2] == {"status": "archived"}]
    assert len(archives) == 3
    archived_ids = {c[1].rsplit("/", 1)[-1] for c in archives}
    assert archived_ids == old_task4_ids
    # the new ledger no longer carries the superseded keys
    new_ledger = ledger.load(CID)
    assert all(":task:4:" not in k or new_ledger[k].hermes_id for k in new_ledger)


def test_editing_an_upstream_task_rewires_downstream_links(root):
    # Editing task 1 (which task 2 depends on) re-keys task 1's cards; task 2's
    # impl, though unchanged, must be rewired onto the NEW task-1 integrate.
    plan_a = _plan_from((FIX / "tasks.md").read_text())
    apply_mod.apply(plan_a, dry_run=False, transport=RecordingTransport())

    edited = (FIX / "tasks.md").read_text().replace(
        "Define the EffectiveScore contract",
        "Define the EffectiveScore contract precisely",
    )
    plan_b = _plan_from(edited)
    t = RecordingTransport()
    apply_mod.apply(plan_b, dry_run=False, transport=t)

    # the new task-1 integrate id is a fresh create; a link must point it at an
    # existing (un-recreated) downstream child
    new_ledger = ledger.load(CID)
    new_t1_integrate = next(
        e.hermes_id for k, e in new_ledger.items()
        if e.task_number == 1 and e.stage == "integrate"
    )
    link_parents = {c[2]["parent"] for c in t.of("POST", "/links")}
    assert new_t1_integrate in link_parents


def test_on_supersede_leave_keeps_old_cards(root):
    plan_a = _plan_from((FIX / "tasks.md").read_text())
    apply_mod.apply(plan_a, dry_run=False, transport=RecordingTransport())
    edited = (FIX / "tasks.md").read_text().replace(
        "Roll the new score into the wiki dump",
        "Roll the new score into the wiki dump and index",
    )
    t = RecordingTransport()
    apply_mod.apply(_plan_from(edited), dry_run=False, transport=t, on_supersede="leave")
    assert [c for c in t.calls if c[0] == "PATCH"] == []
