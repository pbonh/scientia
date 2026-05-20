---
name: scientia-intent-proposal
description: Draft the proposal.md for a scientia OpenSpec change. Reads the bound manifest's core, delegates to scientia-grill to stress-test the why and what-changes, then writes openspec/changes/<tenant>-<change-id>/proposal.md. Use exactly once per change, after scientia-wiki-bind has produced core.md and before any spec/design/adr/tasks work begins. Never edits an already-merged proposal — to change a merged proposal, supersede the entire change.
license: MIT
metadata:
  bundle: scientia
  phase: intent
  openspec_stage: proposal
---

# scientia-intent-proposal

The proposal stage of the OpenSpec intent-driven lifecycle. Produces
`openspec/changes/<tenant>-<change-id>/proposal.md`.

## Inputs

- `development/manifests/<tenant>/<change-id>/core.md` (must exist).
- The user's intent — *why* this change should happen, *what changes*,
  *what breaks*.

## Procedure

1. **Read the manifest core.** Especially slices 1 (domain framing),
   2 (in-scope concepts), 4 (ubiquitous language). These are the
   constraints the proposal must honor.

2. **Stress-test the intent via `scientia-grill`.** Invoke the grill
   skill with the user's draft intent as the target. Use it to
   surface:
   - Is the *why* concrete, or is it paperwork?
   - Are all "what changes" bullets specific enough to spec?
   - Which changes are breaking, and is each one explicitly flagged?
   - Are out-of-scope items named?
   - Does the proposal contradict any in-force ADR from the wiki's
     `wiki/decisions/`? (Surface; do not silently override.)
   - Are the capabilities aligned with the manifest's `capabilities:`
     frontmatter field?

3. **Write `proposal.md`** with this structure:

   ```markdown
   ---
   title: "<short imperative title>"
   tenant: <tenant>
   change_id: <change-id>
   manifest_core: development/manifests/<tenant>/<change-id>/core.md
   created: <YYYY-MM-DD>
   ---

   # Proposal: <title>

   ## Why
   <2–5 paragraphs of motivation. Cite concept pages and prior work
   from the manifest's slice 7.>

   ## What Changes
   - <bullet — one observable change per bullet>
   - **BREAKING:** <flag breaking changes explicitly>
   - ...

   ## Out of Scope
   - <bullet>

   ## Capabilities Introduced or Modified
   - `<capability-slug>` — <one-line description>
   - ...

   ## Open Questions
   - <parked during grill>
   - ...

   ## References
   - Manifest core: `development/manifests/<tenant>/<change-id>/core.md`
   - Relevant ADRs: `[[decisions/<adr-id>]]`, ...
   - Related concepts: `[[concepts/<slug>]]`, ...
   ```

4. **Append to `development/log.md`:**

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-intent-proposal — proposal-drafted — <tenant>/<change-id> — capabilities=<n> breaking=<n>' >> development/log.md
   ```

5. **Hand off.** Report to the orchestrator: stage transitioned to
   `proposed`. Next recommended skill: `scientia-intent-spec`.

## Gates

- Refuse to write if `core.md` does not exist at the expected path.
- Refuse to write if a `proposal.md` already exists for this change
  (proposals are not edited after first write; correct course is to
  add an addendum section labeled `## Addendum <date>`, or to write a
  superseding change).
- The grill must run to completion (or be explicitly skipped with the
  user typing *"skip grill"*, which is recorded in the log as a
  gate-override).

## What this skill never does

- Writes spec, design, ADR, or tasks. Each downstream stage is its own
  skill.
- Computes the design or tasks extension of the manifest. Those are
  computed at the entry of `scientia-intent-design` and
  `scientia-intent-tasks` respectively.
- Edits an in-force ADR. ADR supersession is the responsibility of
  `scientia-intent-adr`.
