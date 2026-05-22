---
name: scientia-kanban-emit
description: Read a verified scientia OpenSpec change and emit two layers of kanban rows via the Hermes CLI — (1) one impl/review/integrate pipeline per `tasks.md` item, with --workspace worktree and `depends on #N` chains wired as --parent edges, and (2) one parent + N per-scenario child pipelines + one aggregator per spec, where each per-scenario impl declares the relevant tasks.md `:integrate` rows as additional --parent edges. Inlines the Gherkin scenario, bounded-context glossary excerpt, ADR ids, the implementation checklist, and the required-handoff schema into each task body. Use once verify is clean and the change is on trunk. Re-runnable — produces the same task ids for unchanged content.
license: MIT
metadata:
  bundle: scientia
  phase: kanban
  order: "2"
---

# scientia-kanban-emit

The main mutator of the kanban phase. Turns a verified, on-trunk
OpenSpec change into durable rows on `kanban.db`.

Emit happens in two phases per change:

1. **tasks.md items.** Every numbered item in `tasks.md` becomes an
   `impl → review → integrate` pipeline, with `--workspace worktree`
   so each worker gets an isolated git worktree to commit into.
   `(depends on #N)` clauses become `--parent` edges on the impl
   stage; the integrator merges the worktree back to trunk so the
   next item in the chain starts from a clean tree that already
   contains its prereqs' commits.

2. **Per-spec scenarios.** Every Gherkin scenario becomes an
   `impl → review → integrate` pipeline (under `--workspace
   dir:<change-dir>`), with a per-spec parent task and per-spec
   aggregator. Each scenario's impl declares additional `--parent`
   edges pointing at the `:integrate` stage of every tasks.md item
   whose `@spec:` markers match the scenario, plus the transitive
   closure under `depends_on`, plus any tasks.md items with no
   `@spec` marker and no `depends_on` (root-scaffolding items
   universal to every scenario).

The two-phase model exists because per-scenario impls can't safely
start until the shared scaffolding declared in `tasks.md` is on
trunk. Concurrent scenario workers sharing a single `dir:`
workspace would otherwise race each other to set up the same
foundations, ending up with incompatible versions of cross-cutting
code.

## Preflight gates

Refuse to emit if any of:

- The change has no `verify-*.md` report, or the latest one has
  `worst_severity` >= `development/config.yaml`'s
  `verify.block_on_severity`.
- `git:spec-on-trunk` fails — any `spec.md` for the change is on a
  feature branch that has not merged to trunk. The sha256 over a
  moving spec body would produce a meaningless idempotency key.
