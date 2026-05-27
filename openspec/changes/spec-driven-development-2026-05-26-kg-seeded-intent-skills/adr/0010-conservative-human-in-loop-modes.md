---
title: "ADR-0010: Default durable-commitment stages to pause_and_ask"
adr_id: ADR-0010
status: proposed
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Confidence-gated automation, conservative at durable commitments (ASR-4)."
shared_types: []
tags: [spec-driven-development, orchestration, human-in-loop]
created: 2026-05-27
---

# ADR-0010: Default durable-commitment stages to pause_and_ask

## Y-Statement

**In the context of** per-stage human-in-loop modes governing what happens at a
low-confidence branch,
**facing** the trade-off between unattended throughput and the cost of a silent
bad architectural commitment,
**we decided for** a per-stage `autonomous` / `pause_and_ask` policy in which
the stages nearest durable commitments — `write_design` and `record_adr` —
default to `pause_and_ask`, while ingestion and seeding (`ingest_source`,
`seed_proposal`, `write_specs`, `generate_tasks`, `audit_wiki`) default to
`autonomous`,
**and against** all-autonomous, all-pause, or a single global mode,
**to achieve** confidence-gated automation (ASR-4) that is conservative exactly
where output is hardest to revise,
**accepting** human latency at the design/ADR stages and the need to tune the
mode table per project.

## Architecturally Significant Requirement

ASR-4: the per-claim `effective` score gates automation, but the *consequence*
of a wrong autonomous pick differs by stage. A mis-seeded proposal is cheaply
revised; a wrong durable ADR or design poisons everything downstream. The mode
table encodes that asymmetry, defaulting to caution where reversal is
expensive.

## Options Considered

### Option A — All stages autonomous
*Pros:* fully unattended.
*Cons:* a low-confidence design/ADR pick is logged but committed; expensive to
unwind. Too risky at durable stages.

### Option B — All stages pause_and_ask
*Pros:* maximally safe.
*Cons:* destroys throughput; a human is interrupted even for trivially
revisable seeding choices.

### Option C — Single global mode
*Pros:* one knob.
*Cons:* cannot express the revisability asymmetry; forces the same risk posture
on ingest and ADR recording.

### Option D — Per-stage modes, conservative defaults at durable stages (chosen)
`write_design` + `record_adr` ⇒ `pause_and_ask`; the rest ⇒ `autonomous`;
`autonomous` low-confidence picks logged to `decisions-log.md`.
*Pros:* matches risk to reversibility; tunable. **Chosen.**
*Cons:* a mode table to maintain; latency at durable stages.

## Consequences

- `autonomous` low-confidence picks are appended to
  `proposals/<change-id>/decisions-log.md` citing the wiki claims and the
  threshold that fired; `pause_and_ask` emits `question-for-operator.md` and
  halts until resolved.
- `record_adr` additionally auto-records without prompting when a decision's
  inherited confidence ≥ `adr_auto_record_min` (0.90), even in
  `pause_and_ask` — high confidence overrides the pause.
- The mode table ships as a default in `references/config.yaml`; projects
  override per stage.

## Supersession

Supersedes nothing.
