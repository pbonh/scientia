---
title: "Core manifest — spec-driven-development/2026-05-26-kg-seeded-intent-skills"
type: manifest-core
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
description: "A portable, clean-room rewrite of scientia as a runtime-agnostic nine-SKILL.md set plus a kg_pipeline Python package, whose novel contribution is seeding the intent phase's proposal and grill stages directly from the wiki treated as a knowledge graph. Per-claim quantitative confidence gates automation (autonomous vs pause_and_ask)."
capabilities: []   # decomposition deferred to scientia-intent-spec; candidate seams listed in §1
scientia_schema: 1
wiki_snapshot: 53cdbb59c3c30d84c8ceaf7fe8e4db17b98457ff
dirty: true        # bound with --allow-dirty; working tree had uncommitted wiki-grill annotations
bundle_version: "0.1.0"
created: 2026-05-26
seed_document: kg-seeded-intent-driven-skills-design.md
---

> **Bind note.** Pinned at `53cdbb5` with `dirty: true`: the working tree
> carried two uncommitted wiki-grill annotations
> (`contexts/spec-driven-development.md` Open-Questions section,
> `contexts/knowledge-base-and-wiki.md` confidence false-cognate) that are
> *not* in the pinned commit. Downstream stages should treat the pin as
> approximate; re-bind to `core-2.md` if those annotations are committed.

## 1 — Domain Framing

**Tenant context:** [[contexts/spec-driven-development]] — *Core
subdomain.* The OpenSpec-style intent phase: expressing *what changes* as
versioned, delta-based specifications with executable Gherkin scenarios,
walked through an artifact-dependency graph from proposal to archive. It
owns the spec vocabulary (*capability, scenario, change, delta, archive*)
and the intent-driven schema that augments OpenSpec with manifest-carried
wiki knowledge. Shares the **intent-driven-schema** kernel with
[[contexts/architecture-decision-records]] (see
[[context-maps/intent-shared-kernel]]).

**This change** is a portable, **clean-room rewrite of scientia** itself
— the intent phase re-expressed as a runtime-agnostic skill set. It draws
on two adjacent core contexts and sits in the scientia core loop
(see [[context-maps/scientia-pipeline]]):

- [[contexts/knowledge-base-and-wiki]] — the wiki/KG that *seeds* the
  proposal and grill stages (the novel seam).
- [[contexts/agent-skills-standard]] — the deliverable is a set of
  `SKILL.md` artifacts; the standard is the substrate the rewrite is
  authored in.

**Resolved framing (from `scientia-wiki-grill`, 2026-05-26):**

1. **Portable rewrite.** The rewrite's vocabulary *supersedes* the
   current model **within the artifacts it produces**. Hermes and
   OpenSpec are *tested-against, not required* — no hard runtime
   dependency.
2. **Clean-room scope.** This repo's existing 224-page wiki corpus is
   **not** migrated to the new typed-node / quantitative-confidence
   scheme. The new model applies only to wikis the rewrite produces.

**Candidate capability seams** (for `scientia-intent-spec` to decompose;
not yet committed): KG wiki model (typed `entity/claim/source/question`
nodes + alias-encoded edges + per-claim confidence); KG → proposal
seeding (`seed-proposal`); KG → grill interrogation (`grill-proposal`);
intent-artifact generation (`write-specs` → `write-design` → `record-adr`
→ `generate-tasks`); pipeline orchestration (`pipeline-controller`); and
the `ingest-source` / `audit-wiki` wiki-maintenance pair.

## 2 — In-Scope Concepts

### Tenant — spec-driven-development

- [[concepts/delta-spec]] — A specification that describes changes
  relative to an existing baseline rather than restating the whole spec.
- [[concepts/fluid-workflow]] — Work modeled as discrete *actions* takeable
  in any order, rather than a linear lock-step sequence of *phases*.
- [[concepts/artifact-dependency-graph]] — A DAG whose nodes are project
  artifacts (`proposal.md`, `spec.md`, `design.md`, `tasks.md`) and whose
  edges are creation dependencies (B requires A first).
