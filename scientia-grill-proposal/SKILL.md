---
name: scientia-grill-proposal
description: Interrogates a proposal against the KG, producing grill.md with four sections — open questions, counter-claims, hidden-assumption challenges, and failure-pattern warnings. Each entry cites the wiki page(s) and effective confidence it draws from. The proposal cannot advance to specs until every grill entry is marked addressed. Activate after scientia-seed-proposal has produced a proposal.md.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+
metadata:
  stage: grill
  version: "1.0"
---

# scientia-grill-proposal

Read `proposals/<change-id>/proposal.md` and emit `grill.md` — the gate that
forces a proposal to confront the weak parts of the KG it leans on. The
highest-leverage section is **hidden-assumption challenges**: every claim the
proposal *implicitly relies on* that sits below the dismissal threshold must be
addressed before the change advances.

## Inputs

- `proposals/<change-id>/proposal.md`.
- The entire wiki, for query (`scientia.wiki`, `scientia.confidence`).

## Outputs

- `proposals/<change-id>/grill.md`, rendered from the `grill` template. Each
  entry carries its own `id` and `addressed: false`, and cites its source
  page(s) with `effective` inline.

## The four sections

1. **Open Questions** — Question pages within 2 hops of the topic entity, plus
   questions you generate from gaps the proposal does not address.
2. **Counter-Claims** — wiki claims with
   `effective >= thresholds.grill_dismiss_min` (0.85) that contradict or stand
   in tension with a proposal assertion (your judgment).
3. **Hidden-Assumption Challenges** — for every proposal assertion, identify the
   wiki claims it implicitly relies on. For each such claim with
   `effective < thresholds.grill_dismiss_min`, add an entry citing the claim and
   its `effective`. A proposal depending on a claim at 0.42 must explicitly
   address that fragility.
4. **Failure-Pattern Warnings** — patterns from Source pages tagged
   `kind: post-mortem` relevant to the topic. **May be explicitly empty** when no
   such source applies.

## Decision rules

- `autonomous`: dismiss a candidate challenge only if its supporting claim has
  `effective < grill_dismiss_min` AND no `contradicts` edge exists; otherwise
  include it.
- `pause_and_ask`: when in doubt, include and flag.
- A high-confidence (≥0.85) contradicting claim is always a counter-claim; a
  relied-upon claim below 0.85 is always a hidden-assumption challenge.

## Advancement gate

A freshly-emitted `grill.md` is **unaddressed by construction**, so
`scientia.validators.validate_grill` reports its entries and
`scientia.advance.advance(change_id, "grill")` refuses to stamp the marker.
The proposer answers each entry in the `## Responses` section and flips its
`addressed:` flag to `true`. Only when no `addressed: false` flag remains does
the grill stage validate clean and advancement become possible. **Do not edit
the flags yourself** — that is the proposer's act.

## Low-confidence handling (mode key: `grill_proposal`, default `autonomous`)

Bias toward inclusion: a missed challenge is more costly than an extra one.

## Acceptance behavior (spec: kg-grill-proposal)

- A relied-upon claim at 0.42 (below `grill_dismiss_min`) surfaces as a
  hidden-assumption challenge citing its effective.
- A contradicting claim at 0.88 (at/above `grill_dismiss_min`) becomes a
  counter-claim with its effective.
- The failure-pattern section is present and explicitly empty when no
  post-mortem source applies.
- Advancement is refused, with a count, while any grill entry is unaddressed.
