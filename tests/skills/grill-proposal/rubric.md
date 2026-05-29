---
skill: grill-proposal
---

# Rubric: grill-proposal

## Setup

Take the proposal produced by the `seed-proposal` eval and a wiki that contains
(a) a claim at `effective 0.42` the proposal implicitly relies on, and (b) a
claim at `effective 0.88` that contradicts a proposal assertion. Run
`grill-proposal`. Save the produced `grill.md` to `output.md` here.

## Expected behavior

- A hidden-assumption challenge cites the 0.42 claim with its `effective`.
- A counter-claim cites the 0.88 claim.
- The failure-pattern section is present and explicitly empty (no post-mortem
  source).
- Every entry carries `addressed: false` (a fresh grill is unaddressed).

## Required mentions (output MUST contain)

- ## Hidden-Assumption Challenges
- effective 0.42
- ## Counter-Claims
- effective 0.88
- ## Failure-Pattern Warnings
- addressed: false

## Forbidden mentions (output MUST NOT contain)

- all entries addressed
- ready to advance

## Pass criteria

The low-confidence dependency is a hidden-assumption challenge, the
high-confidence contradiction is a counter-claim, the failure-pattern section is
explicitly empty, and the grill is emitted unaddressed (blocking advancement).
