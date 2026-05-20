# 01 — Wiki-only: building a research knowledge graph

**Audience.** A research lead or staff engineer mapping a new technical
domain before any change is proposed. The goal is a high-confidence
wiki; *no manifest is bound, no OpenSpec change is created, no kanban
tasks are emitted.*

**Setting.** Anya is the platform lead at a payments company. The
team is about to take ownership of a poorly understood vendor
integration — a third-party fraud-scoring service. Before anyone
writes a proposal, she wants the wiki to actually know what
"fraud scoring," "feature store," and "model drift" mean in *their*
context. She has a folder of three PDFs, two vendor docs, and a
recorded interview transcript with the security team.

```
research/
├── fraud-scoring-vendor-paper.pdf
├── vendor-api-docs.html
├── internal-fraud-postmortem-2025-Q4.pdf
├── security-team-interview-2026-04-30.txt
└── feature-store-architecture-deck.pdf
```

She starts in a fresh repository.

```bash
$ cd ~/work/fraud-research
$ git init -q
$ ls
research/
```

## Phase 1.1 — Initialize the scientia layout

```
> "Use the scientia skill."
```

The orchestrator runs `state_detect.py`, sees no `wiki/`, and
recommends `scientia-wiki-init`.

```
scientia (orchestrator):
  state: wiki_present=false
  recommended next: scientia-wiki-init
  reason: no wiki/ directory present
```

```
> "Initialize the wiki."
```

`scientia-wiki-init` runs `scripts/bootstrap.py`, which creates the
scaffold and logs to `development/log.md`:

```
raw/
wiki/
├── index.md                  (created)
├── log.md                    (created)
├── concepts/                 (empty)
├── entities/                 (empty)
├── summaries/                (empty)
├── syntheses/                (empty)
├── contexts/                 (empty)
├── context-maps/             (empty)
├── decisions/                (empty)
└── specs/                    (empty)
development/
├── config.yaml               (created)
├── log.md                    (created)
├── manifests/                (empty)
└── tasks/                    (empty)
openspec/
├── config.yaml               (created)
├── schemas/intent-driven/    (copied from bundle)
└── changes/                  (empty)
```

`development/log.md` now contains:

```markdown
- 2026-05-19T14:02:11Z — scientia-wiki-init — bootstrap-complete — bundle 0.1.0
```

Anya moves her source documents into `raw/`:

```bash
$ mv research/*.pdf research/*.html research/*.txt raw/
$ git add -A && git commit -q -m "raw: seed fraud-research sources"
```

## Phase 1.2 — Ingest the raw sources

```
> "Use the scientia skill."
```

The orchestrator now detects `wiki_present=true`, `tenants={}`, and
non-empty `raw/`. It recommends `scientia-wiki-ingest`.

```
scientia (orchestrator):
  state: wiki_present=true, raw/ has 5 unprocessed sources
  recommended next: scientia-wiki-ingest (per source)
```

```
> "Ingest raw/fraud-scoring-vendor-paper.pdf."
```

`scientia-wiki-ingest` reads the PDF, applies the *atomic-claim*
discipline, and produces:

- One summary: `wiki/summaries/fraud-scoring-vendor-paper.md`
- Six concept pages:
  - `wiki/concepts/feature-store.md`
  - `wiki/concepts/model-drift.md`
  - `wiki/concepts/score-calibration.md`
  - `wiki/concepts/decision-threshold.md`
  - `wiki/concepts/cold-start-traffic.md`
  - `wiki/concepts/feedback-delay.md`
- One entity page: `wiki/entities/sentinel-score-v3.md`
- Index rows added; log lines appended.

A representative concept page:

```markdown
---
title: "Feature Store"
type: concept
tags: [concept, ml-infrastructure, fraud]
created: 2026-05-19
updated: 2026-05-19
sources: ["raw/fraud-scoring-vendor-paper.pdf"]
confidence: medium
---

## Definition
A feature store is a system of record for engineered features used by
both online inference and offline training, guaranteeing that the same
transformation is applied at both sides.

## How It Works
...

## Key Parameters
- Online/offline parity SLO
- Backfill window
- Materialization cadence

## When To Use
When at least one production model needs sub-100ms feature lookups and
the same features feed a training pipeline.

## Risks & Pitfalls
- Online/offline skew when one transformation path is updated without
  the other.
- Hot-key contention on high-cardinality features.

## Related Concepts
- [[concepts/model-drift]]
- [[concepts/score-calibration]]

## Sources
- raw/fraud-scoring-vendor-paper.pdf
```

