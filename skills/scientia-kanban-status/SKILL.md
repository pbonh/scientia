---
name: scientia-kanban-status
description: Read-only inspection of the Hermes Kanban board for one or more scientia changes. Lists tasks by tenant + change-id, surfaces blocked tasks and their reasons, summarizes aggregator results, and verifies that recorded idempotency keys still match the current spec hashes. Use whenever the user asks "what's the status?" or as the polling loop between emit and ingest. Never mutates the board.
license: MIT
metadata:
  bundle: scientia
  phase: kanban
  role: read-only
---

# scientia-kanban-status

Inspect the board. Mutations are owned by `scientia-kanban-emit` and
`scientia-kanban-archive`.

## Procedure

1. **Scope.** The user (or orchestrator) supplies one of:
   - a specific `<tenant>/<change-id>` to inspect,
   - a tenant only (show all of that tenant's tasks),
   - `--all` (every in-flight tenant).

2. **List tasks** via `hermes kanban list --tenant <t> --json`.
   Filter to rows whose body or title contains the change-id (the
   `@wiki-spec` tag is sufficient).

3. **Group by spec.** Within a change, group child tasks under their
   parent (the aggregator). For each group, summarize:
   - **Aggregator (parent)** — status, claim_lock, comment count.
   - **Children** — one row per scenario, with status, assignee,
     `branch_head` (if completed), and verification outcome.

4. **Surface blocked tasks prominently.** For each blocked task, show
   the latest comment from the worker that explains the block. Show
   the recommended next step the worker suggested. This is the
   "what's stopping us" view.

5. **Idempotency-drift check.** For every task with a recorded
   `idempotency_key` (read from
   `development/tasks/<tenant>/<change-id>/<task-id>.md`), recompute
   the current sha256 of the referenced spec body and compare. If
   they disagree, surface as `idempotency-drift` — the spec was
   edited after emit; consider re-emit.

6. **Output as a markdown table** to the user:

   ```markdown
   ## <tenant>/<change-id> — Pattern: P2 pipeline

   ### Spec: <capability> — aggregator t_a1b2 (ready)

   | Task | Scenario | Stage | Assignee | Status | Verification | Notes |
   |---|---|---|---|---|---|---|
   | t_c3d4 | refund-cash | impl | scientia-implementer | done | green | branch_head abc123 |
   | t_e5f6 | refund-cash | review | scientia-reviewer | running | — | claimed 4m ago |
   | t_g7h8 | refund-credit | impl | scientia-implementer | blocked | — | "glossary conflict on 'refundable_until'" |
   ```

7. **Compute the stage** for the change overall:
   - `running` if any task is `running`.
   - `blocked` if no task is `running` and at least one is `blocked`.
   - `done` if every child + aggregator is `done`.
   - `mixed` otherwise.

8. **Append a status entry** to `development/log.md` (optional; the
   orchestrator may invoke this for polling and not want a log spam.
   Default: log only when the overall stage changes).

## What this skill never does

- Creates, updates, claims, or archives tasks. Read-only.
- Edits spec or change artifacts.
- Refreshes idempotency keys (that requires `scientia-kanban-emit`
  re-run).
