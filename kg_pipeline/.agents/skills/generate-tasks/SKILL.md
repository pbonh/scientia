---
name: generate-tasks
description: Produces tasks.md — a markdown checklist with frontmatter — from design.md and the ADRs. Each task references the spec scenario(s) it satisfies via a traces-spec comment and is grouped by ADR where applicable. This is the final stage of the pipeline; no execution follows. Activate after the ADRs for a change are recorded.
metadata:
  stage: tasks
  version: "1.0"
---

# generate-tasks

Decompose `design.md` and the ADRs into an ordered, dependency-aware checklist
at `proposals/<change-id>/tasks.md`. This is where the authoring pipeline ends —
nothing executes the tasks.

## Inputs

- `proposals/<change-id>/design.md`
- `proposals/<change-id>/adrs/`

## Outputs

- `proposals/<change-id>/tasks.md`, rendered from the `tasks` template via
  `kg_pipeline.templates.render_to_file("tasks", paths.tasks_path(cid), ...)`.

## Authoring discipline

- Markdown checkboxes: `- [ ] **N.** <task>`.
- **Every task carries a `traces-spec` comment** naming the scenario it
  satisfies: `<!-- traces-spec: <capability>#<scenario-id> -->`.
- Group tasks by ADR where applicable: `<!-- traces-adr: ADR-NNNN -->`.
- Order by dependency; note prerequisites inline (e.g. `(depends on #N)`).
- `kg_pipeline.validators.validate_tasks` checks for checklist items and
  `traces-spec` markers.

## Decision rules

- A task with no traceable scenario is a smell — either it is missing a spec or
  it is out of scope; surface it rather than inventing a scenario.
- Use `kg_pipeline.paths` for all paths.

## Low-confidence handling (mode key: `generate_tasks`, default `autonomous`)

Tasks are revisable; runs `autonomous`. Encode the most defensible decomposition
and note open sequencing questions inline.

## Acceptance behavior (spec: intent-artifact-generation)

- Each task in `tasks.md` carries a `traces-spec` comment naming the scenario it
  satisfies.
