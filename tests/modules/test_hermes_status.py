"""Tests for scientia.hermes.status — the FP2 conflict-resolver dead-end detector."""

from scientia.hermes import status
from scientia.hermes.status import LiveCard

RESOLVER = "circuit-solver-delta-conflict-resolver"
INTEGRATOR = "circuit-solver-delta-integrator"


def _card(**kw):
    base = dict(hermes_id="t_x", assignee=INTEGRATOR, status="blocked", reason="")
    base.update(kw)
    return LiveCard(**base)


def test_flags_blocked_card_that_claims_reassign_but_assignee_unchanged():
    cards = [
        _card(
            hermes_id="t_4d0139b9",
            reason="conflict-detected: 6 files in conflict. Reassigned to "
                   "circuit-solver-delta-conflict-resolver per integrator protocol.",
        )
    ]
    out = status.detect_misrouted_reassignments(cards, RESOLVER)
    assert [c.hermes_id for c in out] == ["t_4d0139b9"]


def test_matches_on_resolver_profile_name_even_without_reassign_word():
    cards = [_card(reason=f"handed off to {RESOLVER}")]
    assert len(status.detect_misrouted_reassignments(cards, RESOLVER)) == 1


def test_does_not_flag_card_actually_owned_by_resolver():
    # Correctly reassigned: the resolver owns it and blocked it -> real escalation, not a dead-end.
    cards = [_card(assignee=RESOLVER, reason="reassigned; genuine spec contradiction")]
    assert status.detect_misrouted_reassignments(cards, RESOLVER) == []


def test_does_not_flag_blocked_card_without_reassign_claim():
    # A green self-block (handled by a different detector) must not be caught here.
    cards = [_card(reason="review-required: 50/50 tests pass, needs eyes before merge")]
    assert status.detect_misrouted_reassignments(cards, RESOLVER) == []


def test_does_not_flag_non_blocked_cards():
    cards = [
        _card(status="running", reason="reassigned to the conflict-resolver"),
        _card(status="todo", reason="reassign to conflict-resolver"),
        _card(status="done", reason="done"),
    ]
    assert status.detect_misrouted_reassignments(cards, RESOLVER) == []


def test_case_insensitive_status_and_marker():
    cards = [_card(status="BLOCKED", reason="REASSIGN to the resolver")]
    assert len(status.detect_misrouted_reassignments(cards, RESOLVER)) == 1


def test_unprefixed_resolver_name():
    cards = [
        LiveCard(hermes_id="t1", assignee="integrator", status="blocked",
                 reason="reassigned to conflict-resolver"),
        LiveCard(hermes_id="t2", assignee="conflict-resolver", status="blocked",
                 reason="reassigned to conflict-resolver"),
    ]
    out = status.detect_misrouted_reassignments(cards, "conflict-resolver")
    assert [c.hermes_id for c in out] == ["t1"]


def test_empty_input():
    assert status.detect_misrouted_reassignments([], RESOLVER) == []