Anya proceeds through the remaining four sources, ingesting each in
turn. After the postmortem PDF, the `## Risks & Pitfalls` of
`feature-store.md` gets extended (existing page updated, not
duplicated), `sources:` gains a second entry, `updated:` bumps. After
the interview transcript, two *entity* pages land:
`wiki/entities/security-team.md` (an organizational entity) and
`wiki/entities/fraud-ops-runbook.md`.

```
> "Ingest raw/internal-fraud-postmortem-2025-Q4.pdf."
> "Ingest raw/security-team-interview-2026-04-30.txt."
> "Ingest raw/vendor-api-docs.html."
> "Ingest raw/feature-store-architecture-deck.pdf."
```

`wiki/index.md` now lists 11 concept pages, 4 entity pages, and 5
summaries.

## Phase 1.3 — Strategic DDD pass

```
> "Use the scientia skill."
```

```
scientia (orchestrator):
  state: wiki_present=true, 11 concepts/4 entities/5 summaries, no contexts yet
  recommended next: scientia-wiki-strategy
```

```
> "Run strategy."
```

`scientia-wiki-strategy` reads the index, clusters concepts by shared
vocabulary, and asks Anya (via `scientia-grill`) two questions it
cannot decide alone:

1. *"`score-calibration` and `decision-threshold` both seem to live
   on the inference side. Is `decision-threshold` part of the same
   context as `feature-store` (ml-infrastructure), or part of a
   separate operational context owned by fraud-ops? Recommendation:
   place it under a new `fraud-ops` context, since the threshold is
   tuned by ops, not by ML eng. Reasons: (1) the postmortem names
   ops as the owner; (2) the vendor paper treats threshold as a
   business control; (3) keeping it ML-side would force ops into
   ML's ubiquitous language. Choose: (a) ml-infrastructure, (b)
   fraud-ops, (c) park."*
2. *"`feedback-delay` straddles both ml-infrastructure and fraud-ops.
   Is it a duplicate-concept, a false-cognate, or a genuine
   cross-context concern? Recommendation: cross-context concern —
   leave on its current page, link from both context pages, and
   record on the `ml-infrastructure ↔ fraud-ops` context map. ..."*

Anya picks (b) for the first and accepts the recommendation for the
second. The skill then writes:

```
wiki/contexts/
├── ml-infrastructure.md            (subdomain: supporting)
├── fraud-ops.md                    (subdomain: core)
└── vendor-integration.md           (subdomain: generic)

wiki/context-maps/
├── ml-infra-to-fraud-ops.md
└── vendor-to-ml-infra.md
```

A context page (excerpt):

```markdown
---
title: "fraud-ops"
type: context
tags: [context, bounded-context, core]
created: 2026-05-19
updated: 2026-05-19
confidence: medium
---

## Boundary
The decisions and processes by which the fraud team converts a fraud
score into a transaction outcome (approve, hold, decline, manual
review).

## Subdomain Classification
**Core.** This is where the business invests; thresholding policy and
manual-review workflow are differentiators.

## In-Scope Concepts
- [[concepts/decision-threshold]]
- [[concepts/score-calibration]] (cross-context)
- [[concepts/cold-start-traffic]]
- [[concepts/feedback-delay]] (cross-context)

## In-Scope Entities
- [[entities/security-team]]
- [[entities/fraud-ops-runbook]]

## Ubiquitous Language (Glossary)
- **Decision** — the final transaction-time outcome (one of: approve,
  hold, decline, manual-review). Distinct from a *score*.
- **Threshold** — a numeric cutoff applied to a score to derive a
  decision. Per-segment and time-varying.
- **Manual review** — human-in-the-loop adjudication for transactions
  flagged by a `hold` decision.
- ...

## False Cognates with Adjacent Contexts
- `signal` in vendor-integration refers to a vendor-raw feature; in
  fraud-ops it refers to a derived risk indicator on the ops dashboard.
  See [[context-maps/vendor-to-ml-infra]].

## Sources
- raw/internal-fraud-postmortem-2025-Q4.pdf
- raw/security-team-interview-2026-04-30.txt
```

