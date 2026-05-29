---
name: scientia-record-adr
description: Extracts durable architectural decisions from design.md into individual ADR markdown files (MADR/Nygard style with a Y-statement). Writes one ADR per decision and never combines decisions. At high inherited confidence it presents a pre-drafted ADR as recommended-accept for one-click human confirmation, but never auto-records. Defaults to pause_and_ask. Activate after design.md stabilizes.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+
metadata:
  stage: adr
  version: "1.0"
---

# scientia-record-adr

Distill the durable architectural decisions in `design.md` into immutable ADR
files under `proposals/<change-id>/adrs/`. One ADR per decision — never combine
two decisions into one file (avoids spec/ADR drift).

## Inputs

- `proposals/<change-id>/design.md`

## Outputs

- `proposals/<change-id>/adrs/<NNNN>-<kebab-title>.md`, one per decision,
  rendered from the `adr` template via `scientia.templates`. ADR numbers are
  a monotonic sequence, never reused.

## ADR shape (MADR / Nygard + Y-statement)

The `adr` template provides: `## Status`, `## Y-Statement`, `## Context`,
`## Decision`, `## Consequences`, `## Sources`. The Y-statement is the one-line
executive summary:

> In the context of `<forces>`, facing `<concern>`, we decided for `<option>`
> and against `<alternatives>`, to achieve `<benefits>`, accepting `<drawbacks>`.

`scientia.validators.validate_adrs` checks that every ADR has Status,
Context, Decision, and Consequences sections.

## Confidence-gated presentation (never auto-record)

Compute each decision's **inherited confidence** — the rollup over the design
assertions and the wiki claims they cite (use `scientia.confidence.rollup_*`
where the design cites claims).

- If inherited confidence `>= thresholds.adr_recommend_accept_min` (0.90):
  present the pre-drafted ADR to the operator marked **"recommended: accept"**
  for one-click confirmation. **Do not record it until the operator confirms.**
- Otherwise (in `pause_and_ask`): ask the operator before recording.

There is **no auto-record path** — `adr_recommend_accept_min` only decides
*presentation*, never whether to write without confirmation (ADR-0003,
ADR-0010).

## Immutability

Accepted ADRs are never edited in place. A changed decision is a *new* ADR that
supersedes the prior one (set `supersedes:` and the prior's status to
`superseded`). Never rewrite an accepted ADR's body.

## Low-confidence handling (mode key: `record_adr`, default `pause_and_ask`)

This is the stage nearest the most durable commitment; it always pauses for
human confirmation before recording.

## Acceptance behavior (spec: intent-artifact-generation)

- Two distinct decisions in `design.md` yield two separate ADR files.
- A decision at inherited confidence 0.93 (≥0.90) is presented as
  "recommended: accept" and no ADR is recorded until the operator confirms.
