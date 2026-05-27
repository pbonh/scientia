---
title: "Spec-Driven Development"
type: context
tags: [context, bounded-context, core]
created: 2026-05-24
updated: 2026-05-26
confidence: high
---

## Boundary

The OpenSpec-style intent phase: expressing *what changes* as
versioned, delta-based specifications with executable Gherkin scenarios,
walked through an artifact-dependency graph from proposal to archive.
This context owns the spec vocabulary (*capability, scenario, change,
delta, archive*) and the intent-driven schema that augments OpenSpec
with manifest-carried wiki knowledge. It shares the
**intent-driven-schema** kernel with
[[contexts/architecture-decision-records]] but keeps its own language
for *specifying behaviour* distinct from *recording decisions*.

## Subdomain Classification

**Core.** This is the intent phase of the pipeline — the bridge between
wiki knowledge and durable kanban work. Scientia's whole proposition is
that specs are derived from a pinned wiki manifest and verified before
execution. Differentiating, heavily invested.

## In-Scope Concepts

- [[concepts/delta-spec]]
- [[concepts/fluid-workflow]]
- [[concepts/artifact-dependency-graph]]
- [[concepts/progressive-rigor]]
- [[concepts/opsx-workflow]]
- [[concepts/coordination-workspace]]
- [[concepts/custom-workflow-schema]]
- [[concepts/brownfield-first]]
- [[concepts/spec-driven-with-adr-schema]]
- [[concepts/durable-artifacts-vs-scaffolding]]
- [[concepts/spec-adr-dual-representation]]
- [[concepts/intent-driven-schema]] *(shared kernel — see [[context-maps/intent-shared-kernel]])*
- [[concepts/openspec-git-discipline]]
- [[concepts/gherkin]]

## In-Scope Entities

- [[entities/openspec]]
- [[entities/fission-ai]]
- [[entities/intent-driven-dev]]
- [[entities/openspec-schemas]]
- [[entities/hari-krishnan]]
- [[entities/intent-driven-template]]

## Ubiquitous Language (Glossary)

- **Change** — a unit of intended work, identified `<tenant>/<date>-<slug>`,
  living under `openspec/changes/<id>/` until archived.
- **Capability** — a coherent slice of behaviour; one `spec.md` per
  capability.
- **Delta spec** — a specification expressed as a *change* against an
  existing baseline rather than a from-scratch document (brownfield-first).
- **Scenario** — a Gherkin Given/When/Then example; one observable
  `When` per scenario.
- **Proposal** — the why/what-changes document opening a change.
- **Archive** — moving a completed change out of the active set,
  folding its deltas into the baseline.
- **Artifact-dependency graph** — the DAG ordering proposal → specs →
  design → adr → tasks.
- **Progressive rigor** — applying heavier specification only where risk
  warrants it.
- **Intent-driven schema** — the scientia OpenSpec schema that augments
  each stage with the wiki manifest (shared with ADR context).

## False Cognates with Adjacent Contexts

- **"scenario"** here is a Gherkin behaviour example; in
  [[contexts/infrastructure-automation]] Ansible has no "scenario" but
  *playbook plays* fill a similar narrative role — not the same artifact.
- **"delta"** here is a spec change-set; unrelated to any numeric/diff
  sense elsewhere.
- **"archive"** here is an OpenSpec lifecycle transition; in
  [[contexts/autonomous-agent-orchestration]] *archive* is a kanban task
  state. The scientia ingest phase performs *both* atomically — see
  [[context-maps/scientia-pipeline]].
- **"design"** here names a pipeline stage (`design.md`); in
  [[contexts/software-design-principles]] *design* is the craft of
  structuring code. See [[concepts/c4-model]] which bridges them.

## Open Questions / In-Flight Changes

- **Change `spec-driven-development/2026-05-26-kg-seeded-intent-skills`**
  (in flight) — a portable, *clean-room* rewrite of scientia as a
  runtime-agnostic nine-`SKILL.md` set plus a `kg_pipeline` Python
  package. Its novel contribution is seeding the intent phase's
  `proposal` and `grill` stages directly from the wiki treated as a
  knowledge graph. Resolved framing (from wiki-grill):
  - The rewrite's vocabulary **supersedes** the current model *within
    the artifacts it produces*; it does not depend on Hermes/OpenSpec
    (those are tested-against, not required).
  - **Clean-room scope:** this repo's existing wiki corpus is *not*
    migrated to the new typed-node / quantitative-confidence scheme.
    The new model applies only to wikis the rewrite produces.
- Deferred to the proposal/design stages (not blocking the bind):
  the exact per-claim confidence formula and rollup choice; the
  `autonomous` vs `pause_and_ask` automation thresholds; and the
  precise semantics of the KG → proposal/grill seeding seam.

## Sources

- [[summaries/openspec-docs]]
- [[summaries/openspec-schemas]]
- [[summaries/intent-driven-template]]
- [[summaries/spec-driven-development-with-adr]]
