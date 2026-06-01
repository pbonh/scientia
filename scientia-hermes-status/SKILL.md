---
name: scientia-hermes-status
description: Reports change-level progress for a Hermes-emitted change and surfaces blocks. Uses the same board and profile-prefix resolution as init/emit to correctly map prefixed profile names (e.g. circuit-solver-beta-implementer) back to their roles. Reads the local emit-ledger plus the live board, maps every live card back to its scientia (task number, stage), summarizes impl/review/integrate progress, attaches the latest handoff, and lists any genuine escalations the conflict-resolver flagged with their reasons. Read-only. Activate to check on an emitted change or after a run to see what needs a human.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+; a local Hermes install with the Kanban feature
metadata:
  stage: hermes-status
  version: "0.3"
---

# scientia-hermes-status

Report where an emitted change stands and surface what (if anything) genuinely
needs a human. This is the **observe** phase — **read-only**; it never mutates
the board.

## Activate when

The operator asks how an emitted change is progressing, or after a run to see
what the `conflict-resolver` escalated.

## Inputs

- `proposals/<change-id>/hermes/emit-ledger.json`
  (`scientia.hermes.ledger.load(cid)`) — the `key ↔ hermes_id`, stage, and
  source-hash index.
- The live board: `GET /board`, `GET /tasks/:id` (or the `hermes kanban` CLI).

## Procedure

1. **Resolve the board and profile prefix.** Use
   `scientia.hermes.board.resolve_board` and `scientia.hermes.board.resolve_profile_prefix`
   with the same `hermes:` config block that init and emit used, so profile
   names are interpreted consistently. The prefixed conflict-resolver name is
   `scientia.hermes.board.prefixed_profile(prefix, "conflict-resolver")`.
2. **Load the ledger.** `entries = scientia.hermes.ledger.load(cid)`.
3. **Read the board.** Fetch each `hermes_id`'s live status.
4. **Map back.** For each live card, use `scientia.hermes.idempotency.parse_card_key(key)`
   (or the ledger entry) to recover its `(task_number, stage)`.
5. **Summarize per task.** For each scientia task, report the state of its
   `impl / review / integrate` chain and attach the latest `kanban_complete`
   handoff metadata (`changed_files`, `verification`, `branch_head`).
6. **Surface escalations.** List any card assigned to the prefixed
   `conflict-resolver` profile that is `block`ed (a genuine spec contradiction,
   unratified-contract divergence, or verification that would not go green)
   **with its reason** — this is the only place a human is asked to act.
7. **Detect green self-blocks.** An impl card with `status=blocked` whose
   reason contains "review-required" and whose handoff metadata shows all tests
   passing is a **green self-block** — redundant given the dedicated review
   stage. Recommend `unblock` rather than surfacing it as an escalation.
8. **Detect mis-routed reassignments (conflict-resolver dead-ends).** Build a
   `scientia.hermes.status.LiveCard` per board card (its `assignee`, `status`,
   `reason`, and mapped `task_number`/`stage`) and run
   `scientia.hermes.status.detect_misrouted_reassignments(cards, resolver)`,
   where `resolver` is the prefixed conflict-resolver name from step 1. It
   returns `blocked` cards whose reason *claims* a reassignment to the resolver
   but whose `assignee` was never changed to it — the integrator commented and
   blocked instead of reassigning, so the resolver never receives the card and
   it stalls **invisibly**. Surface each as a **genuine escalation** — more
   urgent than a normal block, because it looks handled but is not — naming the
   integrator that still owns it. The fix is an operator reassign or a re-emit;
   this skill is read-only.
9. **Report drift.** A ledger id absent from the board (or a board card with no
   ledger entry) is reported as drift to reconcile (re-emit).
10. **Warn about worktree recycling.** Note that worktree directories are
    recycled by the dispatcher; code analysis should use git branch references
    (`git show <branch>:<path>`) rather than filesystem reads.

## Decision rules

- Read-only: never create, reassign, or archive — recommend a re-emit instead.
- A reassignment to `conflict-resolver` that is still `running` is **normal
   progress**, not an escalation; only a `block` is an escalation.
- A `blocked` card whose reason claims a reassignment to the resolver but whose
   `assignee` is unchanged is a **dead-end, not progress** — the resolver never
   got it. Always surface it (step 8); it is the most easily missed escalation
   because it reads as handled.
- Recommend the next human action only when something is genuinely escalated.

## Acceptance behavior

- Every live card maps back to its scientia `(task number, stage)` via the
  ledger.
- Escalations are listed with their reasons; routine resolver reassignments are
  not reported as blocks.
- A blocked card that claims reassignment but was never reassigned to the
  resolver is reported as a dead-end escalation, not silently counted as routed.
