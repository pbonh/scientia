---
title: "Spec: Intent Artifact Generation"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: intent-artifact-generation
created: 2026-05-26
updated: 2026-05-26
---

# Capability: Intent Artifact Generation

The downstream authoring stages — `write-specs`, `write-design`,
`record-adr`, `generate-tasks` — that turn an addressed proposal/grill
into Gherkin specs, a C4 design, ADRs, and a tasks checklist. Each stage
consumes the prior artifact and preserves traceability links so a task
can be traced back to the scenario and the scenario to the grill entry.

## Glossary (inlined from manifest)

- **Scenario** — a Gherkin Given/When/Then example; one observable `When`
  per scenario.
- **Artifact-dependency graph** — the DAG ordering proposal → specs →
  design → adr → tasks.
- **Progressive rigor** — applying heavier specification only where risk
  warrants it.

## New Terms (introduced by this capability)

- **traces-grill** — an HTML comment `<!-- traces-grill: <entry-id> -->`
  linking a scenario back to the grill entry it satisfies.
- **traces-spec** — an HTML comment `<!-- traces-spec: <scenario-id> -->`
  linking a task back to the scenario it satisfies.
- **C4Container** — a mermaid C4 container diagram required in `design.md`.

## Personas

- **Pipeline Author** — the LLM agent running an artifact-generation
  stage.
- **Operator** — the human consulted at `pause_and_ask` design/ADR
  branches.

## Acceptance Criteria

- `write-specs` refuses to run while any grill entry is unaddressed.
- Each grill-derived requirement is traceable to a scenario via
  `traces-grill`.
- `design.md` contains at least one mermaid `C4Container` (or its text
  equivalent).
- `record-adr` writes one ADR per decision and never combines decisions.
- Each generated task references its satisfying scenario via
  `traces-spec`.

## Scenarios

### Scenario: Refuse spec authoring while a grill entry is unaddressed
```gherkin
Given a grill.md with one entry whose frontmatter is addressed:false
When the Pipeline Author runs write-specs
Then write-specs refuses and reports the unaddressed grill entry
```

### Scenario: Trace a scenario back to its grill entry
```gherkin
Given an addressed grill entry that became a requirement
When the Pipeline Author authors the scenario satisfying that requirement
Then the scenario carries a traces-grill comment naming that entry's id
```

### Scenario: Require a C4 container diagram in the design
```gherkin
Given a set of authored Gherkin specs for the change
When the Pipeline Author runs write-design
Then design.md contains at least one mermaid C4Container diagram
```

### Scenario: Record one ADR per decision
```gherkin
Given a design.md that contains two distinct durable architectural decisions
When the Pipeline Author runs record-adr
Then two separate ADR files are written, one per decision
```

### Scenario: Present a high-confidence decision as recommended-accept
```gherkin
Given a design decision whose inherited confidence is 0.93, with adr_recommend_accept_min 0.90
When the Pipeline Author runs record-adr in pause_and_ask mode
Then the Operator is prompted with the pre-drafted ADR marked recommended-accept, and no ADR is recorded until the Operator confirms
```

### Scenario: Trace a task back to its scenario
```gherkin
Given a design.md and its ADRs for the change
When the Pipeline Author runs generate-tasks
Then each task in tasks.md carries a traces-spec comment naming the scenario it satisfies
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
