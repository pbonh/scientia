---
name: scientia-intent-spec
description: Author Gherkin-style executable specifications for a scientia change, one spec.md per capability. Reads the manifest core (especially ubiquitous-language and tradeoffs slices), enforces gherkin-authoring discipline (single When per scenario, observable Then, named personas, Markdown wrappers preserved), and writes openspec/changes/<tenant>-<change-id>/specs/<capability>/spec.md. Use after proposal.md is merged to trunk and before scientia-intent-design.
license: MIT
metadata:
  bundle: scientia
  phase: intent
  openspec_stage: spec
---

# scientia-intent-spec

The spec stage of the OpenSpec intent-driven lifecycle. Produces one
`specs/<capability>/spec.md` per capability declared in the proposal.

## Inputs

- `openspec/changes/<tenant>-<change-id>/proposal.md` (must exist and be
  on trunk).
- `development/manifests/<tenant>/<change-id>/core.md`. Slices 4
  (ubiquitous language) and 9 (tradeoffs & suggestions — though slice 9
  is lazily computed; you may compute and attach it here as part of the
  spec-stage manifest extension).

## Procedure

1. **Enumerate the capabilities** from `proposal.md`'s `## Capabilities
   Introduced or Modified` section. For each, you produce one
   `spec.md`.

2. **For each capability**, write `specs/<capability>/spec.md`:

   ```markdown
   ---
   title: "Spec: <capability-display-name>"
   tenant: <tenant>
   change_id: <change-id>
   capability: <capability-slug>
   created: <YYYY-MM-DD>
   updated: <YYYY-MM-DD>
   ---

   # Capability: <Title>

   <One-paragraph capability description.>

   ## Glossary (inlined from manifest)
   <Verbatim copy of the relevant rows from slice 4 of core.md.>

   ## Personas
   - **<name>** — <one-line description, scope, authority>

   ## Acceptance Criteria
   - <bullet, one per testable outcome>

   ## Scenarios

   ### Scenario: <descriptive imperative title>
   ```gherkin
   Given <persona> <state>
   And <additional state>
   When <single observable action>
   Then <observable outcome>
   And <additional outcome>
   ```

   ### Scenario: <next>
   ...

   ## Kanban Tasks
   <!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
   ```

3. **Discipline — every scenario:**
   - **Single `When`.** If you need two observable actions, write two
     scenarios.
   - **Observable `Then`.** State change a user or another agent can
     see; not implementation noise.
   - **Named personas** (the `## Personas` block defines them).
   - **Glossary terms used exactly as defined in the manifest slice 4.**
     Drift here is a false-cognate bug at emit time.
   - **No imperative implementation detail in the `Given/When/Then`
     prose.** The "how" belongs in the implementation, not the
     specification.

4. **Compute the spec-stage manifest extension** (lazy slice 9):
   identify the relevant tradeoffs and suggestions the wiki documents
   (e.g., imperative-vs-declarative-style, idempotency,
   scenario-outline vs. example-based) and add them to
   `development/manifests/<tenant>/<change-id>/spec.md` (note: this is
   the per-stage manifest extension, *not* the OpenSpec spec.md).

5. **Mirror to wiki living documentation.** For each `spec.md` written,
   create or update `wiki/specs/<capability>.md` with frontmatter
   `type: spec` and a `## Source` section pointing back to
   `openspec/changes/<tenant>-<change-id>/specs/<capability>/spec.md`.
   Add a row to `wiki/index.md`'s **Specs** table.

6. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-intent-spec — spec-authored — <tenant>/<change-id> — capability=<slug> scenarios=<n>' >> development/log.md
   ```

7. **Hand off.** Report to the orchestrator: stage transitioned to
   `specs`. Next recommended skill: `scientia-intent-design`.

## Gates

- Refuse to write if `proposal.md` is missing or not on trunk
  (`git-spec-on-trunk` is checked again before emit, but you should
  gate here too to surface early).
- Refuse if any scenario violates the single-`When` rule (the
  gherkin-authoring discipline is mandatory, not advisory).

## What this skill never does

- Writes implementation. Specs describe behavior; implementation is
  the kanban worker's job.
- Edits the `## Kanban Tasks` section — only `scientia-kanban-emit`
  writes there.
- Edits other capabilities' spec files. One skill activation, one
  capability ideally, though multiple capabilities per activation are
  fine if the agent is careful.
