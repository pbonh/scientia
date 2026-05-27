---
title: "Spec: Wiki Maintenance"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: wiki-maintenance
created: 2026-05-26
updated: 2026-05-26
---

# Capability: Wiki Maintenance

The `ingest-source` and `audit-wiki` skills that build and curate the KG.
`ingest-source` turns one raw source into Source/Entity/Claim/Question
pages with an LLM base confidence and inline neighbor contradiction
checks. `audit-wiki` periodically recomputes confidence across the wiki
and batch-scans for cross-page contradictions. Neither skill deletes
pages.

## Glossary (inlined from manifest)

- **Ingest** *(false-cognate flag)* — here, raw-source → KG page. Distinct
  from the pipeline ingest phase (handoff → wiki) elsewhere in scientia.
- **Compounding knowledge** — each ingested source makes future ingests
  and queries richer.

## New Terms (introduced by this capability)

- **Dedupe** — when a candidate claim closely matches an existing claim,
  the existing page is updated (new source appended) instead of creating a
  duplicate.
- **Contradiction edge** — a bidirectional `contradicts` link added when
  a new claim conflicts with an immediate neighbor; the older claim is
  never rewritten.
- **Orphan** — a page no other page references; flagged, never deleted.

## Personas

- **Pipeline Author** — the LLM agent running `ingest-source` or
  `audit-wiki`.
- **Operator** — the human who drops a raw source and reviews the audit
  report.

## Acceptance Criteria

- Ingesting a source registers a source page and sets a base score on each
  new claim, never an `effective` value directly.
- A near-duplicate claim updates the existing page rather than creating a
  new one.
- A detected contradiction adds a bidirectional `contradicts` edge and
  leaves the older claim's text intact.
- `audit-wiki` recomputes all claims and flags orphans without deleting
  them.

## Scenarios

### Scenario: Ingest a source into typed KG pages
```gherkin
Given a raw source file containing one novel assertion
When the Pipeline Author runs ingest-source on that file
Then a source page is registered and a new claim page is created with an LLM base score set
```

### Scenario: Deduplicate against an existing claim
```gherkin
Given a raw source asserting a claim that closely matches an existing claim page
When the Pipeline Author runs ingest-source on that source
Then the existing claim page gains the new source in its sources list and no duplicate claim page is created
```

### Scenario: Record a contradiction without rewriting the older claim
```gherkin
Given a candidate claim that contradicts an immediate neighbor claim
When the Pipeline Author ingests the candidate claim
Then a contradicts edge is added in both directions and the older claim's text is unchanged
```

### Scenario: Audit flags an orphan without deleting it
```gherkin
Given a wiki containing a claim page no other page references
When the Pipeline Author runs audit-wiki
Then the audit report flags the orphan and the orphan page remains on disk
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
