---
title: "Design manifest — spec-driven-development/2026-05-26-kg-seeded-intent-skills"
type: manifest-design
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
scientia_schema: 1
wiki_snapshot: aaf532017e00fc0d7f0158079200c8a6103cc047
created: 2026-05-27
---

> **Snapshot note.** Design entered at `aaf5320`, after the spec stage
> committed all eight `specs/*/spec.md` and the wiki-grill annotations
> that left core's pin `dirty: true`. The working tree is clean at design
> entry, so this pin is exact (unlike core's approximate `53cdbb5`).

## 5 — In-Force ADRs

**Supersession walk:** `wiki/decisions/` does not exist and
`openspec/archive/` does not exist. No ADR has been authored or shipped in
this repository. The supersession graph therefore has **zero nodes, zero
`Supersedes:` chains, and zero orphans** — the walk completes trivially and
the design gate is satisfied.

**In-force ADRs touching this change scope: none.**

Consequence for `design.md`: every decision distilled at this stage is
**net-new**. There is no accepted ADR to honor, override, or mark
not-applicable. `scientia-intent-adr` will write the first ADRs in the
repo's history from the `## Decisions Distilled to ADRs` list, each with no
`Supersedes:` line. The `## In-Force ADR Treatment` section of `design.md`
records this empty state explicitly rather than omitting the heading.

## 6 — Architecturally Significant Requirements

No dedicated quality-attribute-scenario pages exist in the wiki at the
snapshot. The ASRs below are derived per
[[concepts/architecturally-significant-requirement]] from the eight specs'
Acceptance Criteria and the seed brief's Constraints & Non-Goals (§4). Each
is measurable and cross-cutting — it shapes structure rather than a single
component, and so anchors one or more of the distilled ADRs.

- **ASR-1 Portability (runtime-agnostic).** The deliverable runs on any
  Agent-Skills-compliant runtime with no dependency on opencode, MCP,
  Claude Code specifics, Hermes, or any SaaS (brief §4). *Verify:* the
  package and skills execute against the agentskills.io reference with
  opencode/OpenSpec present only as the tested-against reference.
- **ASR-2 Determinism & idempotency.** Every deterministic operation in
  `kg_pipeline` is idempotent (`write_page`, `recompute`, `recompute_all`,
  template render). *Verify:* a second run over unchanged inputs is
  byte-identical (kg-wiki-model + kg-confidence Acceptance Criteria).
- **ASR-3 On-disk-only state transfer.** The controller passes no values in
  memory between stages; every stage reads and writes files only
  (pipeline-orchestration). *Verify:* a stage can be re-run standalone from
  the prior stage's artifact alone.
- **ASR-4 Confidence as a deterministic automation gate.** The per-claim
  `[0,1]` `effective` score, not vibes, decides autonomous vs.
  pause-and-ask and what gets seeded/grilled (kg-confidence,
  kg-seed-proposal, kg-grill-proposal). *Verify:* given a base, source
  count, and contradiction state, `effective` is reproducible from the
  config'd curve and floor.
- **ASR-5 Validation gating.** The controller refuses to advance past a
  stage whose `kg_pipeline.validators` call returns a non-empty error list
  (pipeline-orchestration, pipeline-tooling). *Verify:* a malformed
  artifact halts the pipeline with the validator's error text.
- **ASR-6 Progressive-disclosure skill budget.** Each `SKILL.md` is
  agentskills.io-compliant (kebab-case `name` matching its directory,
  `description` ≤1024 chars stating what+when) and under 500 lines, with
  examples pushed to a sibling `references/` (brief §4,
  [[concepts/progressive-disclosure]], [[concepts/readable-skill]]).
  *Verify:* `validate_skill_md` passes and line count < 500.
- **ASR-7 Provenance / traceability.** Every KG-sourced subsection cites its
  claims as inline wiki-links with `effective` shown; every scenario carries
  `traces-grill` and every task `traces-spec` (kg-seed-proposal,
  kg-grill-proposal, intent-artifact-generation). *Verify:* a task is
  traceable to a scenario to a grill entry.
- **ASR-8 Non-destructive wiki.** `ingest-source` and `audit-wiki` never
  delete pages; contradictions append a bidirectional edge leaving the older
  claim's text intact; orphans are flagged not removed (wiki-maintenance).
  *Verify:* a flagged orphan remains on disk after audit.
- **ASR-9 Minimal dependency surface.** stdlib + `pyyaml`, with `networkx`
  optional and never altering results; templates render via
  `str.format_map`, no Jinja (brief §4, pipeline-tooling). *Verify:* the
  golden-file suite passes with `networkx` absent.

## 8 — Known Pitfalls (in-scope, relevant to the design choices)

Extracted from the `## Risks & Pitfalls` of manifest-core slice-2 concept
pages, filtered to pitfalls the design choices below must actively avoid.

- **Schema / frontmatter drift** ([[concepts/llm-wiki-pattern]],
  [[concepts/wiki-ingest]], [[concepts/agent-schema-document]]) — over many
  LLM ingests page formats and frontmatter conventions silently diverge.
  *Bears on:* the typed-node model, `validate_skill_md`, and the seven
  canonical templates.
- **Stale synthesis / contradiction blindness**
  ([[concepts/compounding-knowledge]], [[concepts/wiki-ingest]]) — an early
  claim is contradicted by a later source and the wiki entrenches stale
  information. *Bears on:* the contradiction floor, `audit-wiki`'s
  `recompute_all`, and the staleness trigger.
- **False contradictions** ([[concepts/wiki-lint]]) — the LLM flags a nuanced
  distinction as a contradiction; human review is essential before
  "resolving". *Bears on:* the rule that a `contradicts` edge is
  append-only and the older claim is never auto-rewritten.
- **Over-normalization / page sprawl** ([[concepts/llm-wiki-pattern]],
  [[concepts/wiki-ingest]]) — too many tiny duplicate claim pages. *Bears
  on:* the ingest dedupe step.
- **Filesystem as source of truth** ([[concepts/artifact-dependency-graph]])
  — manually deleting an artifact breaks the inferred graph without warning.
  *Bears on:* validator-gated stage advance and orphan-flag-not-delete.
- **Vague or overly-broad skill descriptions**
  ([[concepts/progressive-disclosure]]) — the agent fails to activate, or
  over-activates, a skill. *Bears on:* engineered what+when description
  seeds and `validate_skill_md`.
- **SKILL.md / template bloat** ([[concepts/progressive-disclosure]],
  [[concepts/readable-skill]], [[concepts/custom-workflow-schema]]) — oversized
  bodies inflate the context window every activation. *Bears on:* the
  500-line cap and short, structure-only templates.
- **Implementation leakage in Gherkin** ([[concepts/gherkin]]) — UI/DB
  actions leak into `Given`/`Then` instead of observable results. *Bears on:*
  the gherkin-spec template and `write-specs` discipline.
- **Conflating / drift between spec and ADR**
  ([[concepts/spec-adr-dual-representation]],
  [[concepts/durable-artifacts-vs-scaffolding]]) — rationale stuffed into
  specs, or behavior changes without a superseding ADR. *Bears on:*
  one-ADR-per-decision and ADR immutability.
- **Top-level `adr/` collisions** ([[concepts/intent-driven-schema]]) — a repo
  that keeps ADRs elsewhere risks a split decision log. *Bears on:* the
  produced layout placing ADRs under `proposals/<change-id>/adrs/`.
- **No runtime validation of skills** ([[concepts/readable-skill]]) — a
  readable skill has no compile-time check; errors surface at inference.
  *Bears on:* the golden-file module tests + rubric-judged skill evals.
