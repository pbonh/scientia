---
title: "ADR-0007: Split LLM judgment (skills) from deterministic logic (kg_pipeline)"
adr_id: ADR-0007
status: proposed
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Determinism & idempotency of reproducible work (ASR-2)."
  - "Validation gating: a deterministic guardrail the controller calls (ASR-5)."
  - "Progressive-disclosure skill budget (ASR-6)."
shared_types: []
tags: [spec-driven-development, architecture, skills, validation]
created: 2026-05-27
---

# ADR-0007: Split LLM judgment (skills) from deterministic logic (kg_pipeline)

## Y-Statement

**In the context of** a pipeline that mixes LLM reading (rating a source,
drafting a proposal, extracting decisions) with reproducible computation
(parsing, confidence, templating, validation),
**facing** the need for both LLM judgment and deterministic, testable behavior
on a generic runtime,
**we decided for** placing all LLM judgment in `SKILL.md` files and all
deterministic, idempotent, golden-tested operations in the `kg_pipeline`
package, with the validators' error-list as the deterministic guardrail the
controller calls before advancing,
**and against** an all-in-skill design (no determinism) or an all-in-code design
(cannot perform LLM tasks),
**to achieve** determinism and testability (ASR-2), an enforceable validation
gate (ASR-5), and a small per-skill context budget (ASR-6),
**accepting** that the controller is itself an LLM skill and could in principle
skip the validator call — a residual risk addressed for v1 by skill-eval
rubrics rather than a deterministic entrypoint that owns the gate.

## Architecturally Significant Requirement

ASR-2 (idempotent, golden-tested deterministic ops), ASR-5 (the controller
refuses to advance on a non-empty validator error list), and ASR-6 (each
`SKILL.md` < 500 lines with examples in `references/`) jointly require a clean
seam: anything that must be reproducible cannot live in an LLM prompt, and the
gate that protects stage advancement must be pure Python.

## Options Considered

### Option A — All logic in skills (prompted)
*Pros:* simplest packaging; no Python.
*Cons:* nothing is reproducible or testable; confidence math and validation
become non-deterministic; fails ASR-2/ASR-5.

### Option B — All logic in code, skills as thin shells
*Pros:* maximally deterministic.
*Cons:* the LLM-shaped steps (rating, drafting, extraction) cannot be expressed
as deterministic code; defeats the pipeline's purpose.

### Option C — Judgment in skills, determinism in kg_pipeline; validators gate (chosen)
Skills call the package; the package is pure-Python and golden-tested;
`validators.*` returns errors the controller acts on.
*Pros:* determinism where it must hold, judgment where it must happen,
small skills. **Chosen.**
*Cons:* the gate's *invocation* depends on the controller skill obeying its
instructions.

## Consequences

- `kg_pipeline` carries every reproducible operation and a golden-file test per
  module; skills carry no derived state.
- The validation gate is deterministic *as a function*; its *enforcement*
  depends on the controller calling it. For v1, the skill-eval rubric asserts
  the halt; a deterministic `kg_pipeline` entrypoint that owns the gate is the
  flagged alternative if the rubric proves insufficient (design Open Question).
- Skill bodies stay under 500 lines with examples pushed to `references/`.

## Supersession

Supersedes nothing.
