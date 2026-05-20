---
name: scientia-kanban-archive
description: Per-task Hermes Kanban archive operation. Moves a done task to archived status, GC's its workspace directory, and updates development/tasks/<tenant>/<change-id>/ index entries. Destructive — separate from scientia-kanban-status to prevent accidental invocation. Per-change archive across all stores (wiki + openspec + hermes) is scientia-ingest-archive's job; this skill is for ad-hoc, one-off archive of a single task.
license: MIT
metadata:
  bundle: scientia
  phase: kanban
  role: destructive
---

# scientia-kanban-archive

Archive one or more done kanban tasks. Destructive; deliberately
separated from `scientia-kanban-status` to prevent accidental archive
when the user only wanted to inspect.

## When to use this skill vs. `scientia-ingest-archive`

- **`scientia-kanban-archive`** — single-task, ad-hoc cleanup. Use when
  you have a stray done task whose change-context is already settled
  (e.g., a P5 approval task that landed weeks ago).
- **`scientia-ingest-archive`** — per-change atomic archive across
  *all three* stores (wiki updates + OpenSpec archive + Hermes archive
  for every task in the change). Use at the end of a change.

99% of the time you want `scientia-ingest-archive`. This skill exists
for the 1% case.

## Procedure

1. **Identify the task(s)** by id or by query (e.g., "all done tasks
   in tenant `billing` older than 30 days").

2. **For each target task**, verify:
   - `status == "done"` (not `running`, not `blocked`).
   - Its evidence has been ingested
     (`scientia-ingest-evidence` has recorded it on the relevant
     spec's `## Implementation Evidence`). If not, **refuse** and
     direct the user to ingest first.

3. **Archive** via `hermes kanban archive <task-id> [<task-id> …]`.
   `task_ids` are **positional** (space-separated); there is no
   `--ids` / `--task` flag. Single-task and bulk forms:

   ```bash
   # Single task:
   hermes kanban archive t_d733f67e

   # Bulk (one call per batch; all-or-nothing per Hermes):
   hermes kanban archive t_a1 t_b2 t_c3 t_d4
   ```

   This sets status `done → archived` and GC's the workspace directory.

4. **Update the task index** at
   `development/tasks/<tenant>/<change-id>/<task-id>.md`: mark
   `status: archived` in the frontmatter; do not delete the file.

5. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-kanban-archive — archived — <tenant>/<change-id> — task=<id>' >> development/log.md
   ```

## Gates

- Refuse to archive a task whose evidence has not been ingested.
- Refuse to archive a task whose change is still in-flight (other
  tasks in the same change are not done). Use ingest-archive at
  change end instead.

## What this skill never does

- Archives anything in `openspec/changes/`. That is OpenSpec's
  `archive` command, invoked by `scientia-ingest-archive`.
- Edits the wiki. Read-only against `wiki/`.
- Deletes anything. Archive = status flip + workspace GC, not
  filesystem deletion of task records.
