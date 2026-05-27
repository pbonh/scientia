---
title: "Tasks manifest — spec-driven-development/2026-05-26-kg-seeded-intent-skills"
type: manifest-tasks
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
scientia_schema: 1
wiki_snapshot: fac4672677a83e130b04a5a2dc1215e51b776691
created: 2026-05-27
---

> **Snapshot note.** Tasks entered at `fac4672` with a **dirty** working tree
> (this session's grill/adr/verify edits are uncommitted), so this pin is
> approximate — the same posture the design manifest recorded for core's
> `53cdbb5`. No wiki *content* changed at tasks entry; only the change's
> own artifacts did.

## 9 — Tradeoffs & Suggestions (decomposition rules)

No dedicated INVEST / story-splitting / SMART concept pages exist in the wiki at
this snapshot. The rules below are the standard formulations, narrowed to what
constrains *this* decomposition, plus the two testing concepts the wiki does
carry ([[concepts/test-pyramid]], [[concepts/test-driven-development]]).

### INVEST (per-task self-check, applied before exit)

- **Independent** — tasks touch disjoint files where possible; the few that
  share `kg_pipeline/wiki/__init__.py` are serialized by an explicit
  `(depends on #N)` chain rather than run in parallel.
- **Negotiable** — each task names *what* (the scenario/ADR it satisfies), not a
  line-by-line *how*.
- **Valuable** — every behavioral task backlinks a spec scenario; non-behavioral
  tasks (scaffold, CI, docs) are explicitly marked and kept late via deps.
- **Estimable / Small** — one module function or one `SKILL.md` per task; a task
  completes in a single coding session with one observable output.
- **Testable** — each behavioral task's `@spec:` scenario *is* its acceptance
  test; the golden-file/eval tasks make that mechanical.

### Story-splitting heuristics actually used

- **By module seam** — `paths` / `wiki` / `confidence` / `templates` /
  `validators` are split along the package's own module boundaries.
- **By workflow step** — the nine skills split along the pipeline's stages
  (ingest → audit → seed → grill → write-specs → write-design → record-adr →
  generate-tasks → controller).
- **By interface (skill vs module)** — LLM-judgment work (`SKILL.md`) is a
  separate task from the deterministic module it calls (ADR-0007's seam).
- **By data variation** — the confidence scenarios (accumulation / cap /
  contradiction / base-preserved) are acceptance variations on one `recompute`
  task, not separate tasks.
- **By test layer** — module golden-file tests and skill rubric evals are
  distinct tasks, per the test-pyramid (a wide deterministic base under a
  narrower rubric-judged tier).

### SMART (applies to the non-behavioral CI/eval tasks)

Specific (run `validate_skill_md` + golden suite + evals), Measurable (empty
error list / rubric pass), Achievable, Relevant (ASR-6 skill budget, ASR-2
determinism), Time-boxed (one session).

### ADR-derived ordering constraints (hard dependencies)

- **ADR-0001 shared-type gate.** `Page` / `Link`
  (`kg_pipeline/wiki/__init__.py`) must be *produced* (task 4) before any task
  carrying `@uses-shared:` for them. ADR-0001 is `accepted`, so the
  `scientia-kanban-emit` preflight is satisfied.
- **ADR-0005** — `kg_pipeline.paths` (task 2) is the layout authority; module
  and skill tasks resolve paths through it, so it precedes them.
- **ADR-0003** — `references/config.yaml` (task 3) carries the committed
  confidence curve/floor/thresholds + per-stage modes; `confidence`, `seed`,
  `grill`, `record-adr`, and the controller depend on it.
- **ADR-0008** — `templates` module (task 12) + the 7 templates (task 13)
  precede every authoring skill that renders them.
- **ADR-0006** — the package-owned stage-advance marker (task 15) precedes the
  `pipeline-controller` (task 24) that relies on it to enforce the gate.
