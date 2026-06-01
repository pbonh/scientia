---
name: scientia-generate-tasks
description: Produces tasks.md — a markdown checklist with frontmatter — from design.md and the ADRs. Each task references the spec scenario(s) it satisfies via a traces-spec comment and is grouped by ADR where applicable. This is the final stage of the pipeline; no execution follows. Activate after the ADRs for a change are recorded.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+
metadata:
  stage: tasks
  version: "1.0"
---

# scientia-generate-tasks

Decompose `design.md` and the ADRs into an ordered, dependency-aware checklist
at `proposals/<change-id>/tasks.md`. This is where the authoring pipeline ends —
nothing executes the tasks.

## Inputs

- `proposals/<change-id>/design.md`
- `proposals/<change-id>/adrs/`

## Outputs

- `proposals/<change-id>/tasks.md`, rendered from the `tasks` template via
  `scientia.templates.render_to_file("tasks", paths.tasks_path(cid), ...)`.

## Authoring discipline

- Markdown checkboxes: `- [ ] **N.** <task>`.
- **Every task carries a `traces-spec` comment** naming the scenario it
  satisfies: `<!-- traces-spec: <capability>#<scenario-id> -->`.
- Group tasks by ADR where applicable: `<!-- traces-adr: ADR-NNNN -->`.
- Order by dependency; note prerequisites inline (e.g. `(depends on #N)`).
- `scientia.validators.validate_tasks` checks for checklist items and
  `traces-spec` markers.

## Ownership markers (gated: `hermes.conflict_prevention: true`)

When the optional `hermes:` block is present **and** `conflict_prevention` is
true, additionally tag each task with the markers the execution layer's wave +
ratification math reads (parsed by `scientia.hermes.parse.parse_tasks`):

- `<!-- component: <c4-component-id> -->` — the component this task realizes.
- `<!-- touches: path, path -->` — the files it modifies, **constrained to that
  component's owned globs** from `design.md`'s Component Map (a cross-boundary
  touch is a smell `scientia.hermes.validators.ownership_smells` surfaces).
- `<!-- produces-contract: X -->` / `<!-- uses-contract: X -->` — shared
  interfaces it defines / consumes. Order producers before consumers.

`scientia.validators.validate_tasks(path, require_prevention=True)` then requires
each task to carry `component` and `touches`. When prevention is off, none of
these are required and `tasks.md` keeps its current shape (AC-16).

## Decision rules

- A task with no traceable scenario is a smell — either it is missing a spec or
  it is out of scope; surface it rather than inventing a scenario.
- Use `scientia.paths` for all paths.

## Low-confidence handling (mode key: `generate_tasks`, default `autonomous`)

Tasks are revisable; runs `autonomous`. Encode the most defensible decomposition
and note open sequencing questions inline.

## Acceptance behavior (spec: intent-artifact-generation)

- Each task in `tasks.md` carries a `traces-spec` comment naming the scenario it
  satisfies.
