"""scientia.hermes.conflict — the conflict-*prevention* math (pure).

Two deterministic mechanisms, both fed by the authoring-stage ownership markers
(``touches`` / ``produces-contract`` / ``uses-contract``). They are the
structural half of the proposal's conflict-robustness story; the *resolution*
half lives in the ``conflict-resolver`` profile, downstream.

* **File-collision waves** (:func:`compute_waves` / :func:`synthetic_edges`).
  Tasks that touch overlapping paths are spread across "waves" so that at most
  ``max_parallel_per_file_group`` editors of any one path are promotable at
  once; the overflow is serialized by synthetic dependency edges that point a
  later wave's task at the prior wave's *integrate* (so it rebases against a
  trunk that already contains the earlier commit).

* **Shared-contract ratification** (:func:`ratify_contracts`). A task that
  *uses* a shared contract may only proceed once the contract's shape is pinned
  — either by a task that *produces* it (made a parent), or by an accepted ADR.
  Otherwise emit refuses, naming every unpinned ``(consumer, contract)`` pair,
  so two siblings cannot independently invent incompatible versions of the same
  interface.

Wave semantics note: the cap is *per path, per wave*. With the default cap of 2,
two tasks sharing a file may sit in the same wave (their residual conflict is
handled by the resolver downstream); a third forces a new wave. This follows the
normative docstring in the proposal (§6.2) and AC-12 — "no more than
``max_parallel_per_file_group`` cards sharing a touches path are simultaneously
promotable."
"""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

from scientia.hermes.parse import Task

__all__ = [
    "ContractError",
    "compute_waves",
    "synthetic_edges",
    "ratify_contracts",
]


def compute_waves(
    tasks: Sequence[Task], *, max_parallel_per_file_group: int
) -> dict[int, int]:
    """Assign each task a wave index from its ``touches`` overlaps.

    Tasks with no ``touches``, or whose touched paths no other task shares, land
    in wave 0. When more than ``max_parallel_per_file_group`` tasks touch the
    same path, the surplus is pushed to higher waves. Deterministic: tasks are
    considered in ascending ``number`` order and given the lowest wave that keeps
    every one of their paths under the cap.
    """
    cap = max(1, int(max_parallel_per_file_group))
    waves: dict[int, int] = {}
    per_wave_path: dict[tuple[int, str], int] = defaultdict(int)
    for task in sorted(tasks, key=lambda t: t.number):
        if not task.touches:
            waves[task.number] = 0
            continue
        wave = 0
        while not all(per_wave_path[(wave, p)] < cap for p in task.touches):
            wave += 1
        waves[task.number] = wave
        for p in task.touches:
            per_wave_path[(wave, p)] += 1
    return waves


def synthetic_edges(
    tasks: Sequence[Task], waves: Mapping[int, int]
) -> list[tuple[int, int]]:
    """``(parent#, child#)`` edges serializing later waves behind earlier ones.

    For every shared path, tasks are grouped by wave and consecutive wave groups
    are linked parent->child, so a wave-N+1 task starts only once the wave-N
    tasks touching the same path have integrated. The result is de-duplicated and
    sorted for determinism.
    """
    by_path: dict[str, list[int]] = defaultdict(list)
    for task in tasks:
        for p in task.touches:
            by_path[p].append(task.number)

    edges: set[tuple[int, int]] = set()
    for members in by_path.values():
        by_wave: dict[int, list[int]] = defaultdict(list)
        for num in members:
            by_wave[waves[num]].append(num)
        ordered = sorted(by_wave)
        for i in range(len(ordered) - 1):
            for parent in by_wave[ordered[i]]:
                for child in by_wave[ordered[i + 1]]:
                    if parent != child:
                        edges.add((parent, child))
    return sorted(edges)


class ContractError(ValueError):
    """Raised when a ``uses-contract`` task has no producer and no ADR pin."""

    def __init__(self, gaps: Sequence[tuple[int, str]]):
        self.gaps = sorted(set(gaps))
        detail = "; ".join(
            f"task #{num} uses unratified contract {name!r}" for num, name in self.gaps
        )
        super().__init__(
            f"{len(self.gaps)} shared-contract gap(s) — add a producing task or "
            f"ratify via an accepted ADR: {detail}"
        )


def ratify_contracts(
    tasks: Sequence[Task], adr_contracts: set[str]
) -> list[tuple[int, int]]:
    """``(producer#, consumer#)`` edges per shared contract.

    A consumed contract is pinned if some task *produces* it (an edge is added
    from each producer to the consumer) or if it appears in ``adr_contracts``
    (the set of contract names ratified by an *accepted* ADR — resolved by the
    caller, keeping this function pure). A contract that is pinned by neither is a
    gap; if any gaps exist, raises :class:`ContractError` naming all of them.
    """
    producers: dict[str, list[int]] = defaultdict(list)
    for task in tasks:
        for name in task.produces_contracts:
            producers[name].append(task.number)

    edges: set[tuple[int, int]] = set()
    gaps: list[tuple[int, str]] = []
    for task in tasks:
        for name in task.uses_contracts:
            if producers.get(name):
                for producer in producers[name]:
                    if producer != task.number:
                        edges.add((producer, task.number))
            elif name in adr_contracts:
                continue  # pinned by an accepted ADR — no producer edge needed
            else:
                gaps.append((task.number, name))
    if gaps:
        raise ContractError(gaps)
    return sorted(edges)
