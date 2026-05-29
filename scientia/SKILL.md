---
name: scientia
description: Orchestrates the KG-seeded research-to-tasks pipeline (the scientia skill suite). Activate when the user asks to "run the pipeline", "start a new change", or "go from sources to tasks". Reads config.yaml and walks scientia-ingest-source → (scientia-audit-wiki) → scientia-seed-proposal → scientia-grill-proposal → scientia-write-specs → scientia-write-design → scientia-record-adr → scientia-generate-tasks, activating the appropriate child skill at each stage and respecting per-stage thresholds and modes. State moves only through on-disk artifacts; a stage is advanced past only via the package-owned validation marker.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+
metadata:
  stage: orchestration
  version: "1.0"
---

# scientia

Sequence the pipeline and enforce the gates. You pass **nothing in memory**
between stages (ADR-0006): each stage reads the prior stage's artifact off disk
and writes its own. You decide *order and gating*; the child skills do the work
and `scientia` owns every derived number and every advance marker.

## Procedure

1. **Resolve or generate `<change-id>`** (kebab-case, e.g.
   `2026-05-28-rag-replacement`). Create `proposals/<change-id>/` via
   `scientia.paths.change_dir(cid)`.
2. **Read `references/config.yaml`** (`scientia.paths.config_path()`).
   **Surface any unrecognized top-level key** to the operator (see Recognized
   keys below) rather than ignoring it.
3. **Walk the stages in order**, activating the child skill for each. After each
   stage, gate advancement with `scientia.advance.advance(cid, stage)` — it
   re-runs the stage's validator and writes the `<stage>.ok` marker **only** if
   there are no errors. **Never advance past a stage whose `AdvanceResult.ok` is
   False**; report its `errors` and halt.
4. **Honor each stage's mode** at a low-confidence branch (see below).
5. **Maintain `decisions-log.md`** for every autonomous low-confidence pick.

## Stage → child skill → mode key

| Order | Stage | Child skill | Gated by `advance(...)` | Mode key |
|------:|-------|-------------|--------------------------|----------|
| 1 | ingest | `scientia-ingest-source` | (wiki validation) | `ingest_source` |
| 1a | audit (conditional) | `scientia-audit-wiki` | (wiki validation) | `audit_wiki` |
| 2 | seed | `scientia-seed-proposal` → `proposal` | `proposal` | `seed_proposal` |
| 3 | grill | `scientia-grill-proposal` → `grill` | `grill` | `grill_proposal` |
| 4 | specs | `scientia-write-specs` → `specs` | `specs` | `write_specs` |
| 5 | design | `scientia-write-design` → `design` | `design` | `write_design` |
| 6 | adr | `scientia-record-adr` → `adrs` | `adrs` | `record_adr` |
| 7 | tasks | `scientia-generate-tasks` → `tasks` | `tasks` | `generate_tasks` |

## Conditional audit

If `modes.audit_wiki` is `autonomous` and the wiki has not been audited within
`audit.staleness_days` (14), activate `scientia-audit-wiki` **between
`scientia-ingest-source` and `scientia-seed-proposal`**. (Audit freshness is also
backstopped by the confidence rollups, which raise on a stale `inputs_hash`.)

## Mode semantics (ADR-0010)

- **`autonomous`** — at a low-confidence branch, pick the safest default and
  append an entry to `proposals/<change-id>/decisions-log.md`
  (`scientia.paths.decisions_log_path`) citing the wiki claim(s) involved
  **and the threshold that fired**. Continue.
- **`pause_and_ask`** — at a low-confidence branch, emit
  `proposals/<change-id>/question-for-operator.md`
  (`scientia.paths.question_for_operator_path`) and **halt**. Do not proceed
  until the artifact is resolved (deleted, or marked answered in its
  frontmatter).

The defaults are conservative: the stages nearest durable architectural
commitments (`write_design`, `record_adr`) default to `pause_and_ask`.

## Decision rules (spec: pipeline-orchestration)

- Never advance past a stage whose artifact fails validation — gate every stage
  through `scientia.advance.advance`, which is the *only* writer of the
  advance marker. The orchestrator cannot fabricate an advance.
- Every autonomous low-confidence pick is logged with claim citations and the
  firing threshold.
- A `pause_and_ask` branch halts on `question-for-operator.md`.
- Unrecognized `config.yaml` keys are surfaced, not silently ignored.

## Recognized `config.yaml` keys

Top-level: `confidence`, `thresholds`, `audit`, `modes`, `hermes`. Within:
`confidence.{source_count_curve, contradiction_floor, rollup}`;
`thresholds.{proposal_seed_min, prior_art_floor, grill_dismiss_min,
adr_recommend_accept_min, low_confidence_floor}`; `audit.{staleness_days}`;
`modes.{ingest_source, audit_wiki, seed_proposal, grill_proposal, write_specs,
write_design, record_adr, generate_tasks}`; the optional `hermes` block
(execution layer — see below). Any other key is surfaced.

## Optional execution layer (additive)

When a `hermes:` block is present in `config.yaml` **and** the `tasks` stage has
advanced clean, recommend the execution layer:
`scientia-hermes-init → scientia-hermes-emit` (then `scientia-hermes-status` to
observe). This is the *only* hermes-related behavior the orchestrator gains, and
it is purely additive — **absent the block, behavior is unchanged** and Hermes is
never a dependency. When `hermes.conflict_prevention: true`, the `write_design`
and `generate_tasks` stages also emit the gated ownership markers (Component Map,
Shared Contracts, per-task `component`/`touches`/`*-contract`), and
`validate_design`/`validate_tasks` are called with `require_prevention=True`.

## Acceptance behavior

- A failing stage halts the orchestrator with the validation errors reported.
- An autonomous low-confidence pick is written to `decisions-log.md` with
  citations and the firing threshold.
- A `pause_and_ask` branch emits `question-for-operator.md` and does not advance
  until resolved.
- A stale wiki triggers `scientia-audit-wiki` before `scientia-seed-proposal`.
- An unrecognized config key is surfaced to the operator.
