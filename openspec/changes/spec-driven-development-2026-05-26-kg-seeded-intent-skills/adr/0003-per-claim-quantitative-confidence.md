---
title: "ADR-0003: Model confidence per-claim and quantitatively"
adr_id: ADR-0003
status: proposed
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Confidence is a deterministic automation gate, not a vibe (ASR-4)."
shared_types: []
tags: [spec-driven-development, confidence, automation-gate]
created: 2026-05-27
---

# ADR-0003: Model confidence per-claim and quantitatively

## Y-Statement

**In the context of** a pipeline whose autonomous-vs-human decisions and
seeding/grill thresholds must be reproducible,
**facing** the fact that scientia's existing per-page *qualitative*
high/medium/low confidence cannot gate automation and a single LLM rating is
poorly calibrated and ignores accumulation,
**we decided for** a per-claim *quantitative* `[0,1]` model —
`effective = min(contradiction_floor, base × multiplier)` when contradicted,
else `base × multiplier` — and for **confirming the seed brief's configuration
as the committed default** rather than re-deriving it,
**and against** the per-page qualitative field, a pure-LLM score, or a learned
probabilistic model,
**to achieve** a deterministic automation gate that sharpens the
compounding-knowledge principle (accumulation raises, contradiction caps),
**accepting** that the curve and floor are hand-tuned constants and `effective`
is a calibrated heuristic, not a probability.

## Architecturally Significant Requirement

ASR-4: given a claim's `base`, distinct source count, and contradiction state,
`effective` must be reproducible from the configured curve and floor, so that
`seed-proposal` inclusion, `grill-proposal` challenges, and
`record-adr` auto-recording behave identically across runs and runtimes. This
also resolves proposal Open Question #4 (confirm defaults at design time).

**Committed configuration defaults (confirmed):**

```yaml
confidence:
  source_count_curve: [1.00, 0.04, 1.10]   # base, step, cap
  contradiction_floor: 0.40
  rollup: min
thresholds:
  proposal_seed_min: 0.70
  prior_art_floor:   0.60
  grill_dismiss_min: 0.85
  adr_auto_record_min: 0.90
  low_confidence_floor: 0.40
audit:
  staleness_days: 14
```

`multiplier(n) = min(1.10, 1.00 + 0.04 × (n − 1))`.

## Options Considered

### Option A — Keep per-page qualitative high/medium/low
*Pros:* zero new machinery; matches the existing wiki.
*Cons:* not orderable against a threshold; cannot gate automation; the unit
(page) is too coarse — a page mixes strong and weak claims. Fails ASR-4.

### Option B — Pure LLM score per claim, no augmentation
*Pros:* simplest.
*Cons:* poorly calibrated; ignores accumulation (the wiki pattern's central
insight) and contradiction; non-reproducible if re-asked.

### Option C — Learned/Bayesian confidence model
*Pros:* principled.
*Cons:* needs training data and a dependency; non-deterministic; over-built for
the brief. A non-goal.

### Option D — Per-claim base × deterministic multiplier, contradiction floor (chosen)
LLM sets `base` once; pure-Python source-count multiplier and contradiction cap
produce `effective`.
*Pros:* deterministic, idempotent, cheap, gated by config; encodes
accumulation-raises / contradiction-caps. **Chosen.**
*Cons:* hand-tuned constants; heuristic, not probabilistic.

## Consequences

- The unit of confidence is the **claim**, not the page; only `claim` pages
  carry it (`entity`/`source`/`question` do not).
- The qualitative per-page field remains a documented **false cognate** of this
  model and is *not* migrated into existing wikis (clean-room scope).
- The constants are config-tunable; changing a *default* in a future release is
  a supersession of this ADR, not an in-place edit.
- Page/edge confidence is a rollup (default `min`) over claims — see
  [[concepts/architecturally-significant-requirement]] and ADR-0004.

## Supersession

Supersedes nothing.
