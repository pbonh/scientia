"""Tests for scientia.hermes.ledger — local index + supersede diff (AC-4)."""

from pathlib import Path

import pytest

from scientia.hermes import ledger, parse
from scientia.hermes.ledger import LedgerEntry
from scientia.hermes.plan import PlanOptions, Routing, build_plan

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "hermes-change"
ROUTING = Routing(
    default_implementer="implementer", default_reviewer="reviewer",
    default_integrator="integrator", resolver="conflict-resolver",
)
CID = "2026-05-28-rag-replacement"


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("SCIENTIA_ROOT", str(tmp_path))
    return tmp_path


def _plan_from(tasks_md):
    tasks = parse.parse_tasks(tasks_md)
    c4, cm, contracts = parse.parse_design((FIX / "design.md").read_text())
    return build_plan(CID, tasks, c4, cm, contracts, ROUTING,
                      PlanOptions(conflict_prevention=False))


def test_round_trip_is_idempotent_on_disk(root):
    entries = {
        "k1": LedgerEntry("k1", 1, "impl", "H1", "sha1", "todo"),
        "k2": LedgerEntry("k2", 1, "review", None, "sha1", None),
    }
    ledger.record(CID, entries)
    first = (root / "proposals" / CID / "hermes" / "emit-ledger.json").read_bytes()
    loaded = ledger.load(CID)
    assert loaded["k1"] == entries["k1"]
    ledger.record(CID, loaded)  # writing what we loaded changes nothing
    assert (root / "proposals" / CID / "hermes" / "emit-ledger.json").read_bytes() == first


def test_load_missing_ledger_returns_empty(root):
    assert ledger.load("never-emitted") == {}


def test_diff_reports_all_added_on_first_emit(root):
    plan = _plan_from((FIX / "tasks.md").read_text())
    d = ledger.diff({}, plan)
    assert len(d.added) == len(plan.cards) + 1  # + epic
    assert d.removed == [] and d.changed == []


def test_unchanged_re_emit_diffs_clean(root):
    plan = _plan_from((FIX / "tasks.md").read_text())
    old = ledger.entries_for_plan(plan)
    d = ledger.diff(old, plan)
    assert d.is_empty


def test_editing_a_task_rekeys_and_reports_changed(root):
    plan_a = _plan_from((FIX / "tasks.md").read_text())
    old = ledger.entries_for_plan(plan_a)
    # edit task 4's wording -> its three stage cards re-key
    edited = (FIX / "tasks.md").read_text().replace(
        "Roll the new score into the wiki dump", "Roll the new score into the wiki dump and index"
    )
    plan_b = _plan_from(edited)
    d = ledger.diff(old, plan_b)
    # task 4's impl/review/integrate are re-keyed: 3 changed, nothing else
    assert len(d.changed) == 3
    assert d.added == [] and d.removed == []
    for old_key, new_key in d.changed:
        assert ":task:4:" in old_key and ":task:4:" in new_key and old_key != new_key