- [[concepts/progressive-rigor]] — Specification depth/formality scales
  with a change's risk, scope, and cross-team impact.
- [[concepts/opsx-workflow]] — OPSX, the modern schema-driven workflow
  system for OpenSpec.
- [[concepts/coordination-workspace]] — A durable planning home in OpenSpec
  linking multiple repos/folders under stable names for cross-repo changes.
- [[concepts/custom-workflow-schema]] — A user-defined YAML config declaring
  artifact types, their dependencies, and their AI-generation templates.
- [[concepts/brownfield-first]] — Prioritizing tools/practices for evolving
  existing codebases over greenfield-from-scratch description.
- [[concepts/spec-driven-with-adr-schema]] — A custom OpenSpec schema that
  inserts a dedicated, *durable* ADR stage into proposal-to-tasks flow.
- [[concepts/durable-artifacts-vs-scaffolding]] — The distinction between
  artifacts that persist as living documentation and scaffolding discarded
  once a change archives.
- [[concepts/spec-adr-dual-representation]] — Living documentation needs two
  complementary artifacts answering different questions (what vs. why).
- [[concepts/intent-driven-schema]] — A custom OpenSpec schema capturing
  intent, observable behaviour, technical design, and durable decisions
  *before* implementation. *(shared kernel — [[context-maps/intent-shared-kernel]])*
- [[concepts/openspec-git-discipline]] — Rules governing when OpenSpec
  lifecycle phases may run relative to git state.
- [[concepts/gherkin]] — A structured, near-natural-language notation for
  describing behaviour as *executable examples*.

### Cross-context — knowledge-base-and-wiki (the KG-seeding seam)

- [[concepts/llm-wiki-pattern]] — An LLM agent incrementally builds and
  maintains a structured, interlinked markdown KB between user and raw
  sources. *(the pattern the rewrite generalizes)*
- [[concepts/compounding-knowledge]] — Information should accumulate and
  strengthen over time rather than be re-derived per query.