- The Hermes CLI is not on PATH.
- The Hermes gateway is not running (no `gateway` process in
  `~/.hermes/processes.json`). Without it the dispatcher never ticks,
  so emitted tasks would sit in `todo` forever. Refuse and tell the
  user to start it themselves. Recommended:

  ```bash
  hermes gateway install   # one-time, writes launchd/systemd service
  hermes gateway start     # starts the service
  ```

  Alternatives: `hermes gateway run` (foreground; recommended for
  WSL/Docker/Termux) or `nohup hermes gateway start > ~/.hermes/logs/gateway.log 2>&1 &`
  (no-service-manager fallback; doesn't survive reboot). Full guidance
  in `scientia-kanban-init` step 6.
- An ADR cited by the spec is `deprecated` or `superseded` without a
  successor — emission would be against a stale decision.
- **A required scientia profile does not exist.** For each role this
  emit would assign (`implementer`, `reviewer`, `integrator`,
  `aggregator`), the resolved profile name (default `scientia-<role>`,
  or `hermes.profile_names.<role>` if overridden) must be registered
  with Hermes — `hermes profile show <name>` returns 0. Otherwise the
  dispatcher will park the emitted tasks as `skipped_nonspawnable`
  forever. Refuse and tell the user to run `scientia-kanban-init` to
  create the missing profiles. This gate is independent of
  the model-config drift check below — drift only applies when
  `hermes.profiles` is declared, but profile *existence* is required
  unconditionally.
- **Profile model config drift.** If `development/config.yaml` declares
  `hermes.profiles.<role>`, the effective value of each declared leaf
  (read via `hermes -p <resolved-name> config show --json`) must match
  the declared value. On mismatch, refuse and surface every drifted
  `(profile, key, scientia-value, hermes-value)`; the user re-runs
  `scientia-kanban-init` (which is authoritative) to converge. When
  `hermes.profiles` is absent, the check is a no-op — every profile
  inherits Hermes' host-level defaults and there is nothing to drift
  against. See `scientia-kanban-init/references/profile-models.md` for
  the schema.

## Procedure

1. **Enumerate specs.** For each `openspec/changes/<tenant>-<change-id>/specs/<capability>/spec.md`:

   - Compute the **parent idempotency key**:
     `<capability>:<governing-adr-id>:<sha256(spec-body)>`.
     The sha256 excludes (a) frontmatter, (b) the auto-generated
     `## Kanban Tasks` section. See
     `scripts/idempotency_key.py`.
   - For each `### Scenario:` block, compute the **child key**:
     `<capability>:<governing-adr-id>:<scenario-slug>:<sha256(scenario-block)>`.

2. **Determine collaboration pattern** from the governing ADR's
   status (resolved from the spec's `## Glossary`-adjacent metadata or
   from the change's `adr/`):
   - `accepted` → **P2 pipeline** (`implementer → reviewer →
     integrator`)
   - `proposed` → **P5 human-in-loop** (same P2 plus a final approval
     task emitted with `--triage` so a human specifier promotes it
     before the rest of the pipeline runs)
   - multiple specs in this change → wrap the whole emit in a **P1
     fan-out** parent
   - reviewer-agreement-matters override (per
     `development/config.yaml`'s tenant settings) → **P3
     voting/quorum**
   - `deprecated`/`superseded` without successor → refuse

3. **For each scenario, build the task body** to this schema (verbatim
   from `[[concepts/task-specification]]`):

   ```markdown
   # @wiki-spec: <capability>

   ## Goal
   <verbatim from spec's capability description>

   ## Approach
   <narrative, optional; leave empty if the spec has no opinion>

   ## Acceptance Criteria
   <verbatim from spec's `## Acceptance Criteria`>

   ## Scenario
   ```gherkin
   <verbatim Gherkin block>
   ```

   ## Glossary (inlined; do not paraphrase)
   <verbatim from spec's `## Glossary` section,
    which itself was verbatim from manifest core's slice 4>

   ## Governing ADRs
   - ADR-NNNN — <title> — status=accepted

   ## Implementation Checklist (from tasks.md, advisory)
   <tasks from the parent spec's tasks.md scoped to this scenario>

   ## Required Handoff
   <verbatim from references/HANDOFF_SCHEMA.md>

   ---
   wiki_backlink: wiki/specs/<capability>.md
   idempotency_key: <child-key>
   ```

4. **Build the parent task body**: same shape but at the spec level —
   inlines the full `## Implementation Checklist` from `tasks.md`,
   not just the per-scenario subset. Assignee: `scientia-aggregator`.

5. **Emit via the Hermes CLI.** For each task, in dependency order
   (flags verified against `hermes kanban create --help` on Hermes
   Agent v0.12.0):

   ```bash
   hermes kanban create \
     --idempotency-key "$IDEMPOTENCY_KEY_SHORT" \
     --tenant "$TENANT" \
     --assignee "$PROFILE" \
     --workspace "$KIND:$ABS_PATH" \
     --skill scientia-kanban-worker \
     --skill scientia-grill \
     --body "$(cat "$BODY_TMPFILE")" \
     "$TITLE"
   ```

   - `title` is **positional** (last arg). There is no `--title` flag.
   - `--body` is **inline only**. Read the prepared body tmpfile with
     `"$(cat …)"` — there is no `--body-file`.
   - Tasks link to dependencies via `--parent <id>` on the `create` call
     (repeatable). In Hermes, `--parent` *is* the dependency edge — the
     dispatcher promotes `todo → ready` only after all `--parent` tasks
     reach `done`. Use it for both hierarchy (parent → child) and pipeline
     stages (impl → review → integrate). There is no `--depends-on` flag.
   - `hermes kanban link <parent-id> <child-id>` adds a dependency *after*
     creation; the `--parent` shortcut on `create` avoids the extra call
     in the common case.
   - For pattern P5 ("human-in-loop"), the final approval task is
     emitted with `--triage` (parks the task for a human specifier to
     promote it). There is no `--require-approval` flag.
   - **Absolute workspace paths only** (confused-deputy guard).
   - `--tenant` is the bounded-context slug, always.

   **Rejected flags (do NOT invent these — Hermes will error out with
   `argparse: invalid choice` or `unrecognized arguments`):**

   | If you reach for… | Use instead |
   |---|---|
   | `--title "…"` | positional `"$TITLE"` (last arg) |
   | `--body-file <path>` | `--body "$(cat <path>)"` |
   | `--depends-on <id>` | `--parent <id>` (repeatable) |
   | `--require-approval` | `--triage` (parks task for human promotion) |
   | `--format json` on `kanban list` / `kanban dispatch` | `--json` |

   Re-verify with `hermes kanban create --help` if a flag here ever
   looks stale.

6. **Re-emit semantics.** Hermes' `create --idempotency-key` returns the
   existing task id when a non-archived task with that key already
   exists, but it does **not** update the body / title / assignee —
   there is no `kanban update` verb. So:

   - Same triple → `create` is a no-op aside from returning the id; if
     the freshly-computed body differs from what's on Hermes (e.g.
     glossary was refreshed by a new manifest bind), `emit.py` issues
     `hermes kanban comment <id> --body "refreshed-at: <ts>\n\n<body>"`
     so the latest content is in the comment thread.
   - Edited scenario → new sha → new child key → new child task; the
     old child stays closed (`hermes kanban archive` is up to you).
   - New ADR id (supersession) → new parent key + new child keys →
     fresh task tree; old tree closed.
   - Renamed slug → fresh task tree.

7. **Write the `## Kanban Tasks` section back to each `spec.md`**
   listing parent key, every child key, and aggregator key. This is
   the wiki-side traceability record.

8. **Write index entries** under
   `development/tasks/<tenant>/<change-id>/<task-id>.md` for each
   task, recording the idempotency key and a backlink to the spec.

9. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-kanban-emit — emitted — <tenant>/<change-id> — pattern=<P2|P3|P5|...> tasks=<n>' >> development/log.md
   ```

10. **Hand off.** Stage transitions to `emitted`. Recommended next
    skill: `scientia-kanban-status` (to inspect as workers run).

## Recovery — when workers crash or violate the protocol

A worker that fails to call `hermes kanban complete` or `hermes
kanban block` before its process exits leaves its task parked. The
dispatcher will not re-promote it on the next gateway tick — manual
intervention is required. Two distinct failure modes account for
nearly all of these:

1. **`crashed` — exit code non-zero.** Typically: unknown skill,
   missing profile resources, model credentials not configured.
   Reads as `crashed` in `hermes kanban dispatch --dry-run --json`.
2. **`protocol_violation` — exit code 0, no terminal tool call.**
   The model produced a text-only final assistant turn (often
   prose saying "I'm done" or summarizing the work) without ever
   calling `complete` or `block`. The worker process exits cleanly,
   Hermes records a `protocol_violation` event, and the task moves
   to `gave_up` (`failures: 1, effective_limit: 1, limit_source:
   dispatcher`) — **one strike, retired**. The kanban-worker skill
   (`scientia-kanban-worker/SKILL.md`, "Headless execution
   discipline") forbids this mode explicitly; recurrence usually
   means the skill is not loaded in the worker profile or its
   per-turn invariant is being overridden by a profile body.

**Diagnostics.** Run `hermes kanban dispatch --dry-run --json` and
look at the `skipped_nonspawnable` and `crashed` arrays. A
`skipped_nonspawnable` entry usually means the task's assignee
profile is unknown to Hermes — confirm with
`hermes profile show <assignee>` (this also drives the
profile-existence preflight gate). A `crashed` entry means the
worker exited non-zero; read its stderr with
`hermes kanban log <task-id>`. The most common stderr seen in
practice is `Error: Unknown skill(s): scientia-kanban-worker,
scientia-grill`, which means the profile-local skill symlinks are
missing — re-run `scientia-kanban-init` step 4 to install them.

A **`protocol_violation`** event will not appear in the `crashed`
array (exit was clean). Confirm it by reading the task's event
trail directly:

```sql
sqlite3 ~/.hermes/kanban.db \
  "select event, payload, ts from events where task_id='<task-id>' \
   order by ts desc limit 8;"
```

You'll see `gave_up | {"error": "worker exited cleanly (rc=0)
without calling kanban_complete or kanban_block — protocol
violation", ...}`. The worker session log will read `Messages: 1
(1 user, 0 tool calls)` — silent-by-design. When this mode recurs:

- Verify `scientia-kanban-worker` is actually loaded for the
  assignee's profile: `hermes -p <assignee> skills list --source
  local | grep scientia-kanban-worker`. If absent, re-run
  `scientia-kanban-init` step 4.
- Check the SKILL.md sha against the bundle's: a stale or
  hand-edited copy may have lost the "every turn must contain at
  least one tool call" invariant.
- If both check out and the failure recurs across multiple tasks,
  the model is the likely culprit — escalate via
  `development/config.yaml`'s `hermes.profiles.<role>.model` (see
  `scientia-kanban-init/references/profile-models.md`) and re-run
  init to converge.

**Recovery.** After fixing the underlying cause, re-promote the
parked tasks and let the dispatcher try again:

```bash
hermes kanban unblock <task-id> [<task-id> …]
hermes kanban dispatch --json   # or wait for the next gateway tick
```

`hermes kanban unblock` is positional-only (no `--task-id` flag);
pass each id as a positional argument. Re-running emit is a no-op
for these tasks (the idempotency key already exists) and will not
itself recover them — you must explicitly `unblock`.

## Helpers

- `scripts/idempotency_key.py` — compute the (spec-slug, adr-id, sha)
  triple from a `spec.md` and a scenario block.

  ```bash
  # Parent key (one per spec×ADR):
  python3 scripts/idempotency_key.py --spec <path/to/spec.md> --adr ADR-NNNN

  # Child key (per Gherkin scenario):
  python3 scripts/idempotency_key.py \
      --spec <path/to/spec.md> --adr ADR-NNNN --scenario <scenario-slug>

  # Machine-readable output:
  python3 scripts/idempotency_key.py --spec … --adr … [--scenario …] --json
  ```

  The `--spec` value is a filesystem path to the spec.md; `--adr` is
  the bare id (`ADR-NNNN`, not a path). The script prints the key to
  stdout.
- `scripts/emit.py` — orchestrate the full emit pipeline (preflights,
  pattern selection, body construction, hermes CLI invocation,
  `## Kanban Tasks` writeback).
- `references/HANDOFF_SCHEMA.md` — the verbatim `## Required Handoff`
  block inlined into every task body.

## What this skill never does

- Edits spec bodies (except the auto-generated `## Kanban Tasks`
  section). The sha256 hash deliberately excludes that section.
- Mutates `tasks.md` contents. The apply phase owns the checkbox
  list; emit only reads from `tasks.md` (parses each `- [ ] **N.**`
  bullet for `@spec`/`@adr`/`(depends on #N)` markers) and writes
  per-task index files under
  `development/tasks/<tenant>/<change>/`.
- Spawns workers. That is the gateway-hosted dispatcher's job; emit
  only writes rows to `kanban.db`. If the gateway is down the
  preflight refuses, so emit never leaves orphan rows for a missing
  dispatcher.
- Starts the Hermes gateway. The user owns that process (see
  `scientia-kanban-init` step 6).
- Archives tasks. That is `scientia-kanban-archive` (or
  `scientia-ingest-archive` at change end).

## Running

Prefer the script over the procedure above when possible — the script
owns preflight gates, pattern selection, body construction, the
`hermes kanban create` calls (with the verified CLI shape), the
re-emit refresh-comment, the `## Kanban Tasks` writeback, the per-task
index entries, and the `development/log.md` append:

```bash
python3 skills/scientia-kanban-emit/scripts/emit.py \
    --change <tenant>/<change-slug> \
    [--only-spec <capability>] \
    [--dry-run]
```

The model executes the prose procedure only when the script is
unavailable. Tests live under `skills/scientia-kanban-emit/tests/`
(`python3 -m unittest discover` from the skill directory).
