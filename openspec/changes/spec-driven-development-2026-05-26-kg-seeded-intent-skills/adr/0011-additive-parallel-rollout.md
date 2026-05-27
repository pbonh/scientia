---
title: "ADR-0011: Roll out the portable rewrite as an additive parallel path, deprecating phase-by-phase"
adr_id: ADR-0011
status: accepted
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Delivery continuity: the proven Hermes/OpenSpec execution+ingest path stays fully supported while the portable authoring half (ASR-1) is built and mastered first."
shared_types: []
tags: [spec-driven-development, rollout, deprecation, scope]
created: 2026-05-27
---

# ADR-0011: Roll out the portable rewrite as an additive parallel path, deprecating phase-by-phase

## Y-Statement

**In the context of** replacing scientia's wiki→intent→kanban→ingest loop with a
portable, runtime-agnostic Agent Skills implementation, where *this* change
delivers only the wiki→intent authoring half (raw→tasks),
**facing** the choice between declaring the rewrite canonical and deprecating
the existing Hermes/OpenSpec bundle now versus introducing it alongside the
proven bundle,
**we decided for** shipping the rewrite as an **additive, parallel** authoring
path practiced standalone to `tasks.md`, keeping the existing bundle fully
supported, with **total replacement as the eventual goal** sequenced
authoring-first and **deprecation/removal proceeding phase-by-phase** as each
portable replacement lands and passes its evals,
**and against** declaring the rewrite canonical and deprecating the whole bundle
now (a half implementation cannot replace the full loop), a single big-bang
cutover, or treating the rewrite as a permanent authoring-only fork,
**to achieve** delivery continuity (the working loop is never pulled out from
under in-flight work), incremental risk, and time to master the authoring craft
before porting execution and ingest,
**accepting** that during the interim the portable `proposals/<change-id>/`
output is not consumable by the existing OpenSpec-shaped execution loop
(authoring is exercised standalone), that two authoring paths coexist, and that
the overall migration spans multiple future changes with no committed timeline.

## Architecturally Significant Requirement

The rewrite's purpose is ASR-1 portability, but it lands **incrementally**: this
change is only the authoring half. Declaring it canonical and deprecating a
complete, working wiki→intent→kanban→ingest loop in favor of a raw→tasks half
would orphan execution and ingest with no replacement. The significant
requirement is **delivery continuity**: the proven path must stay available and
unbroken while the portable halves are built, mastered, and proven one at a
time. This decision was settled in the 2026-05-27 grill (scope = total
replacement eventual; rollout = additive parallel, phase-by-phase deprecation).

## Options Considered

### Option A — Declare canonical now, deprecate the whole bundle
*Pros:* strong directional signal; one canonical path.
*Cons:* deprecates a complete loop in favor of a half; orphans execution+ingest
with no portable successor; misleads ("deprecated but it's the only runner").
Rejected in grill.

### Option B — Permanent authoring-only fork
Keep the portable path authoring-only forever; execution/ingest stay on
Hermes/OpenSpec indefinitely.
*Pros:* clean, bounded scope.
*Cons:* abandons the goal of a fully portable scientia; entrenches the runtime
coupling the rewrite exists to remove.

### Option C — Additive parallel path, total replacement eventual, phase-by-phase deprecation (chosen)
Ship authoring beside the proven bundle; deprecate/remove each piece only as its
portable replacement lands and passes evals.
*Pros:* truthful current-state labeling; delivery continuity; incremental risk;
defers the total-vs-permanent commitment until evals prove the path. **Chosen.**
*Cons:* interim format seam (produced layout ≠ OpenSpec execution input); two
coexisting paths; multi-change migration with an uncommitted timeline.

## Consequences

- This change deprecates **nothing**; the `**BREAKING:**` framing was removed
  from `proposal.md` in favor of the additive-parallel statement.
- The flat `proposals/<change-id>/` produced layout (ADR-0005) stands; the
  interim non-interop with the OpenSpec-shaped execution loop is accepted, since
  authoring is practiced standalone (the rewrite ends at `tasks.md`).
- Cutover is not a single event: each future change ports one phase (execution,
  then ingest) and may deprecate the bundle piece it replaces, gated on that
  piece passing its evals.
- A follow-up change is required to port kanban-execution and ingest-synthesis
  to portable skills before the existing bundle can be fully removed.

## Supersession

Supersedes nothing.
