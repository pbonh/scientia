---
title: "ADR-0005: Lay out produced changes under a flat proposals/<change-id>/ tree"
adr_id: ADR-0005
status: accepted
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Portability: produced artifacts are not coupled to OpenSpec's directory contract (ASR-1)."
shared_types: []
tags: [spec-driven-development, file-layout, portability]
created: 2026-05-27
---

# ADR-0005: Lay out produced changes under a flat proposals/<change-id>/ tree

## Y-Statement

**In the context of** a portable pipeline that *produces* changes (proposal,
grill, specs, design, ADRs, tasks) on disk,
**facing** the choice between the OpenSpec-shaped layout this very repo uses
(`openspec/changes/<id>/` + `development/manifests/<id>/`) and the seed brief's
flatter `proposals/<change-id>/` tree,
**we decided for** the brief's flat `proposals/<change-id>/` layout, with all
paths centralized in `kg_pipeline.paths`,
**and against** reproducing the OpenSpec directory contract or making the layout
pluggable,
**to achieve** portability — produced artifacts carry no dependency on
OpenSpec's conventions (opencode + OpenSpec are tested-against, not required) —
and a single source of layout truth,
**accepting** that the produced layout diverges from scientia's own
self-hosting layout and is not drop-in for OpenSpec tooling.

## Architecturally Significant Requirement

ASR-1: the deliverable must not depend on opencode/OpenSpec. Emitting produced
changes into `openspec/changes/` + `development/manifests/` would bake
OpenSpec's contract into the output, coupling every produced wiki to a specific
toolchain. This decision resolves proposal Open Question #3, explicitly flagged
as a design-stage decision.

## Options Considered

### Option A — OpenSpec-shaped (`openspec/changes/` + `development/manifests/`)
*Pros:* matches this repo; drop-in for OpenSpec/opencode tooling.
*Cons:* couples produced artifacts to OpenSpec's contract; violates ASR-1; the
manifest split is scientia-internal machinery the produced pipeline does not
have.

### Option B — Configurable / pluggable layout
*Pros:* flexible.
*Cons:* premature generality; two code paths to test; no caller needs it yet.

### Option C — Flat `proposals/<change-id>/`, centralized in paths (chosen)
One subdir per change holding `proposal.md`, `grill.md`, `decisions-log.md`,
`specs/`, `design.md`, `adrs/`, `tasks.md`; `kg_pipeline.paths` is the only
place that knows the layout.
*Pros:* portable; self-contained; one layout authority; ADRs live under the
change (`adrs/`), avoiding a split decision log. **Chosen.**
*Cons:* not OpenSpec-drop-in; differs from scientia's self-hosting shape.

## Consequences

- Skills MUST resolve every path through `kg_pipeline.paths`; literal paths are
  forbidden, so a future layout change is one module edit.
- Produced ADRs live at `proposals/<change-id>/adrs/`, scoped to the change —
  avoiding the top-level `adr/` collision pitfall
  ([[concepts/intent-driven-schema]]).
- The produced layout is intentionally *not* the layout this repo uses to host
  the rewrite itself; the two are independent.

## Supersession

Supersedes nothing.
