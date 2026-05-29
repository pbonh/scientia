---
skill: record-adr
---

# Rubric: record-adr

## Setup

Provide a `design.md` containing two distinct durable decisions, one with
inherited confidence 0.93 (≥ `adr_recommend_accept_min` 0.90) and one at 0.70.
Run `record-adr` in `pause_and_ask` mode. Save the agent's transcript/summary to
`output.md` here.

## Expected behavior

- Two separate ADR files are drafted (one per decision; never combined).
- The 0.93 decision is presented as "recommended-accept" for one-click
  confirmation, and is NOT written until the operator confirms.
- The 0.70 decision is presented as a normal pause-and-ask prompt.

## Required mentions (output MUST contain)

- two
- recommended-accept
- Y-Statement
- await
- confirm

## Forbidden mentions (output MUST NOT contain)

- auto-recorded
- combined the two decisions
- recorded without asking

## Pass criteria

One ADR per decision, the high-confidence decision presented as
recommended-accept but never auto-recorded (it waits for operator confirmation),
and each ADR uses the MADR/Y-statement shape.
