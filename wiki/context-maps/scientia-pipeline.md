---
title: "Scientia Pipeline (Core Loop)"
type: context-map
tags: [context-map]
contexts: [knowledge-base-and-wiki, spec-driven-development, architecture-decision-records, autonomous-agent-orchestration, agent-skills-standard]
created: 2026-05-24
updated: 2026-05-24
---

## Relationships

The five core contexts form scientia's closed loop:

```
[Knowledge Base & Wiki] ──manifest──► [Spec-Driven Development]
                                            │
                                  (intent-driven-schema)
                                            ▼
                              [Architecture Decision Records]
                                            │
                                    verified change
                                            ▼
                          [Autonomous Agent Orchestration]
                                            │
                                  handoffs (ingest)
                                            ▼
                              back to [Knowledge Base & Wiki]
```

- **Knowledge Base & Wiki → Spec-Driven Development** —
  *Customer/Supplier (upstream/downstream).* The wiki is upstream; the
  bound manifest (`core.md`, pinned at a wiki git rev) is the published
  contract the intent phase conforms to.
- **Spec-Driven Development ↔ Architecture Decision Records** —
  *Shared Kernel.* They co-own [[concepts/intent-driven-schema]]. Detail
  in [[context-maps/intent-shared-kernel]].
- **ADR → Autonomous Agent Orchestration** — *Customer/Supplier.* An
  ADR's *status* maps to a kanban *collaboration pattern* via
  `emit.default_pattern_by_adr_status` in `development/config.yaml`
  (accepted→P2-pipeline, proposed→P5-human-in-loop, deprecated/
  superseded→refuse).
- **Autonomous Agent Orchestration → Knowledge Base & Wiki** —
  *Customer/Supplier (ingest).* Completed task *handoffs* are folded
  back into wiki pages, closing the loop and enriching the next change.
- **Agent Skills Standard → all four** — *Conformist / shared substrate.*
  Every phase above is delivered as an agent skill conforming to the
  standard; the standard is upstream of all pipeline phases.

## False Cognates

- **"archive"** — Spec-Driven (OpenSpec change archive) vs Orchestration
  (kanban task archive). The ingest phase performs *both atomically*
  (`scientia-ingest-archive`), which is why the word recurs.
- **"status"** — ADR lifecycle status vs kanban task status; bridged
  (not conflated) by the emit policy mapping.
- **"context"** — ADR "in the context of…" vs the LLM *context window*
  that orchestration manages.
- **"ingest"** — wiki ingest (raw→page) vs pipeline ingest
  (handoff→wiki). Both land in the Knowledge Base context but are
  different mechanisms.

## Duplicate Concepts

- [[concepts/intent-driven-schema]] is intentionally shared (kernel),
  not duplicated — it has a single page referenced by both intent
  contexts.
- [[concepts/progressive-disclosure]] (Agent Skills) and
  [[concepts/progressive-rigor]] (Spec-Driven) are near-synonyms in
  spirit (ration effort) but distinct concepts — *not* a duplicate to
  merge.

## Open Questions

- Does the ADR-status→pattern mapping belong to the ADR context or the
  Orchestration context? Currently encoded in `development/config.yaml`
  (emit policy), i.e. owned by neither wiki context — a pipeline
  configuration concern.
