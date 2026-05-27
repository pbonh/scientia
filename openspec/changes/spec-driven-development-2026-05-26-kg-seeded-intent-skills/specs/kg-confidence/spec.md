---
title: "Spec: KG Confidence Model"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: kg-confidence
created: 2026-05-26
updated: 2026-05-26
---

# Capability: KG Confidence Model

The per-claim quantitative confidence model and its deterministic
recompute (`kg_pipeline.confidence`). A claim's confidence is an LLM base
score in `[0,1]`, augmented by a pure-Python source-count multiplier and
clamped by a contradiction floor to an `effective` score. Page and edge
confidence are rolled up on demand from the claims involved. All
operations are idempotent.

## Glossary (inlined from manifest)

- **"confidence"** *(false-cognate flag from manifest slice 4)* — in
  scientia's own wiki, confidence is a per-page *qualitative*
  high/medium/low field. This capability defines a per-claim
  *quantitative* `[0,1]` model. Same word, different mechanism.

## New Terms (introduced by this capability)

- **Base score** — the LLM rating recorded at ingest; never edited after
  creation.
- **Source-count multiplier** — `min(1.10, 1.00 + 0.04 * (n - 1))` over
  `n` distinct source pages; capped at +10%.
- **Contradiction floor** — a configurable ceiling (default `0.40`)
  applied when the claim has any `contradicts` edge.
- **Effective score** — the recomputed value:
  `min(floor, base × multiplier)` if contradicted, else `base × multiplier`.
- **Rollup** — page/edge confidence aggregated over claims; `min`
  (default), `mean`, or `max`.

## Personas

- **Pipeline Author** — the LLM agent that sets a base score at ingest
  and triggers recompute when sources or contradictions change.
- **Confidence Module** — `kg_pipeline.confidence`, the deterministic
  recompute engine.

## Acceptance Criteria

- `effective` is always the recomputed value; the agent never hand-edits
  it.
- The source-count multiplier is applied and capped per the configured
  curve.
- A contradicted claim's `effective` is clamped to at most the floor,
  regardless of multiplier output.
- `recompute` is idempotent: a second recompute over unchanged inputs
  changes nothing.
- Page rollup defaults to the minimum effective over the page's claims.

## Scenarios

### Scenario: Accumulation raises effective via the source-count multiplier
```gherkin
Given a claim with base 0.80, no contradiction, and two distinct sources
When the Confidence Module recomputes the claim
Then the claim's effective score is 0.832
```

### Scenario: The source-count multiplier caps at plus ten percent
```gherkin
Given a claim with base 0.80, no contradiction, and ten distinct sources
When the Confidence Module recomputes the claim
Then the claim's effective score is 0.88
```

### Scenario: A contradiction clamps effective to the floor
```gherkin
Given a claim with base 0.90 and an incoming contradicts edge, with floor 0.40
When the Confidence Module recomputes the claim
Then the claim's effective score is 0.40
```

### Scenario: Recompute is idempotent over unchanged inputs
```gherkin
Given a claim whose effective score was just recomputed
When the Confidence Module recomputes the same claim again
Then the claim's frontmatter is unchanged
```

### Scenario: Page confidence rolls up as the weakest claim
```gherkin
Given a page aggregating claims with effective scores 0.82, 0.61, and 0.90, with rollup set to min
When the Pipeline Author requests the page's rolled-up confidence
Then the returned value is 0.61
```

### Scenario: The base score is preserved across recompute
```gherkin
Given a claim whose base score is 0.78
When the Confidence Module recomputes the claim after a new source is added
Then the claim's base score remains 0.78
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
