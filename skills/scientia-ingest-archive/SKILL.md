---
name: scientia-ingest-archive
description: Atomic per-change archive across all three stores. Confirms applied synthesis, then runs openspec archive on the change, hermes kanban archive on every task in the change, and writes a final wiki/log.md and development/log.md entry. Atomic — either all three succeed or none do. Use after scientia-ingest-synthesize is applied and the user has accepted the proposed wiki edits.
license: MIT
metadata:
  bundle: scientia
  phase: ingest
  order: "3"
---

# scientia-ingest-archive

The closing-the-loop step. Once the change is complete and the wiki
has been updated from the synthesis, archive across all three stores
atomically.

## Preflight gates

Refuse to archive unless **all** of:

- Every kanban task for the change is `status == "done"` and has
  evidence ingested.
- `wiki/syntheses/<tenant>-<change-id>.md` exists and its frontmatter
  has `status: applied` (the user has accepted and applied the
  proposed edits).
- `git:worker-branch-merged` passes for every task's `branch_head`
  (all worker branches are on trunk).
- `openspec verify <tenant>-<change-id>` reports clean (no critical
  findings).

If any gate fails, surface the conflict and refuse. The user fixes
the failed gate, then re-runs.

## Procedure

1. **Plan the archive** as a three-store operation:
   - Store A: Hermes kanban — archive every task in this change.
   - Store B: OpenSpec — move `openspec/changes/<tenant>-<change-id>/`
     to `openspec/archive/<tenant>-<change-id>/`.
   - Store C: Wiki — finalize log entries; mark the synthesis
     `status: archived`.

2. **Dry-run.** Show the user what will happen:
   - List the N kanban task ids that will be archived.
   - Show the OpenSpec source and destination paths.
   - Show the wiki log entries that will be appended.

3. **Confirm with the user.** Require explicit "archive
   `<tenant>/<change-id>`" to proceed.

4. **Execute in order, with rollback discipline:**

   a. **Hermes archive.** For each task: `hermes kanban archive
      <task-id>`. Track which succeeded. If any fails, do not
      proceed; surface the failure and direct user to inspect.
   b. **OpenSpec archive.** `openspec archive <tenant>-<change-id>`.
      Moves the change directory to `openspec/archive/`. If this
      fails after step (a) succeeded, surface the partial state and
      direct user to manually re-run step (b).
   c. **Wiki finalization.** Append to `wiki/log.md`:
      ```bash
      printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-ingest-archive — change-archived — <tenant>/<change-id> — kanban_tasks=<n>' >> wiki/log.md
      ```
      Update `wiki/syntheses/<tenant>-<change-id>.md` frontmatter:
      `status: archived`.

5. **Finalize manifest.** Move `development/manifests/<tenant>/<change-id>/`
   to `development/manifests/<tenant>/archive/<change-id>/`. This
   keeps the manifests durable and reviewable, but makes clear that
   the tenant is now idle (eligible for a new in-flight change).

6. **Finalize task index.** Move
   `development/tasks/<tenant>/<change-id>/` to
   `development/tasks/<tenant>/archive/<change-id>/`.

7. **Append a final entry** to `development/log.md`:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-ingest-archive — archived — <tenant>/<change-id> — atomic=ok' >> development/log.md
   ```

8. **Hand off.** Report archive complete. The tenant is now idle;
   a new change can begin under the same tenant via
   `scientia-wiki-grill` → `scientia-wiki-bind`.

## Rollback discipline

If an intermediate step fails (Hermes archive succeeded but OpenSpec
archive crashed), the user is told the *exact* state and the *exact*
recovery command. Scientia does not silently unarchive Hermes tasks
because OpenSpec failed — that would lose audit trail. The recovery
is always forward (re-run the failed step), not backward.

## What this skill never does

- Deletes anything. Archive = move; nothing is removed from disk.
- Edits the wiki's concept or entity pages (the synthesis already
  did that, with user approval).
- Resurrects archived changes. To re-open work, write a new change
  that supersedes.
