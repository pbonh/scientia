---
title: "Spec: KG-Seeded Grill"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: kg-grill-proposal
created: 2026-05-26
updated: 2026-05-26
---

# Capability: KG-Seeded Grill

The `grill-proposal` skill reads a proposal and emits `grill.md` with four
sections, each interrogating the proposal against the KG. Every entry
cites the wiki page(s) it draws from with `effective` shown inline. The
proposal cannot advance until every grill entry is addressed.

## Glossary (inlined from manifest)

- **"grill"** *(false-cognate flag from manifest slice 4)* — this
  capability's grill *auto-generates* `grill.md` from KG queries; it is
  not the interactive human interview that scientia's interactive grill
  performs. This spec governs the automated one.

## New Terms (introduced by this capability)

- **Counter-claim** — a wiki claim with `effective >= grill_dismiss_min`
  (default 0.85) that contradicts or stands in tension with a proposal
  assertion.
- **Hidden-assumption challenge** — a wiki claim a proposal implicitly
  relies on whose `effective < grill_dismiss_min`; the highest-leverage
  category.
- **Addressed** — an entry's frontmatter flag (`addressed: true`) the
  proposer sets once the entry is resolved.

## Personas

- **Pipeline Author** — the LLM agent running `grill-proposal`.
- **Proposer** — the author of the proposal under interrogation, who
  resolves each grill entry.

## Acceptance Criteria

- Each grill entry cites its source wiki page(s) with `effective` inline.
- A hidden-assumption challenge is raised for every implicitly-relied-upon
  claim below `grill_dismiss_min`.
- A high-confidence contradicting claim becomes a counter-claim entry.
- The failure-pattern section may be empty when no relevant post-mortem
  source exists.

## Scenarios

### Scenario: Surface a low-confidence dependency as a hidden-assumption challenge
```gherkin
Given a proposal assertion that implicitly relies on a wiki claim with effective 0.42, with grill_dismiss_min 0.85
When the Pipeline Author runs grill-proposal on that proposal
Then grill.md contains a hidden-assumption challenge citing that claim and its effective value
```

### Scenario: Raise a counter-claim from a high-confidence contradiction
```gherkin
Given a wiki claim with effective 0.88 that contradicts a proposal assertion, with grill_dismiss_min 0.85
When the Pipeline Author runs grill-proposal on that proposal
Then grill.md lists that claim as a counter-claim with its effective value
```

### Scenario: Leave the failure-pattern section empty when no post-mortem applies
```gherkin
Given no source page tagged kind:post-mortem is relevant to the proposal topic
When the Pipeline Author runs grill-proposal on the proposal
Then the failure-pattern-warnings section is present and explicitly empty
```

### Scenario: Block advancement while a grill entry is unaddressed
```gherkin
Given a grill.md whose entries are not all marked addressed:true
When the Proposer attempts to advance the change to the spec stage
Then advancement is refused with the count of unaddressed entries
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