- [[concepts/wiki-ingest]] — The operation of adding a new raw source to an
  LLM wiki. *(rewrite's `ingest-source`)*
- [[concepts/wiki-query]] — The operation of asking questions against an LLM
  wiki. *(the traversal the seeding stages rely on)*
- [[concepts/wiki-lint]] — The periodic health-check operation on an LLM
  wiki. *(rewrite's `audit-wiki`)*
- [[concepts/agent-schema-document]] — A config file telling an agent how a
  wiki is structured and what ingest/query/maintain workflows to use.

### Cross-context — agent-skills-standard (the deliverable substrate)

- [[concepts/agent-skills-format]] — A lightweight, file-based spec for
  packaging knowledge/workflows so agents discover, load, execute on demand.
- [[concepts/progressive-disclosure]] — Three-stage loading by which
  Agent-Skills agents consume skills. *(near-cognate of progressive-rigor)*
- [[concepts/skill-validation]] — Checking that a skills folder conforms to
  the spec (layout, frontmatter, naming, references).
- [[concepts/readable-skill]] — A structured natural-language document that
  serves as an executable specification for an LLM orchestrator.

## 3 — In-Scope Entities

- [[entities/openspec]] — Open-source specification and planning framework
  for AI-assisted software development. *(tested-against, not required)*
- [[entities/fission-ai]] — The organization that created and maintains
  OpenSpec.
- [[entities/intent-driven-dev]] — The project/org behind intent-driven.dev
  and the `intent-driven-dev` GitHub org.
- [[entities/openspec-schemas]] — Public MIT repo of OpenSpec workflow
  schemas maintained by Intent-Driven Dev.
- [[entities/hari-krishnan]] — Author of the "ADRs with Spec-Driven
  Development using OpenSpec" post; argues for durable ADRs.
- [[entities/intent-driven-template]] — Public GitHub template repo from
  Intent-Driven Dev.
- [[entities/andrej-karpathy]] — Author of the LLM Wiki pattern the rewrite
  generalizes. *(cross-context: knowledge-base-and-wiki)*
- [[entities/agentskills-io]] — Website/community hub for the Agent Skills
  open standard. *(cross-context: agent-skills-standard)*
- [[entities/skills-ref]] — Reference validation CLI for the Agent Skills
  standard. *(cross-context; relevant to the brief's skill-validation tests)*

## 4 — Ubiquitous Language

Verbatim from [[contexts/spec-driven-development]] `## Ubiquitous Language`:

- **Change** — a unit of intended work, identified `<tenant>/<date>-<slug>`,
  living under `openspec/changes/<id>/` until archived.
- **Capability** — a coherent slice of behaviour; one `spec.md` per capability.
- **Delta spec** — a specification expressed as a *change* against an
  existing baseline rather than a from-scratch document (brownfield-first).
- **Scenario** — a Gherkin Given/When/Then example; one observable `When`
  per scenario.
- **Proposal** — the why/what-changes document opening a change.
- **Archive** — moving a completed change out of the active set, folding
  its deltas into the baseline.
- **Artifact-dependency graph** — the DAG ordering proposal → specs →
  design → adr → tasks.
- **Progressive rigor** — applying heavier specification only where risk
  warrants it.
- **Intent-driven schema** — the scientia OpenSpec schema that augments each
  stage with the wiki manifest (shared with ADR context).

### False-cognate flags (carry downstream — do not conflate)

- **"confidence"** — In *this* wiki it is a per-page *qualitative*
  high/medium/low field. The change *introduces* a per-claim *quantitative*
  `[0,1]` model (base × source-count multiplier, clamped by a contradiction
  floor → `effective`) used to gate automation. Same word, different
  mechanism. The quantitative model belongs to the new spec's vocabulary,
  not this glossary.
- **"grill"** — The change's `grill-proposal` *auto-generates* a `grill.md`
  from KG queries; scientia's [[scientia-grill]] is an *interactive human
  interview*. Near-cognates; the rewrite's is the automated one.
- **"scenario" / "delta" / "archive" / "design"** — per the tenant context's
  False-Cognates section (Gherkin example vs Ansible play; spec change-set
  vs numeric diff; OpenSpec lifecycle vs kanban state; pipeline stage vs
  code-structuring craft).
- **"progressive disclosure" (skill loading) vs "progressive rigor"
  (specifying)** — both ration effort/context but are distinct concepts;
  not to be merged.

## 7 — Related Prior Work

Summaries whose `## Relevant Concepts` overlap the in-scope set:

- [[summaries/openspec-docs]] — **OpenSpec Documentation**: the specification
  and planning framework for AI-assisted development by Fission AI.
  *(8-concept overlap; the rewrite's intent-phase reference.)*
- [[summaries/llm-wiki]] — **LLM Wiki**: Karpathy's pattern for LLM-built
  personal knowledge bases. *(6-concept overlap; the KG the rewrite seeds from.)*
- [[summaries/intent-driven-template]] — **Intent-Driven Template**: the
  public template repo pairing OpenSpec with durable ADRs.
- [[summaries/spec-driven-development-with-adr]] — **ADRs with Spec-Driven
  Development using OpenSpec** (Hari Krishnan): keeping architectural
  rationale durable outside the change folder.
- [[summaries/openspec-schemas]] — **OpenSpec Schemas Repository**: the
  MIT-licensed workflow-schema repo.
- [[summaries/agentskills-io-specification]] — **Agent Skills
  Specification**: the formal folder-based skill format the deliverable
  must conform to.
- [[summaries/c4model-com-home]] — **The C4 Model** (Simon Brown): the
  diagramming approach the brief's `write-design` stage emits.
- [[summaries/agentskills-io-home]] — **Agent Skills Overview**: the open
  standard's home/documentation hub.

---

*Slices 5/6/8 (in-force ADRs, ASRs, pitfalls) are computed at
`scientia-intent-design` time. Slice 9 (tradeoffs) at
`scientia-intent-tasks` time. Slice 10 (addenda) lazily as the live-query
escape hatch is used.*
