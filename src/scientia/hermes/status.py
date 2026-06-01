"""scientia.hermes.status — pure detectors backing scientia-hermes-status (read-only).

The status skill reads each live card's ``assignee`` / ``status`` / ``reason``
from the board (read-only) and feeds them here. These detectors turn that raw
board state into the report's escalations.

The headline detector is :func:`detect_misrouted_reassignments`, which catches a
**conflict-resolver dead-end** (FP2 from the circuit-solver-delta friction
analysis): an integrator hit a real merge conflict, *commented and blocked* the
card with a reason saying "reassigned to <resolver>", but never actually changed
the ``assignee``. The card then sits ``blocked`` forever — the resolver never
receives it, and nothing surfaces it to a human because it *looks* handled. The
plan-side fix (the integrate card now demands a verified reassign) prevents it
going forward; this is the runtime backstop that flags any that still slip
through on a live board.

Pure: the caller supplies the :class:`LiveCard` snapshots, so the deterministic
suite runs this with no Hermes and no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

__all__ = ["LiveCard", "detect_misrouted_reassignments"]

# Phrases an integrator uses when it *intends* to hand a conflict to the
# resolver. Matched case-insensitively against the block reason; the resolver's
# own (prefixed) profile name is also matched, supplied at call time.
_REASSIGN_MARKERS = ("reassign", "conflict-resolver", "conflict resolver")


@dataclass(frozen=True)
class LiveCard:
    """A live board card as seen by the status skill (a read-only snapshot).

    ``assignee`` is the profile that currently owns the card, ``status`` its
    board status (e.g. ``"blocked"``), and ``reason`` the block/handoff text.
    ``stage``/``task_number`` are the scientia mapping (from the ledger or
    :func:`scientia.hermes.idempotency.parse_card_key`) and are carried only for
    reporting.
    """

    hermes_id: str
    assignee: str
    status: str
    reason: str = ""
    title: str = ""
    stage: Optional[str] = None
    task_number: Optional[int] = None


def _claims_reassignment(reason: str, resolver_profile: str, markers: Sequence[str]) -> bool:
    low = reason.lower()
    if resolver_profile and resolver_profile.strip().lower() in low:
        return True
    return any(m in low for m in markers)


def detect_misrouted_reassignments(
    cards: Sequence[LiveCard],
    resolver_profile: str,
    *,
    reassign_markers: Sequence[str] = _REASSIGN_MARKERS,
) -> list[LiveCard]:
    """Blocked cards that *claim* a reassignment to the resolver but were never reassigned (FP2).

    Returns every card that is **blocked**, whose ``reason`` mentions handing the
    work to the conflict-resolver (a marker phrase or the resolver's own profile
    name), yet whose ``assignee`` is **not** the resolver — meaning the
    integrator commented + blocked instead of reassigning, so the resolver never
    gets it and the pipeline silently dead-ends.

    A card genuinely owned by the resolver (``assignee == resolver_profile``) is
    excluded — that is a real escalation surfaced elsewhere, not a dead-end.
    """
    resolver = (resolver_profile or "").strip().lower()
    out: list[LiveCard] = []
    for card in cards:
        if (card.status or "").strip().lower() != "blocked":
            continue
        if (card.assignee or "").strip().lower() == resolver:
            continue  # correctly reassigned — the resolver owns it
        if _claims_reassignment(card.reason or "", resolver_profile, reassign_markers):
            out.append(card)
    return out
