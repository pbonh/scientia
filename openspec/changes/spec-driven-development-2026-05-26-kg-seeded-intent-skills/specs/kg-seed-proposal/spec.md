---
title: "Spec: KG-Seeded Proposal"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: kg-seed-proposal
created: 2026-05-26
updated: 2026-05-26
---

# Capability: KG-Seeded Proposal

The `seed-proposal` skill queries the wiki-as-KG and emits a proposal
pre-populated with four KG-sourced subsections, each citing the claims it
draws from with the claim's `effective` value shown inline. This is the
novel seam: where the KG holds high-confidence claims the proposal is
seeded automatically; where it is thin, the gap is surfaced as a
candidate problem rather than guessed.

## Glossary (inlined from manifest)

- **Proposal** — the why/what-changes document opening a change.
- **Capability** — a coherent slice of behaviour; one `spec.md` per
  capability.

## New Terms (introduced by this capability)

- **context-from-kg** — high-confidence claims relevant to the topic,
  fetched by entity-neighborhood traversal (threshold
  `proposal_seed_min`, default 0.70).
- **prior-art-from-kg** — claims sourced from a `kind: publication`
  source page (relaxed floor `prior_art_floor`, default 0.60).
- **candidate-problems** — gaps, contradictions, and low-confidence
  regions presented as problem statements (the inverted flow).
- **constraints-from-kg** — claims tagged `kind: constraint` or at the end
  of a `refines` chain from a constraints-root entity.

## Personas

- **Pipeline Author** — the LLM agent running `seed-proposal`.
- **Operator** — the human who supplies the optional topic hint and
  reviews the seeded proposal.

## Acceptance Criteria

- Each KG-sourced subsection cites its source claims as inline wiki-links
  with the claim's `effective` shown.
- `context-from-kg` includes only claims at or above `proposal_seed_min`
  and within two hops of the topic entity.
- `candidate-problems` surfaces low-confidence and contradicted claims and
  nearby question pages.
- When a subsection has no qualifying claims in `autonomous` mode, it is
  emitted with an explicit empty-note rather than omitted.

## Scenarios

### Scenario: Seed context from high-confidence neighborhood claims
```gherkin
Given a topic entity whose two-hop neighborhood contains a claim with effective 0.85, with proposal_seed_min 0.70
When the Pipeline Author runs seed-proposal for that topic
Then the proposal's context-from-kg section cites that claim with its effective value shown inline
```

### Scenario: Exclude a sub-threshold claim from context
```gherkin
Given a topic entity whose neighborhood contains only a claim with effective 0.55, with proposal_seed_min 0.70
When the Pipeline Author runs seed-proposal for that topic
Then that claim does not appear in the context-from-kg section
```

### Scenario: Surface a low-confidence region as a candidate problem
```gherkin
Given the topic neighborhood contains a claim with effective 0.32, below the low_confidence_floor
When the Pipeline Author runs seed-proposal for that topic
Then the proposal's candidate-problems section presents that claim as a problem statement citing its effective value
```

### Scenario: Broaden prior art with the relaxed publication floor
```gherkin
Given a claim with effective 0.63 sourced from a kind:publication source page, with prior_art_floor 0.60
When the Pipeline Author runs seed-proposal for the related topic
Then the proposal's prior-art-from-kg section cites that publication-sourced claim
```

### Scenario: Emit an empty subsection with an explicit note
```gherkin
Given no wiki claim qualifies for the constraints-from-kg subsection, with mode autonomous
When the Pipeline Author runs seed-proposal
Then the constraints-from-kg section is present and contains the note that the KG provided no high-confidence content
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
