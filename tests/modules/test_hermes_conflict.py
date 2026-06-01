"""Tests for scientia.hermes.conflict — the prevention math (AC-12, AC-13)."""

import pytest

from scientia.hermes import conflict
from scientia.hermes.parse import Task


def _t(number, touches=(), produces=(), uses=()):
    return Task(
        number=number,
        title=f"t{number}",
        touches=tuple(touches),
        produces_contracts=tuple(produces),
        uses_contracts=tuple(uses),
    )


def test_disjoint_tasks_all_share_wave_zero():
    tasks = [_t(1, ["a.py"]), _t(2, ["b.py"]), _t(3, ["c.py"])]
    assert conflict.compute_waves(tasks, max_parallel_per_file_group=2) == {1: 0, 2: 0, 3: 0}


def test_tasks_with_no_touches_are_unconstrained():
    tasks = [_t(1), _t(2), _t(3)]
    assert conflict.compute_waves(tasks, max_parallel_per_file_group=1) == {1: 0, 2: 0, 3: 0}


def test_cap_overflow_pushes_surplus_to_next_wave():
    # Three tasks share one file; cap 2 -> third spills to wave 1.
    tasks = [_t(1, ["f.py"]), _t(2, ["f.py"]), _t(3, ["f.py"])]
    waves = conflict.compute_waves(tasks, max_parallel_per_file_group=2)
    assert waves == {1: 0, 2: 0, 3: 1}
    # No more than `cap` cards sharing the path sit in any wave (AC-12).
    counts = {}
    for num, w in waves.items():
        counts[w] = counts.get(w, 0) + 1
    assert max(counts.values()) <= 2


def test_cap_one_fully_serializes_a_shared_file():
    tasks = [_t(1, ["f.py"]), _t(2, ["f.py"]), _t(3, ["f.py"])]
    assert conflict.compute_waves(tasks, max_parallel_per_file_group=1) == {1: 0, 2: 1, 3: 2}


def test_synthetic_edges_serialize_consecutive_waves_on_shared_path():
    tasks = [_t(1, ["f.py"]), _t(2, ["f.py"]), _t(3, ["f.py"])]
    waves = conflict.compute_waves(tasks, max_parallel_per_file_group=2)  # {1:0,2:0,3:1}
    edges = conflict.synthetic_edges(tasks, waves)
    # wave-1 task 3 serialized behind wave-0 tasks 1 and 2 (they share f.py)
    assert edges == [(1, 3), (2, 3)]


def test_no_synthetic_edges_when_all_in_one_wave():
    tasks = [_t(1, ["f.py"]), _t(2, ["f.py"])]
    waves = conflict.compute_waves(tasks, max_parallel_per_file_group=2)
    assert conflict.synthetic_edges(tasks, waves) == []


def test_ratify_links_producer_before_consumer():
    tasks = [_t(1, produces=["X"]), _t(2, uses=["X"])]
    assert conflict.ratify_contracts(tasks, set()) == [(1, 2)]


def test_ratify_accepts_adr_pinned_contract_without_producer():
    tasks = [_t(2, uses=["X"])]
    assert conflict.ratify_contracts(tasks, {"X"}) == []


def test_ratify_raises_on_unpinned_contract_naming_every_gap():
    tasks = [_t(2, uses=["X"]), _t(3, uses=["Y"])]
    with pytest.raises(conflict.ContractError) as exc:
        conflict.ratify_contracts(tasks, set())
    assert exc.value.gaps == [(2, "X"), (3, "Y")]
    assert "X" in str(exc.value) and "Y" in str(exc.value)