## Phase 1.4 — Lint

```
> "Lint the wiki."
```

`scientia-wiki-lint` walks frontmatter and wiki-links, reporting:

```
scientia-wiki-lint:
  CRITICAL: 0
  WARNING:  2
  SUGGESTION: 5

WARNING — wiki/concepts/feedback-delay.md
  `confidence: low` and referenced from two contexts. Consider raising
  to medium via additional sources, or marking as open question.

WARNING — wiki/context-maps/vendor-to-ml-infra.md
  Section `## Duplicate Concepts` is empty but expected after strategy.
```

No CRITICAL findings means a manifest *could* be bound from this state.
Anya is not yet binding — she's doing pure research — but she fixes
the warnings to keep the wiki honest. She:

1. Adds a one-line "Open Question" note to `feedback-delay.md`
   confirming the page's authority is mid-grade.
2. Adds a `## Duplicate Concepts` note to the context map: *"None
   identified after one strategic pass — revisit when a concrete change
   forces choice between `signal` (vendor-raw) and `signal` (ops
   indicator)."*

Re-runs lint → 0 CRITICAL, 0 WARNING, 5 SUGGESTION. Clean enough.

## Phase 1.5 — Stop here

Anya does **not** run `scientia-wiki-grill` or `scientia-wiki-bind`.
There is no change to bind to — the wiki itself is the deliverable.
She publishes the repo to the team's docs index and moves on.

```
> "Show me the wiki status."

scientia (orchestrator):
  - tenants: {} (no in-flight changes)
  - wiki/index.md present
  - 11 concept pages, 4 entity pages, 5 summaries
  - 3 contexts, 2 context maps
  - lint: clean
  - recommended next: idle — name a tenant when a change is planned
```

## Artifacts produced

```
raw/
  fraud-scoring-vendor-paper.pdf
  vendor-api-docs.html
  internal-fraud-postmortem-2025-Q4.pdf
  security-team-interview-2026-04-30.txt
  feature-store-architecture-deck.pdf

wiki/
  index.md
  log.md
  summaries/
    fraud-scoring-vendor-paper.md
    vendor-api-docs.md
    internal-fraud-postmortem-2025-q4.md
    security-team-interview-2026-04-30.md
    feature-store-architecture-deck.md
  concepts/
    feature-store.md
    model-drift.md
    score-calibration.md
    decision-threshold.md
    cold-start-traffic.md
    feedback-delay.md
    backfill-window.md
    online-offline-skew.md
    manual-review-queue.md
    chargeback-feedback-loop.md
    vendor-rate-limit.md
  entities/
    sentinel-score-v3.md
    security-team.md
    fraud-ops-runbook.md
    feature-platform-v2.md
  contexts/
    ml-infrastructure.md
    fraud-ops.md
    vendor-integration.md
  context-maps/
    ml-infra-to-fraud-ops.md
    vendor-to-ml-infra.md
  decisions/   (empty — no ADRs yet)
  specs/       (empty)
  syntheses/   (empty)

development/
  config.yaml
  log.md
  manifests/   (empty)
  tasks/       (empty)

openspec/
  config.yaml
  schemas/intent-driven/
  changes/     (empty)
```

## Variations

**Knowledge keeps arriving.** Drop a new file in `raw/` and re-invoke
`scientia-wiki-ingest`. The skill is incremental: existing concept
pages are extended (new `sources:` entries, bumped `updated:`),
not duplicated.

**A new researcher joins.** They `git clone` the repo and run *"Use
the scientia skill"*. The orchestrator detects the same state Anya
left, with `tenants: {}`. Either ingest more, run strategy again
(idempotent: only writes new contexts), or read `wiki/index.md` to
get oriented.

**A change emerges.** When the team finally decides to *do* something
with this knowledge — e.g., replace the vendor — they pick a tenant
(`fraud-ops` or `vendor-integration`) and run
`scientia-wiki-grill` against the change scope. That is the
narrative of [02 — End-to-end single change](02-end-to-end-single-change.md).
