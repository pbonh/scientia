---
skill: pipeline-controller
---

# Rubric: pipeline-controller

## Setup

Point `pipeline-controller` at a project with `sources/karpathy-2026.md`, an
empty `wiki/`, and the shipped `references/config.yaml`. Ask it to run the
pipeline end-to-end for a new change. Save its run log/summary to `output.md`.

## Expected behavior

- It generates a `<change-id>` and creates `proposals/<change-id>/`.
- It walks the stages in order and gates each via the package-owned advance
  marker (refusing to advance past a failing stage).
- It halts at `write_design` / `record_adr` (pause_and_ask) for operator input.
- It logs autonomous low-confidence picks to `decisions-log.md`.

## Required mentions (output MUST contain)

- proposals/
- advance
- decisions-log.md
- pause_and_ask
- question-for-operator.md

## Forbidden mentions (output MUST NOT contain)

- skipped validation
- advanced past the failing stage
- passed state in memory

## Pass criteria

State moves only on disk, every stage is gated by the package-owned validation
marker (no fabricated advance), the durable-commitment stages pause for the
operator, and autonomous picks are logged with citations and the firing
threshold.
