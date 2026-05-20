---
name: scientia-ingest-synthesize
description: Per-change cross-task synthesis. Once every kanban task in a change is done, reads all handoffs and Implementation Evidence to distill lessons learned, then writes a proposed-edit synthesis page at wiki/syntheses/<change-id>.md. The synthesis names which existing concept and entity pages should be updated, and which new pages should be created, but does NOT write directly to wiki/concepts/ or wiki/entities/ — the user reviews and applies the synthesis manually. Use exactly once per change.
license: MIT
metadata:
  bundle: scientia
  phase: ingest
  order: "2"
---

# scientia-ingest-synthesize

After every per-task evidence has been ingested, distill the
cross-task story into a proposed synthesis at
`wiki/syntheses/<tenant>-<change-id>.md`. **Proposed edits only.**
Direct writes to `wiki/concepts/` and `wiki/entities/` are not allowed
(this is enforced by `development/config.yaml`'s
`ingest.synthesize_proposes_only: true`).

## Procedure

1. **Verify readiness.** Every kanban task for the change is `done`.
   Every task has had `scientia-ingest-evidence` applied
   (its idempotency-key has a matching bullet on the relevant spec
   page). If not, refuse and direct user to ingest evidence first.

2. **Assemble the cross-task picture.** Read:
   - Every `## Implementation Evidence` bullet across all spec pages
     for this change.
   - Every task's `## Required Handoff` block (especially
     `residual_risk` and `dependencies`).
   - The change's `design.md` and ADRs (now with hindsight after
     implementation).
   - The bound manifest layers (`core.md`, `design.md`, `tasks.md`).

3. **Identify candidates** for wiki update:

   - **Existing concept pages to extend.** A concept the change
     touched whose `## Risks & Pitfalls` should now include a newly
     learned pitfall, or whose `## Key Parameters` should reflect a
     newly understood constraint.
   - **Existing entity pages to extend.** An entity the change
     adopted (library, tool, service) whose `## Common Strategies`
     should now include the strategy the change demonstrated.
   - **New concept pages.** A pattern, anti-pattern, or technique the
     change discovered that does not yet have a wiki page.
   - **New entity pages.** A tool, library, or service introduced
     during implementation that does not yet have an entity page.
   - **Context page updates.** The bounded context's
     `## Ubiquitous Language` glossary may now include new terms; its
     `## In-Scope Concepts` / `## In-Scope Entities` may need entries.
   - **ADR follow-ups.** Decisions the change deferred or surfaced
     that warrant a new ADR in a future change.

4. **Write the synthesis** at
   `wiki/syntheses/<tenant>-<change-id>.md`:

   ```yaml
   ---
   title: "Synthesis: <change title>"
   type: synthesis
   tenant: <tenant>
   change_id: <change-id>
   status: proposed                 # proposed | applied | superseded
   created: <YYYY-MM-DDTHH:MM:SSZ>
   pages_compared: [<list of pages whose evidence informed this synthesis>]
   ---

   # Synthesis: <Title>

   ## Cross-Task Summary
   <2–5 paragraphs of what happened end-to-end during this change.>

   ## Proposed Edits

   ### Update [[concepts/<slug>]]
   - **Section:** `## Risks & Pitfalls`
   - **Add bullet:** "<text>"
   - **Justification:** <one line>
   - **Source tasks:** t_a1b2, t_c3d4

   ### Update [[entities/<slug>]]
   - **Section:** `## Common Strategies`
   - **Add paragraph:** "<text>"
   - ...

   ### New page [[concepts/<new-slug>]]
   - **Type:** concept
   - **Tags:** [concept, ...]
   - **Definition:** <2–3 sentences>
   - **Why now:** <which task discovered this>

   ### Update [[contexts/<tenant>]]
   - **Section:** `## Ubiquitous Language`
   - **Add term:** `<term>` — <definition>

   ## Deferred Follow-ups
   - <ADR-worthy decisions the change surfaced but deferred>
   - <Future spec / change candidates>

   ## How to Apply

   Each `### Update` and `### New page` block above is a proposed
   edit. To apply:

   1. Review each block with the user.
   2. For accepted blocks, edit the named page (or create it).
   3. Update the synthesis frontmatter: `status: applied`.
   4. Append a line to `wiki/log.md` per page edited.
   ```

5. **Update `wiki/index.md`** — add a row to the **Syntheses** table.

6. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-ingest-synthesize — synthesized — <tenant>/<change-id> — proposed_edits=<n>' >> development/log.md
   ```

7. **Hand off.** Tell the user the synthesis is ready for review.
   Recommended next step: review the synthesis, apply accepted edits,
   then run `scientia-ingest-archive`.

## Gates

- Refuse if any kanban task for the change is not `done`.
- Refuse if any task's evidence has not been ingested.
- Refuse to write directly to `wiki/concepts/` or `wiki/entities/`.
  The synthesis is a proposal; the user (or a separate
  human-approved action) materializes the edits.

## What this skill never does

- Edits concept or entity pages directly.
- Archives the change. That is `scientia-ingest-archive`.
- Edits OpenSpec change artifacts.
- Decides which proposed edits the user should accept. That is the
  user's call.
