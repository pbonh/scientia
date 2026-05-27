---
title: "ADR-0006: Transfer pipeline state through on-disk artifacts only"
adr_id: ADR-0006
status: proposed
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "On-disk-only state transfer; the controller passes no in-memory values (ASR-3)."
  - "Portability across runtimes (ASR-1)."
  - "Validation gating enforced by construction: the advance marker is a package-owned, validator-passed write (ASR-5)."
shared_types: []
tags: [spec-driven-development, orchestration, state-transfer]
created: 2026-05-27
---

# ADR-0006: Transfer pipeline state through on-disk artifacts only

## Y-Statement

**In the context of** the `pipeline-controller` sequencing ingest → seed →
grill → specs → design → adr → tasks,
**facing** the choice of how state moves between stages,
**we decided for** transferring state *only* through on-disk artifacts — each
stage reads the prior artifact from disk and writes its own — with the
controller holding no in-memory pipeline object, and with the stage-advance
marker itself being an on-disk artifact written *only* by `kg_pipeline` after
its validators pass, so the controller cannot fabricate an advance,
**and against** an in-memory pipeline/context object passed between stages,
**to achieve** resumability, runtime-agnostic portability, and the ability to
re-run or inspect any stage from its inputs alone,
**accepting** the cost of re-parsing artifacts at each stage and the absence of
a rich typed in-memory handoff.

## Architecturally Significant Requirement

ASR-3: the controller passes no values in memory; a stage must be re-runnable
standalone from the prior stage's artifact. This is what makes the pipeline
portable (ASR-1) — the controller is itself a `SKILL.md` whose runtime may
differ between invocations, so no in-memory state can be assumed to survive a
stage boundary.

## Options Considered

### Option A — In-memory pipeline/context object
A controller process threads a context object through stages.
*Pros:* rich typed handoff; no re-parsing.
*Cons:* assumes a single long-lived process; not portable across Agent-Skills
runtimes; not resumable after interruption; couples stages.

### Option B — Shared in-memory blob + disk artifacts (hybrid)
*Pros:* faster.
*Cons:* two sources of truth that can disagree; the worst of both. Rejected.

### Option C — On-disk artifacts only (chosen)
Files are the sole inter-stage channel; `kg_pipeline.paths` locates them.
*Pros:* resumable, inspectable, portable, re-runnable per stage. **Chosen.**
*Cons:* re-parse cost; handoff limited to what is serialized in the artifact.

## Consequences

- Any stage can be re-run in isolation given the prior artifact — supports
  resume-after-halt (`question-for-operator.md`) and partial re-runs.
- The controller is stateless between stages; it sequences and validates, it
  does not carry data.
- Each artifact must be self-sufficient for the next stage — reinforced by the
  validators gating advancement (ADR-0007).
- The "stage N validated → proceed" record is an on-disk marker written
  **solely by `kg_pipeline`**, and only when `validators.*` returns an empty
  error list. Because advancing the pipeline *is* this deterministic, validated
  write, the LLM controller cannot skip the gate by fiat — it sequences and
  reads, but cannot author the advance. This closes the ASR-5 enforcement gap
  that ADR-0007 previously logged as residual risk.

## Supersession

Supersedes nothing.
