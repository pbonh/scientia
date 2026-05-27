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
`kg_pipeline.confidence.recompute` its *sole* writer and *idempotent* — also
stamping an `inputs_hash` over (`base`, distinct source count, contradiction
state) — so that a rollup verifies each claim's `inputs_hash` against its live
inputs and **raises rather than reading a stale value**, with freshness still
prefetched by `recompute_all` plus the audit staleness trigger,
**and against** never storing it (recompute on every read) or storing it with
no freshness guarantee,
**to achieve** deterministic, idempotent confidence (ASR-2), cheap reads, and a
stable automation gate (ASR-4),
**accepting** a window in which a stored `effective` is stale between an
input change and the next recompute — now surfaced as a loud staleness error by
the `inputs_hash` check rather than silently used.

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
  `source_count`, `contradicted`, and an `inputs_hash` stamp over (`base`,
  distinct source count, contradiction state).
- `rollup_page` / `rollup_edge` read stored `effective` but first verify each
  claim's `inputs_hash` against its live inputs; on mismatch the rollup
  **raises a validation error** (caught by the controller's advance gate,
  ADR-0006) rather than returning a stale value. The controller still schedules
  `recompute_all` / `audit-wiki` via `audit.staleness_days` as a heuristic
  prefetch; the `inputs_hash` check is the hard backstop for an edit made
  *within* the staleness window.
- Reads stay cheap in the fresh case; the recompute-on-read variant (design
  Open Question #3) is therefore **not needed** and stays deferred.

## Supersession

Supersedes nothing.
