---
name: scientia-intent-design
description: Draft the design.md for a scientia OpenSpec change. Computes the design-stage manifest extension (in-force ADRs via supersession walk, ASRs/QAS, known pitfalls), then writes design.md with C4-style diagrams and an explicit treatment of how each in-force ADR is honored, overridden, or unaffected. Use after specs are merged to trunk and before scientia-intent-adr.
license: MIT
metadata:
  bundle: scientia
  phase: intent
  openspec_stage: design
---

# scientia-intent-design

The design stage. Translates the *what* (proposal + specs) into a
concrete *how*, while honoring every in-force ADR.

## Inputs

- `openspec/changes/<tenant>-<change-id>/proposal.md`
- `openspec/changes/<tenant>-<change-id>/specs/*/spec.md`
- `development/manifests/<tenant>/<change-id>/core.md`

## Procedure

1. **Compute the design-stage manifest extension** at
   `development/manifests/<tenant>/<change-id>/design.md`:

   - **Slice 5 — In-force ADRs.** Walk the ADR supersession graph in
     `wiki/decisions/` and (if any change has already shipped ADRs in
     this repo) `openspec/archive/`. Filter to ADRs whose `tags:` or
     `## Architecturally Significant Requirement` touches the change
     scope. List by `(id, title, status, ASR)`.
   - **Slice 6 — ASRs / QAS.** Quality-attribute scenarios and
     architecturally-significant requirements from the wiki.
   - **Slice 8 — Known pitfalls.** Extract `## Risks & Pitfalls`
     bullets from in-scope concept pages (manifest core slice 2) that
     are relevant to the design choices being made.

   Frontmatter:

   ```yaml
   ---
   title: "Design manifest — <tenant>/<change-id>"
   type: manifest-design
   tenant: <tenant>
   change_id: <change-id>
   scientia_schema: 1
   wiki_snapshot: <git-rev-at-design-entry>     # may differ from core's pin
   created: <YYYY-MM-DD>
   ---
   ```

2. **Write `design.md`** at the change directory:

   ```markdown
   ---
   title: "Design: <change title>"
   tenant: <tenant>
   change_id: <change-id>
   manifest_design: development/manifests/<tenant>/<change-id>/design.md
   created: <YYYY-MM-DD>
   ---

   # Design

   ## Overview
   <2–4 paragraphs of how this change will be implemented at a high level.>

   ## Context Diagram (C4 L1)
   <Mermaid block. Plain Mermaid, not C4-specific Mermaid.>

   ## Container / Component Diagram (C4 L2/L3, as appropriate)
   <Mermaid block. Smallest useful diagram set. Do not over-draw.>

   ## In-Force ADR Treatment
   For each in-force ADR from the design manifest's slice 5:
   - **ADR-NNNN — <title>** — _Honored | Overridden by ADR-MMMM | Not Applicable_
     <one paragraph justifying.>

   ## Architecturally Significant Requirements
   <Reference manifest slice 6. State which ASRs the design must meet.>

   ## Known Pitfalls Avoided
   <Reference manifest slice 8 and state how the design avoids each.>

   ## Open Questions
   - <questions the grill could not resolve at proposal stage,
     promoted here if they touch design>
   - <new questions surfaced during design>

   ## Decisions Distilled to ADRs
   The following design decisions will be captured as ADRs by
   `scientia-intent-adr`:
   - <decision, with proposed ADR slug>
   - ...
   ```

3. **Treat each in-force ADR explicitly.** This is the rule that
   prevents silent override. If the design contradicts an accepted
   ADR, the conflict goes in `## Open Questions` until the user
   chooses to supersede the ADR (which is `scientia-intent-adr`'s
   job, not this skill's).

4. **Use the smallest useful diagram set.** A change spanning one
   bounded context usually needs one L1 context diagram + one L3
   component diagram. Resist drawing L2 container diagrams unless the
   change crosses processes.

5. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-intent-design — design-drafted — <tenant>/<change-id> — adrs_in_force=<n> open_questions=<n>' >> development/log.md
   ```

6. **Hand off.** Stage transitions to `design`. Next recommended
   skill: `scientia-intent-adr`.

## Gates

- Refuse to write if no `specs/` directory exists for the change.
- The supersession walk must complete (no orphan ADRs, no unresolved
  `Supersedes:` chains). If walk fails, report findings and refuse to
  draft until the wiki is repaired.

## What this skill never does

- Writes ADRs. ADR authoring is `scientia-intent-adr`.
- Edits in-force ADRs. ADRs are immutable; supersede via a new ADR.
- Emits tasks. Emission is `scientia-kanban-emit` after the full
  intent stage is verified.
