---
name: scientia-hermes-status
description: Reports change-level progress for a Hermes-emitted change and surfaces blocks. Reads the local emit-ledger plus the live board, maps every live card back to its scientia (task number, stage), summarizes impl/review/integrate progress, attaches the latest handoff, and lists any genuine escalations the conflict-resolver flagged with their reasons. Read-only. Activate to check on an emitted change or after a run to see what needs a human.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+; a local Hermes install with the Kanban feature
metadata:
  stage: hermes-status
  version: "0.2"
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

1. **Load the ledger.** `entries = scientia.hermes.ledger.load(cid)`.
2. **Read the board.** Fetch each `hermes_id`'s live status.
3. **Map back.** For each live card, use `scientia.hermes.idempotency.parse_card_key(key)`
   (or the ledger entry) to recover its `(task_number, stage)`.
4. **Summarize per task.** For each scientia task, report the state of its
   `impl / review / integrate` chain and attach the latest `kanban_complete`
   handoff metadata (`changed_files`, `verification`, `branch_head`).
5. **Surface escalations.** List any card the `conflict-resolver` `block`ed
   (a genuine spec contradiction, unratified-contract divergence, or
   verification that would not go green) **with its reason** — this is the only
   place a human is asked to act.
6. **Detect green self-blocks.** An impl card with `status=blocked` whose
   reason contains "review-required" and whose handoff metadata shows all tests
   passing is a **green self-block** — redundant given the dedicated review
   stage. Recommend `unblock` rather than surfacing it as an escalation.
7. **Report drift.** A ledger id absent from the board (or a board card with no
   ledger entry) is reported as drift to reconcile (re-emit).
8. **Warn about worktree recycling.** Note that worktree directories are
   recycled by the dispatcher; code analysis should use git branch references
   (`git show <branch>:<path>`) rather than filesystem reads.

## Decision rules

- Read-only: never create, reassign, or archive — recommend a re-emit instead.
- A reassignment to `conflict-resolver` that is still `running` is **normal
   progress**, not an escalation; only a `block` is an escalation.
- Recommend the next human action only when something is genuinely escalated.

## Acceptance behavior

- Every live card maps back to its scientia `(task number, stage)` via the
  ledger.
- Escalations are listed with their reasons; routine resolver reassignments are
  not reported as blocks.
