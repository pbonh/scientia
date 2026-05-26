---
title: "Build the portable KG-seeded intent-driven Agent Skills pipeline"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
manifest_core: development/manifests/spec-driven-development/2026-05-26-kg-seeded-intent-skills/core.md
seed_document: kg-seeded-intent-driven-skills-design.md
created: 2026-05-26
---

# Proposal: Build the portable KG-seeded intent-driven Agent Skills pipeline

## Why

Scientia's central bet is that knowledge compounds in a wiki and that every
change is born from it (see [[concepts/llm-wiki-pattern]],
[[concepts/compounding-knowledge]]). Today that bet is realized in a bundle
hard-coupled to specific runtimes — Hermes for execution and OpenSpec for the
intent schema. The coupling makes the pipeline non-portable and ties its most
valuable idea — *knowledge-seeded intent* — to one stack.

This change rebuilds the wiki→intent half of scientia as a **portable,
runtime-agnostic Agent Skills set**, per the design brief
`kg-seeded-intent-driven-skills-design.md`. It composes two patterns the wiki
already documents: Karpathy's **LLM Wiki** ([[concepts/llm-wiki-pattern]]) and
**intent-driven development** ([[concepts/intent-driven-schema]],
[[concepts/artifact-dependency-graph]], [[concepts/gherkin]]). The novel
contribution lives in the **seam** between them: the wiki, treated as a
knowledge graph over typed pages, *seeds* the `proposal` and `grill` stages.
Where the KG holds high-confidence claims the pipeline automates decisions that
would normally need a human; where confidence is low it surfaces the gap as a
challenge rather than guessing.

To make "high vs low confidence" a deterministic gate rather than vibes, the
brief replaces the wiki's current *qualitative* per-page confidence with a
*quantitative* per-claim model: an LLM base score in `[0,1]`, augmented by a
pure-Python source-count multiplier and clamped by a contradiction floor to an
idempotently-recomputed `effective` score. This is a deliberate sharpening of
the [[concepts/compounding-knowledge]] principle — accumulation (more sources)
raises confidence; contradiction caps it.

The deliverable is portable across any Agent Skills–compliant runtime
([[concepts/agent-skills-format]], [[concepts/progressive-disclosure]]);
opencode + OpenSpec are the tested-against reference, not a dependency. Prior
art grounding this work, drawn from the manifest: [[summaries/openspec-docs]],
[[summaries/llm-wiki]], [[summaries/intent-driven-template]],
[[summaries/spec-driven-development-with-adr]],
[[summaries/agentskills-io-specification]], and [[summaries/c4model-com-home]]
for the design stage's C4 diagrams.

## What Changes

- Author **nine `SKILL.md` files** under `.agents/skills/` —
  `pipeline-controller`, `ingest-source`, `audit-wiki`, `seed-proposal`,
  `grill-proposal`, `write-specs`, `write-design`, `record-adr`,
  `generate-tasks` — each agentskills.io-compliant (kebab-case `name` matching
  its directory, `description` ≤1024 chars saying what + when) and under 500
  lines, with examples pushed to a sibling `references/`.
- Author the **`kg_pipeline/` Python package** (`wiki`, `confidence`,
  `templates`, `validators`, `paths`): pure-Python, stdlib + `pyyaml` (optional
  `networkx`), every public function docstring'd and golden-tested, **all
  deterministic operations idempotent**.
- Introduce the **typed-node KG model**: page types `entity` / `claim` /
  `source` / `question` (claim is the unit carrying confidence), with edge kinds
  encoded in the wiki-link alias slot (`mentions` default, `supports`,
  `contradicts`, `refines`).
- Introduce the **per-claim quantitative confidence model**:
  `effective = base × source_count_multiplier`, clamped to `contradiction_floor`
  when contradicted; rollups (`min` default, `mean`, `max`) for page and edge
  confidence.
- Implement **KG → proposal seeding** (`context-from-kg`, `prior-art-from-kg`,
  `candidate-problems`, `constraints-from-kg`) and **KG → grill interrogation**
  (open-questions, counter-claims, hidden-assumption challenges,
  failure-pattern warnings), each citing wiki claims with `effective` inline.
- Add **automation thresholds + human-in-loop modes** (`autonomous` vs
  `pause_and_ask`) in `references/config.yaml`, with `autonomous` logging picks
  to a `decisions-log.md` and `pause_and_ask` emitting
  `question-for-operator.md` and halting.
