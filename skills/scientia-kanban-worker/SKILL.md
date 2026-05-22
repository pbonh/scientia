---
name: scientia-kanban-worker
description: Worker-side discipline loaded into every Hermes-spawned scientia profile. Knows how to read a kanban task body that follows the scientia schema (inlined Gherkin, glossary, ADRs, implementation checklist, required-handoff), perform the work, post structured comments, fill in the Required Handoff block on completion, and move the task from running to done or blocked correctly. Always present on every scientia agent profile; do not invoke directly.
license: MIT
metadata:
  bundle: scientia
  phase: kanban
  role: worker-discipline
---

# scientia-kanban-worker

This skill is loaded into every scientia agent profile (`implementer`,
`reviewer`, `integrator`, `aggregator`) so they share one consistent
view of task semantics and the structured-handoff protocol. The
*per-role* behavior is in the profile body; this skill is the
*per-task* discipline.

## On spawn

The Hermes dispatcher gives you, in order:

1. **Task title.**
2. **Task body** (the structured block scientia-kanban-emit wrote).
3. **Every comment** on the task, chronologically, with author names.
4. **Completion results of every parent task** (resolved via
   `task_links`).
5. Your **profile's skills and memory** (including this skill).

**There is no hidden context.** If something is not visible on
`hermes kanban show <id>`, it does not exist for you. Do not consult
external state.

## Headless execution discipline

You are spawned by the Hermes dispatcher via `hermes -p <profile> chat
-q "work kanban task <id>"` with `stdin` closed. **There is no user
on the other end of this turn.** Every prompt you "ask" simply ends
the turn waiting for a reply that will never arrive, which the
dispatcher then reaps as a crash — and respawns you into an identical
loop.

Concretely:

- **Never ask clarifying questions of "the user".** No "Would you
  like me to…", "Should I…", "Do you want…", "Let me know if…",
  "Please confirm…", or any other phrasing that solicits a reply.
- **Make the decision yourself, or block the task.** If you face
  genuine ambiguity, choose the documented escape hatch: flip
  `running → blocked` with a comment + handoff that names the
  ambiguity, the options considered, and the recommended next step.
  A human will read it via `hermes kanban show` and either unblock
  with guidance or reassign. *Blocking is how you ask a question.*
- **Do not offer menus of alternatives.** If you find yourself about
  to type "I can do A, B, or C — which do you prefer?", you must
  instead pick one (justify in a comment) or block (citing the
  alternatives in the handoff).
- **Every assistant turn must contain at least one tool call until
  you have called `hermes kanban complete` or `hermes kanban block`
  on this task.** A text-only assistant turn — even one that says
  "the task is complete" or "I'm done" — ends the worker process
  with exit code 0 *without* closing the kanban row. The dispatcher
  records a `protocol_violation` event, marks the task `gave_up`
  (`failures: 1, effective_limit: 1`), and **will not respawn you**
  until a human runs `hermes kanban unblock <id>`. This is the
  single most common scientia worker failure mode; it is
  silent-by-design and indistinguishable in worker logs from a
  successful run (`Messages: 1, 0 tool calls`). Do not let your turn
  end with text alone.
- **Before writing "done" / "complete" / "finished" / "implemented"
  in text, you MUST have *already* issued `hermes kanban complete
  <id>` earlier in the same turn.** Prose is not a completion
  signal — only the `complete` tool call moves the row to `done`.
  If you have nothing left to do but cannot honestly call
  `complete` (tests fail, ambiguity surfaced, dependency missing),
  call `hermes kanban block <id> --reason "…"` instead. Never end
  on prose.
- **Pre-exit self-check.** Before what you intend to be your last
  assistant turn, answer in your own reasoning: *"Did I call
  `hermes kanban complete <id>` or `hermes kanban block <id>` with
  this task's id in this conversation?"* If you cannot point to the
  exact tool call, you have not finished — make the call now. When
  in doubt between `complete` and `block`, block — `complete` is a
  promise to downstream tasks that this work is mergeable, and
  recovery from a false `complete` is more expensive than recovery
  from a precautionary `block`.

This applies to *every* scientia profile (`implementer`, `reviewer`,
`integrator`, `aggregator`) regardless of role. The role decides
*what* you do; this discipline decides *how* you terminate.

## Reading the task body

Every scientia task body follows this fixed structure. Read in order:

1. **`# @wiki-spec:`** line — the spec slug. You may consult
   `wiki/specs/<spec-slug>.md` for living-documentation context but
   never edit it (the aggregator does that).
2. **`## Goal`** — verbatim from spec. This is your contract.
3. **`## Acceptance Criteria`** — also verbatim. Your work must
   satisfy these.
4. **`## Scenario`** — the Gherkin block. This is the executable
   specification.
5. **`## Glossary`** — inlined verbatim from the bounded-context's
   ubiquitous language. **Use these terms exactly as defined.**
   Paraphrasing them risks false-cognate drift across workers.
6. **`## Governing ADRs`** — the in-force decisions you must honor.
   You may read their full text in `openspec/changes/<id>/adr/` or
   `wiki/decisions/`.
7. **`## Implementation Checklist`** — advisory tasks from
   `tasks.md` scoped to this scenario.
8. **`## Required Handoff`** — the schema you will fill on completion.

## During work

- Stay in your assigned workspace (`workspace_path`, always absolute).
- Use the inlined glossary terms exactly. Drift is a defect.
- If you find ambiguity, contradiction with an ADR, or a glossary
  conflict that the task body does not resolve, **do not guess**.
  Mark the task `running → blocked` and post a comment with:
  - the specific ambiguity,
  - the interpretations you considered,
  - a recommended next step (often "user clarify" or "consult
    ADR-NNNN").
- Use `hermes kanban comment <id> --body-file <path>` for substantial
  notes. The comment thread is the durable handoff channel; treat it
  like a per-task journal.

## On completion

1. Build the `## Required Handoff` block per
   `scientia-kanban-emit/references/HANDOFF_SCHEMA.md`. Every field
   required; empty strings only where the schema names them.

2. Post a completion comment that contains the handoff block, then
   call:

   ```bash
   hermes kanban complete <task-id> --result-file <handoff.md>
   ```

   The dispatcher records `completed_at` and unblocks any children
   that depended on this task.

3. **Never archive yourself.** Archive is owned by either the
   integrator (per-task) or `scientia-ingest-archive` (per-change).

## On blocking

1. Post a comment explaining the block.
2. Fill in the handoff block with `blocked_reason` populated and
   `branch_head` set to whatever commit your branch is at.

   ```bash
   hermes kanban block <task-id> --reason "<short>" --result-file <handoff.md>
   ```

3. The task waits for a human or peer agent to post an `unblock`
   comment + flip status to `ready`. When you are re-spawned, you
   will see the full thread.

## What this skill never does

- Decides what role you play. That comes from the profile body
  (`scientia-implementer.md`, etc.).
- Edits intent artifacts (proposal, spec, design, ADR, tasks). Specs
  are upstream contracts.
- Consults external state. If it is not in the task body, the
  comment thread, parent results, or your profile's memory, it
  effectively does not exist.
