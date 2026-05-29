---
name: scientia-write-design
description: Produces design.md from the gherkin specs, including C4 diagrams as mermaid code blocks, capturing implementation approach, trade-offs, and component boundaries. Requires at least one mermaid C4Container diagram. Defaults to pause_and_ask because design decisions create durable downstream commitments. Activate after the specs for a change are written.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+
metadata:
  stage: design
  version: "1.0"
---

# scientia-write-design

Synthesize the specs into `proposals/<change-id>/design.md`: how the change is
built, the trade-offs, and the component boundaries — grounded in C4 diagrams.

## Inputs

- `proposals/<change-id>/specs/` (all capability specs)

## Outputs

- `proposals/<change-id>/design.md`, rendered from the `c4` template via
  `scientia.templates.render_to_file("c4", paths.design_path(cid), ...)`.

## Requirements

- **At least one mermaid `C4Container` diagram** (the `c4` template ships one;
  adapt it to the actual containers). `scientia.validators.validate_design`
  enforces this — the design stage will not advance without it.
- Draw only the C4 levels that answer a real question (context, container, and
  — if a single container's internals matter — component). Prefer the smallest
  useful set.
- Cover: overview, the component/module structure the specs imply, and the
  trade-offs you are accepting.

## Conflict-prevention inputs (gated: `hermes.conflict_prevention: true`)

When the optional `hermes:` config block is present **and**
`conflict_prevention` is true, additionally emit two sections so the execution
layer (`scientia-hermes-emit`) can decompose work without collisions:

- **`## Component Map`** — each C4 component id → the path globs it owns, one
  bullet per component (`- confidence: src/scientia/confidence.py,
  tests/modules/test_confidence.py`). Derive boundaries from the
  container/component diagram and the wiki's bounded contexts.
- **`## Shared Contracts`** — each cross-component interface, pinned to an owner
  and (where decided) an ADR
  (`- confidence.EffectiveScore — owner: confidence — ratified-by: ADR-0004`).

`scientia.validators.validate_design(path, require_prevention=True)` then
**requires** both sections; when prevention is off, neither is required and the
design keeps its current shape (full backward compatibility).

## Decision rules

- Validate with `validate_design(paths.design_path(cid))` before finishing
  (pass `require_prevention=True` when `hermes.conflict_prevention` is on).
- Keep diagrams as mermaid code blocks embedded in markdown — no external image
  assets.

## Low-confidence handling (mode key: `write_design`, default `pause_and_ask`)

Design is one of the two stages nearest a durable architectural commitment, so
it defaults to `pause_and_ask`. At a low-confidence branch — a component
boundary or technology choice the KG does not strongly support — emit
`proposals/<change-id>/question-for-operator.md` (via
`scientia.paths.question_for_operator_path`) describing the options and halt.
Do not silently pick.

## Acceptance behavior (spec: intent-artifact-generation)

- The produced `design.md` contains at least one mermaid `C4Container` diagram.
