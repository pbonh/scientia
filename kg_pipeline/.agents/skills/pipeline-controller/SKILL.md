---
name: pipeline-controller
description: Orchestrates the KG-seeded research-to-tasks pipeline. Activate when the user asks to "run the pipeline", "start a new change", or "go from sources to tasks". Reads config.yaml and walks ingest → (audit) → seed-proposal → grill-proposal → write-specs → write-design → record-adr → generate-tasks, activating the appropriate child skill at each stage and respecting per-stage thresholds and modes. State moves only through on-disk artifacts; a stage is advanced past only via the package-owned validation marker.
metadata:
  stage: orchestration
  version: "1.0"
---

# pipeline-controller

Sequence the pipeline and enforce the gates. You pass **nothing in memory**
between stages (ADR-0006): each stage reads the prior stage's artifact off disk
and writes its own. You decide *order and gating*; the child skills do the work
and `kg_pipeline` owns every derived number and every advance marker.

## Procedure

1. **Resolve or generate `<change-id>`** (kebab-case, e.g.
   `2026-05-28-rag-replacement`). Create `proposals/<change-id>/` via
   `kg_pipeline.paths.change_dir(cid)`.
2. **Read `references/config.yaml`** (`kg_pipeline.paths.config_path()`).
   **Surface any unrecognized top-level key** to the operator (see Recognized
   keys below) rather than ignoring it.
3. **Walk the stages in order**, activating the child skill for each. After each
   stage, gate advancement with `kg_pipeline.advance.advance(cid, stage)` — it
   re-runs the stage's validator and writes the `<stage>.ok` marker **only** if
   there are no errors. **Never advance past a stage whose `AdvanceResult.ok` is
   False**; report its `errors` and halt.
4. **Honor each stage's mode** at a low-confidence branch (see below).
5. **Maintain `decisions-log.md`** for every autonomous low-confidence pick.

## Stage → child skill → mode key

| Order | Stage | Child skill | Gated by `advance(...)` | Mode key |
|------:|-------|-------------|--------------------------|----------|
| 1 | ingest | `ingest-source` | (wiki validation) | `ingest_source` |
| 1a | audit (conditional) | `audit-wiki` | (wiki validation) | `audit_wiki` |
| 2 | seed | `seed-proposal` → `proposal` | `proposal` | `seed_proposal` |
| 3 | grill | `grill-proposal` → `grill` | `grill` | `grill_proposal` |
| 4 | specs | `write-specs` → `specs` | `specs` | `write_specs` |
| 5 | design | `write-design` → `design` | `design` | `write_design` |
| 6 | adr | `record-adr` → `adrs` | `adrs` | `record_adr` |
| 7 | tasks | `generate-tasks` → `tasks` | `tasks` | `generate_tasks` |

## Conditional audit

If `modes.audit_wiki` is `autonomous` and the wiki has not been audited within
`audit.staleness_days` (14), activate `audit-wiki` **between ingest and
seed-proposal**. (Audit freshness is also backstopped by the confidence
rollups, which raise on a stale `inputs_hash`.)

## Mode semantics (ADR-0010)

- **`autonomous`** — at a low-confidence branch, pick the safest default and
  append an entry to `proposals/<change-id>/decisions-log.md`
  (`kg_pipeline.paths.decisions_log_path`) citing the wiki claim(s) involved
  **and the threshold that fired**. Continue.
- **`pause_and_ask`** — at a low-confidence branch, emit
  `proposals/<change-id>/question-for-operator.md`
  (`kg_pipeline.paths.question_for_operator_path`) and **halt**. Do not proceed
  until the artifact is resolved (deleted, or marked answered in its
  frontmatter).

The defaults are conservative: the stages nearest durable architectural
commitments (`write_design`, `record_adr`) default to `pause_and_ask`.

## Decision rules (spec: pipeline-orchestration)

- Never advance past a stage whose artifact fails validation — gate every stage
  through `kg_pipeline.advance.advance`, which is the *only* writer of the
  advance marker. The controller cannot fabricate an advance.
- Every autonomous low-confidence pick is logged with claim citations and the
  firing threshold.
- A `pause_and_ask` branch halts on `question-for-operator.md`.
- Unrecognized `config.yaml` keys are surfaced, not silently ignored.

## Recognized `config.yaml` keys

Top-level: `confidence`, `thresholds`, `audit`, `modes`. Within:
`confidence.{source_count_curve, contradiction_floor, rollup}`;
`thresholds.{proposal_seed_min, prior_art_floor, grill_dismiss_min,
adr_recommend_accept_min, low_confidence_floor}`; `audit.{staleness_days}`;
`modes.{ingest_source, audit_wiki, seed_proposal, grill_proposal, write_specs,
write_design, record_adr, generate_tasks}`. Any other key is surfaced.

## Acceptance behavior

- A failing stage halts the controller with the validation errors reported.
- An autonomous low-confidence pick is written to `decisions-log.md` with
  citations and the firing threshold.
- A `pause_and_ask` branch emits `question-for-operator.md` and does not advance
  until resolved.
- A stale wiki triggers `audit-wiki` before `seed-proposal`.
- An unrecognized config key is surfaced to the operator.
