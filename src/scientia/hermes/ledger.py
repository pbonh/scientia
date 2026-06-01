"""scientia.hermes.ledger — scientia's local index of the board (pure I/O).

Hermes owns the truth (its SQLite DB). This ledger is a *local* mirror at
``proposals/<change-id>/hermes/emit-ledger.json`` — one entry per card (the epic
plus every stage of every task) recording ``key -> hermes_id``, the task's
``source_sha``, and the last seen status. It enables four things:

* **idempotent re-emit** — :mod:`.apply` pre-checks the ledger and skips any key
  it already created (AC-3);
* **link wiring** — resolving a parent card key to its live id;
* **supersede detection** — :func:`diff` reports which keys were *added*,
  *removed*, or *changed* (re-keyed) since the last emit, so superseded cards can
  be archived (AC-4);
* **status mapping** — recovering the ``(task, stage)`` a live id belongs to.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Optional, Union

from scientia import paths
from scientia.hermes import idempotency
from scientia.hermes.plan import EmitPlan

__all__ = ["LedgerEntry", "LedgerDiff", "load", "record", "diff", "entries_for_plan"]


@dataclass
class LedgerEntry:
    key: str
    task_number: Optional[int]
    stage: str
    hermes_id: Optional[str]
    source_sha: str
    last_status: Optional[str] = None


@dataclass
class LedgerDiff:
    added: list[str]
    removed: list[str]
    changed: list[tuple[str, str]]  # (old_key, new_key) for a re-keyed (task, stage)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def load(change_id: str) -> dict[str, LedgerEntry]:
    """Load the ledger for a change. Returns ``{}`` when none exists yet."""
    path = paths.emit_ledger_path(change_id)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, LedgerEntry] = {}
    for key, raw in data.get("entries", {}).items():
        out[key] = LedgerEntry(
            key=key,
            task_number=raw.get("task_number"),
            stage=raw.get("stage", ""),
            hermes_id=raw.get("hermes_id"),
            source_sha=raw.get("source_sha", ""),
            last_status=raw.get("last_status"),
        )
    return out


def record(change_id: str, entries: Union[Mapping[str, LedgerEntry], Iterable[LedgerEntry]]) -> None:
    """Write the ledger (canonical, key-sorted JSON; idempotent on disk)."""
    if isinstance(entries, Mapping):
        items = list(entries.values())
    else:
        items = list(entries)
    payload = {
        "change_id": change_id,
        "entries": {
            e.key: {k: v for k, v in asdict(e).items() if k != "key"}
            for e in sorted(items, key=lambda e: e.key)
        },
    }
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path = paths.emit_ledger_path(change_id)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def entries_for_plan(plan: EmitPlan) -> dict[str, LedgerEntry]:
    """Build fresh (id-less) ledger entries for every card in a plan."""
    cards = ([plan.epic] + list(plan.cards)) if plan.epic is not None else list(plan.cards)
    out: dict[str, LedgerEntry] = {}
    for card in cards:
        info = idempotency.parse_card_key(card.key)
        out[card.key] = LedgerEntry(
            key=card.key,
            task_number=info["task_number"],
            stage=info["stage"],
            hermes_id=None,
            source_sha=info["sha"],
            last_status=None,
        )
    return out


def diff(old: Mapping[str, LedgerEntry], plan: EmitPlan) -> LedgerDiff:
    """Compare the prior ledger against a fresh plan.

    A ``(task, stage)`` present in both but under a different key is reported as
    *changed* (the old card is superseded); keys only in the plan are *added*;
    keys only in the ledger and not re-keyed are *removed*.
    """
    plan_entries = entries_for_plan(plan)
    plan_keys = set(plan_entries)
    old_keys = set(old)

    plan_by_ident = {
        (e.task_number, e.stage): k for k, e in plan_entries.items()
    }
    old_by_ident = {(e.task_number, e.stage): k for k, e in old.items()}

    raw_added = plan_keys - old_keys
    raw_removed = old_keys - plan_keys

    changed: list[tuple[str, str]] = []
    used_added: set[str] = set()
    used_removed: set[str] = set()
    for ident, new_key in plan_by_ident.items():
        old_key = old_by_ident.get(ident)
        if old_key and old_key != new_key and new_key in raw_added and old_key in raw_removed:
            changed.append((old_key, new_key))
            used_added.add(new_key)
            used_removed.add(old_key)

    return LedgerDiff(
        added=sorted(raw_added - used_added),
        removed=sorted(raw_removed - used_removed),
        changed=sorted(changed),
    )
