---
name: scientia-kanban-emit
description: Read a verified scientia OpenSpec change, compute idempotency-key triples, pick a collaboration pattern from ADR status, and emit one parent kanban task plus N per-scenario child tasks plus one aggregator task per spec via the Hermes CLI. Inlines the Gherkin scenario, bounded-context glossary excerpt, ADR ids, the implementation checklist, and the required-handoff schema into each task body. Use once verify is clean and the change is on trunk. Re-runnable — produces the same task ids for unchanged content.
license: MIT
metadata:
  bundle: scientia
  phase: kanban
  order: "2"
---

# scientia-kanban-emit

The main mutator of the kanban phase. Turns a verified, on-trunk
OpenSpec change into durable rows on `kanban.db`.

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

   ```markdown
   - YYYY-MM-DDTHH:MM:SSZ — scientia-kanban-emit — emitted — <tenant>/<change-id> — pattern=<P2|P3|P5|...> tasks=<n>
   ```

10. **Hand off.** Stage transitions to `emitted`. Recommended next
    skill: `scientia-kanban-status` (to inspect as workers run).

## Helpers

- `scripts/idempotency_key.py` — compute the (spec-slug, adr-id, sha)
  triple from a `spec.md` and a scenario block.
- `scripts/emit.py` — orchestrate the full emit pipeline (preflights,
  pattern selection, body construction, hermes CLI invocation,
  `## Kanban Tasks` writeback).
- `references/HANDOFF_SCHEMA.md` — the verbatim `## Required Handoff`
  block inlined into every task body.

## What this skill never does

- Edits spec bodies (except the auto-generated `## Kanban Tasks`
  section). The sha256 hash deliberately excludes that section.
- Mutates `tasks.md`. The apply phase owns `tasks.md`.
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
