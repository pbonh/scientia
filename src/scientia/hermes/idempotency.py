"""scientia.hermes.idempotency — stable, content-addressed card keys.

A card key is the idempotency contract between scientia and Hermes: re-emitting
an unchanged change yields identical keys (so :mod:`.apply` skips creation and
the board is untouched), while editing a task's text changes its key (so the old
card is superseded and a fresh one created — :func:`scientia.hermes.ledger.diff`
reports the swap).

Key shapes::

    <change-id>:task:<N>:<sha>:<stage>      # impl | review | integrate | single
    <change-id>:epic:<sha>                  # the C4 architecture epic

``<sha>`` is a short hash of the *identity-defining* content (not the file's byte
layout): a task's title, dependencies, component, touched paths, contracts, and
spec/ADR refs — each canonicalized so that cosmetically reordering markers does
not churn the key. Reordering whole tasks in the file never changes any key,
because the author's ``**N.**`` number is part of the key, not the line order.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Optional, Sequence

from scientia.hermes.parse import C4Diagram, ComponentMap, Contract, Task

__all__ = [
    "STAGES",
    "source_sha",
    "design_sha",
    "card_key",
    "epic_key",
    "parse_card_key",
]

STAGES = ("epic", "impl", "review", "integrate", "single")

_SHA_LEN = 12
_KEY_RE = re.compile(
    r"^(?P<change>.+?):(?:task:(?P<num>\d+):(?P<sha>[0-9a-f]+):(?P<stage>[a-z]+)"
    r"|epic:(?P<esha>[0-9a-f]+))$"
)


def _short(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:_SHA_LEN]


def source_sha(task: Task) -> str:
    """The content hash of a task's identity. Stable under marker reordering."""
    payload = json.dumps(
        {
            "number": task.number,
            "title": task.title,
            "spec_refs": sorted(task.spec_refs),
            "adr_ref": task.adr_ref,
            "depends_on": sorted(task.depends_on),
            "component": task.component,
            "touches": sorted(task.touches),
            "produces_contracts": sorted(task.produces_contracts),
            "uses_contracts": sorted(task.uses_contracts),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return _short(payload)


def design_sha(
    c4: Sequence[C4Diagram],
    comp_map: ComponentMap,
    contracts: Sequence[Contract],
) -> str:
    """The content hash of the architecture the epic carries."""
    payload = json.dumps(
        {
            "c4": [[d.level, d.title, d.mermaid] for d in c4],
            "owned": {k: sorted(v) for k, v in sorted(comp_map.owned.items())},
            "contracts": sorted(
                [c.name, c.owner, c.ratified_by] for c in contracts
            ),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return _short(payload)


def card_key(change_id: str, *, number: int, sha: str, stage: str) -> str:
    """The key for one stage card of task ``number``."""
    if stage not in STAGES or stage == "epic":
        raise ValueError(f"invalid task stage {stage!r}; expected one of {STAGES[1:]}")
    return f"{change_id}:task:{number}:{sha}:{stage}"


def epic_key(change_id: str, *, sha: str) -> str:
    """The key for the change's C4 architecture epic."""
    return f"{change_id}:epic:{sha}"


def parse_card_key(key: str) -> dict:
    """Decompose a key into ``{kind, change_id, task_number, sha, stage}``.

    ``kind`` is ``"task"`` or ``"epic"``. For an epic, ``task_number`` and
    ``stage`` are ``None`` (``stage`` reported as ``"epic"``). Raises on a key
    that does not match either shape.
    """
    m = _KEY_RE.match(key)
    if not m:
        raise ValueError(f"unrecognized card key: {key!r}")
    if m.group("esha") is not None:
        return {
            "kind": "epic",
            "change_id": m.group("change"),
            "task_number": None,
            "sha": m.group("esha"),
            "stage": "epic",
        }
    return {
        "kind": "task",
        "change_id": m.group("change"),
        "task_number": int(m.group("num")),
        "sha": m.group("sha"),
        "stage": m.group("stage"),
    }
