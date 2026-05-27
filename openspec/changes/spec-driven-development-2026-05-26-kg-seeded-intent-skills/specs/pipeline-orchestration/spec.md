---
title: "Spec: Pipeline Orchestration"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: pipeline-orchestration
created: 2026-05-26
updated: 2026-05-26
---

# Capability: Pipeline Orchestration

The `pipeline-controller` skill plus the `config.yaml`-driven automation
thresholds and human-in-loop modes. The controller resolves a change-id,
walks the stages in order, validates each stage's artifact before
advancing, and honors each stage's mode at low-confidence branches. State
transfer is by on-disk artifact only — the controller passes no values in
memory.

## Glossary (inlined from manifest)

- **Change** — a unit of intended work, identified `<tenant>/<date>-<slug>`.
- **Artifact-dependency graph** — the DAG ordering proposal → specs →
  design → adr → tasks.

## New Terms (introduced by this capability)

- **Mode** — per-stage policy: `autonomous` (pick safe default, log it,
  continue) or `pause_and_ask` (emit `question-for-operator.md`, halt).
- **decisions-log.md** — the per-change record of every autonomous
  low-confidence pick, citing the wiki claims and the threshold that
  fired.
- **question-for-operator.md** — the halt artifact a `pause_and_ask`
  stage emits; the controller waits until it is resolved.
- **Staleness** — the audit policy: if the wiki has not been audited
  within `audit.staleness_days`, the controller may run `audit-wiki`.

## Personas

- **Controller** — the `pipeline-controller` skill sequencing the stages.
- **Operator** — the human who resolves `question-for-operator.md` halts.

## Acceptance Criteria

- Advancement past a stage is gated on its artifact passing validation; a
  failing stage halts the pipeline with its validation errors reported, and
  cannot be advanced past by the controller alone.
- In `autonomous` mode a low-confidence pick is written to
  `decisions-log.md` with claim citations and the firing threshold.
- In `pause_and_ask` mode the controller halts on
  `question-for-operator.md` until it is resolved.
- Unrecognized `config.yaml` keys are surfaced rather than silently
  ignored.

## Scenarios

### Scenario: Refuse to advance past a stage whose artifact fails validation
```gherkin
Given a stage whose produced artifact fails its validator
When the Controller attempts to advance to the next stage
Then the Controller halts at the failing stage and reports the validation errors
```

### Scenario: Log an autonomous low-confidence pick
```gherkin
Given a stage in autonomous mode reaching a low-confidence branch
When the Controller takes the safe default at that branch
Then an entry is appended to decisions-log.md citing the wiki claims and the threshold that fired
```

### Scenario: Halt at a pause_and_ask branch
```gherkin
Given a stage in pause_and_ask mode reaching a low-confidence branch
When the Controller evaluates that branch
Then the Controller emits question-for-operator.md and does not advance until it is resolved
```

### Scenario: Trigger an audit when the wiki is stale
```gherkin
Given the wiki was last audited longer ago than audit.staleness_days, with audit_wiki mode autonomous
When the Controller runs between the ingest and seed-proposal stages
Then the Controller activates audit-wiki before seed-proposal
```

### Scenario: Surface an unrecognized config key
```gherkin
Given a config.yaml containing a key the controller does not recognize
When the Controller reads the configuration
Then the unrecognized key is surfaced to the Operator
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
