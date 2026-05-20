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
  user to start it themselves:

  ```bash
  nohup hermes gateway start > ~/.hermes/logs/gateway.log 2>&1 &
  ```

  Same gate as `scientia-kanban-init` step 6 — scientia never spawns
  the gateway, it only refuses to proceed without one.
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
   - Child tasks link to the parent via `--parent <parent-id>` on the
     `create` call (repeatable).
   - Pipeline stage dependencies are added *after* creation, not on
     `create`: `hermes kanban link <previous-stage-id> <new-id>`.
     (There is no `--depends-on` flag on `create`.)
   - For pattern P5 ("human-in-loop"), the final approval task is
     emitted with `--triage` (parks the task for a human specifier to
     promote it). There is no `--require-approval` flag.
   - **Absolute workspace paths only** (confused-deputy guard).
   - `--tenant` is the bounded-context slug, always.

6. **Re-emit semantics.** If a task with the same idempotency key
   already exists:
   - Same triple → update the task body in place (refresh glossary,
     task description), leave id stable.
   - Edited scenario → new sha → new child key → new child task; old
     child closed with a `kanban_comment` pointing forward.
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

## TODO (separate change)

`scripts/emit.py` is referenced in the **Helpers** section above but
not yet written — only `scripts/idempotency_key.py` exists. Until
`emit.py` lands, this SKILL.md procedure is executed by the model
each run, which is exactly how a `--body-file` flag that doesn't exist
in Hermes 0.12.0 shipped (and then had to be improvised around at
runtime — see `~/.pi/sessions/2026-05-20T20-25-03-724Z_*.jsonl`).

Once `scripts/emit.py` is implemented it should own: preflight gates,
pattern selection, body construction, `hermes kanban create` +
`hermes kanban link` calls, `## Kanban Tasks` writeback, and the
`development/log.md` append. The SKILL.md procedure can then collapse
to "run `scripts/emit.py --change <id>`" and CLI flags live in one
tested place. Until then, keep the CLI block above verbatim accurate
against `hermes kanban create --help`.