- Author **seven markdown templates + `config.yaml`** in `references/`
  (proposal, gherkin-spec, adr, c4, tasks, wiki-page, grill).
- Author **golden-file module tests** (`tests/modules/`) and **fixture-based
  skill evals** (`tests/skills/`, rubric-judged for the LLM-shaped skills).
- **BREAKING:** the portable rewrite becomes the **canonical** scientia
  wiki→intent implementation; the existing Hermes/OpenSpec-coupled skill bundle
  is **deprecated** in its favor. (Deprecation only — see Out of Scope for
  physical removal.)

## Out of Scope

- **Migrating this repo's existing wiki corpus.** The 224 concept + 83 entity
  pages stay in the current `concept/entity/summary` + qualitative-confidence
  scheme. The new typed-node / quantitative-confidence model applies only to
  wikis the rewrite *produces* (clean-room, confirmed at wiki-grill).
- **Physically deleting the existing scientia bundle.** This change deprecates
  it; removal/cutover is a follow-up change so the working bundle is not pulled
  out from under in-flight work.
- **Code generation or execution beyond `tasks.md`.** The brief's pipeline ends
  at task emission (brief §4).
- **Verification, test-running, or CI integration of the generated pipeline's
  output.** (The rewrite's own module tests/evals are in scope; running the
  *produced* tasks is not.)
- Graph DB, vector store, embeddings; multi-user collaboration semantics; a
  TypeScript twin (brief §4 non-goals).
- **The kanban-execution and ingest-back-to-wiki phases** — see Open Questions;
  the brief's loop is raw→tasks, narrower than scientia's current
  wiki→intent→kanban→ingest loop.

## Capabilities Introduced or Modified

Candidate decomposition for `scientia-intent-spec` (manifest `capabilities:`
is intentionally empty pending the spec stage):

- `kg-wiki-model` — typed-node wiki + on-demand traversal library
  (`kg_pipeline.wiki`).
- `kg-confidence` — per-claim base/multiplier/floor → effective + rollups
  (`kg_pipeline.confidence`).
- `kg-seed-proposal` — the four-layer KG→proposal seeding (`seed-proposal`).
- `kg-grill-proposal` — the four-section KG→grill interrogation
  (`grill-proposal`).
- `intent-artifact-generation` — `write-specs` → `write-design` →
  `record-adr` → `generate-tasks` and their templates.
- `wiki-maintenance` — `ingest-source` + `audit-wiki`.
- `pipeline-orchestration` — `pipeline-controller`, config, modes,
  decisions-log.
- `pipeline-tooling` — `templates` / `validators` / `paths` modules and the
  golden-file + eval test suites.

## Open Questions

- **Execution & ingest phases.** The brief deliberately ends at `tasks.md`, so
  this rewrite does *not* reproduce scientia's kanban-execution or
  ingest-synthesis phases. If "replace existing scientia" is meant to be total,
  those phases need their own portable design in a follow-up change; otherwise
  the rewrite is explicitly the *wiki→intent authoring* half only. **Flagged,
  not decided.**
- **Cutover.** Does a follow-up change physically remove the deprecated bundle,
  and on what trigger (new bundle passing its evals)?
- **Produced-pipeline layout.** The brief's `proposals/<change-id>/` layout
  differs from scientia's `openspec/changes/` + `development/manifests/`. Should
  the produced pipeline adopt the brief's flatter layout, or stay
  OpenSpec-shaped for the tested-against reference? (Design-stage decision.)
- **Confidence config defaults.** Brief fixes `source_count_curve`,
  `contradiction_floor 0.40`, `rollup min`, and the threshold table; confirm
  these at design time rather than re-deriving.

## References

- Manifest core: `development/manifests/spec-driven-development/2026-05-26-kg-seeded-intent-skills/core.md`
- Seed brief: `kg-seeded-intent-driven-skills-design.md`
- Relevant ADRs: none in-force (`wiki/decisions/` empty at bind time).
- Related concepts: [[concepts/llm-wiki-pattern]], [[concepts/compounding-knowledge]],
  [[concepts/wiki-ingest]], [[concepts/wiki-query]], [[concepts/intent-driven-schema]],
  [[concepts/artifact-dependency-graph]], [[concepts/gherkin]],
  [[concepts/progressive-rigor]], [[concepts/agent-skills-format]],
  [[concepts/progressive-disclosure]], [[concepts/skill-validation]],
  [[concepts/readable-skill]], [[concepts/c4-model]].
