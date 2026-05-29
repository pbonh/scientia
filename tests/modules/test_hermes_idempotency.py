"""Tests for scientia.hermes.idempotency (AC-3, AC-4 key behavior)."""

import pytest

from scientia.hermes import idempotency
from scientia.hermes.parse import Task


def _task(**kw):
    base = dict(number=1, title="t", touches=("a.py",))
    base.update(kw)
    return Task(**base)


def test_key_shape_and_per_stage_suffix():
    t = _task()
    sha = idempotency.source_sha(t)
    for stage in ("impl", "review", "integrate", "single"):
        key = idempotency.card_key("cid", number=1, sha=sha, stage=stage)
        assert key == f"cid:task:1:{sha}:{stage}"
    assert idempotency.epic_key("cid", sha="abc123") == "cid:epic:abc123"


def test_sha_stable_under_marker_reordering():
    a = _task(spec_refs=("x", "y"), touches=("a.py", "b.py"), depends_on=(2, 3))
    b = _task(spec_refs=("y", "x"), touches=("b.py", "a.py"), depends_on=(3, 2))
    assert idempotency.source_sha(a) == idempotency.source_sha(b)


def test_sha_changes_on_text_edit():
    a = _task(title="do the thing")
    b = _task(title="do the thing differently")
    assert idempotency.source_sha(a) != idempotency.source_sha(b)


def test_sha_changes_when_dependencies_change():
    a = _task(depends_on=(2,))
    b = _task(depends_on=(2, 3))
    assert idempotency.source_sha(a) != idempotency.source_sha(b)


def test_invalid_task_stage_rejected():
    with pytest.raises(ValueError):
        idempotency.card_key("cid", number=1, sha="x", stage="epic")
    with pytest.raises(ValueError):
        idempotency.card_key("cid", number=1, sha="x", stage="bogus")


def test_parse_card_key_round_trips_task_and_epic():
    info = idempotency.parse_card_key("2026-demo:task:3:deadbeef0000:review")
    assert info == {
        "kind": "task",
        "change_id": "2026-demo",
        "task_number": 3,
        "sha": "deadbeef0000",
        "stage": "review",
    }
    epic = idempotency.parse_card_key("2026-demo:epic:abc123")
    assert epic["kind"] == "epic" and epic["task_number"] is None and epic["stage"] == "epic"


def test_parse_card_key_rejects_garbage():
    with pytest.raises(ValueError):
        idempotency.parse_card_key("not-a-key")
