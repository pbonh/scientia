---
title: "ADR-0004: Store the effective score as a derived, recompute-owned value"
adr_id: ADR-0004
status: proposed
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Determinism & idempotency: recompute is the only writer and is idempotent (ASR-2)."
  - "Confidence as a stable automation gate (ASR-4)."
shared_types: []
tags: [spec-driven-development, confidence, idempotency]
created: 2026-05-27
---

# ADR-0004: Store the effective score as a derived, recompute-owned value

## Y-Statement

**In the context of** the per-claim confidence model (ADR-0003) whose
`effective` value gates automation and is read frequently during seeding and
grilling,
**facing** the tension that a derived value persisted in frontmatter can drift
from its inputs, while recomputing on every read is wasteful,
**we decided for** persisting `effective` in the claim's frontmatter but making
`kg_pipeline.confidence.recompute` its *sole* writer and *idempotent*, with
rollups reading post-recompute values and freshness guaranteed by
`recompute_all` plus the audit staleness trigger,
**and against** never storing it (recompute on every read) or storing it with
no freshness guarantee,
**to achieve** deterministic, idempotent confidence (ASR-2), cheap reads, and a
stable automation gate (ASR-4),
**accepting** a window in which a stored `effective` is stale between an
input change and the next recompute, and a reliance on audit/staleness
discipline to close it.

## Architecturally Significant Requirement

ASR-2 requires every deterministic operation to be idempotent: a second
`recompute` over unchanged inputs must change nothing, and `base` must survive
recompute untouched. ASR-4 requires the gate value to be stable and
reproducible. A derived field that any skill could hand-edit would break both;
hence the single-writer rule.

## Options Considered

### Option A — Never store; recompute on every read
*Pros:* impossible to drift; always correct.
*Cons:* every traversal re-reads all sources and contradiction edges per claim;
costly at the brief's read-heavy seeding/grill stages.

### Option B — Store, but allow any writer
*Pros:* convenient.
*Cons:* skills hand-edit it, defeating determinism and auditability; the gate
becomes a vibe again. Rejected.

### Option C — Store; recompute is sole, idempotent writer; freshness via audit (chosen)
`base` is written once at ingest and frozen; `recompute` derives and writes
`effective`; `recompute_all` + staleness keep it fresh.
*Pros:* cheap reads, deterministic, auditable, idempotent. **Chosen.**
*Cons:* a staleness window between edit and recompute.

## Consequences

- `base` is immutable after ingest; only `recompute` writes `effective`,
  `source_count`, and `contradicted`.
- `rollup_page` / `rollup_edge` read stored `effective`; callers that gate on a
  rollup must ensure `recompute_all` (or `audit-wiki`) has run — the controller
  schedules this via `audit.staleness_days`.
- The staleness window is the explicit cost; a recompute-on-read variant is
  deferred (see design Open Questions) unless a caller proves it necessary.

## Supersession

Supersedes nothing.
