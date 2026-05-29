---
name: scientia-seed-proposal
description: Generates a proposal artifact pre-populated from the KG. Produces four subsections — context-from-kg, prior-art-from-kg, candidate-problems, constraints-from-kg — each citing the wiki claims it draws from with their effective confidence shown inline. This is the novel seam where the knowledge graph supplies the problem, not just the answer. Activate when starting a new change, optionally with a topic hint (a string or an Entity page id).
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+
metadata:
  stage: seed
  version: "1.0"
---

# scientia-seed-proposal

Query the wiki and emit `proposals/<change-id>/proposal.md` pre-populated with
KG-sourced subsections. Confidence is the gate: high-confidence claims become
context and prior art; **low-confidence and contradicted regions become
candidate problems** — inverting the usual flow where a human supplies the
problem.

## Inputs

- `<change-id>` (controller-generated).
- Optional topic hint: a free string or an Entity page id.

## Outputs

- `proposals/<change-id>/proposal.md`, rendered from the `proposal` template via
  `scientia.templates.render_to_file("proposal", paths.proposal_path(cid), ...)`.

## Subsections and their rules

Resolve the topic to an entity, then traverse its neighborhood with
`scientia.wiki.neighbors(topic_page, wiki_dir, hops=2)`. Read each claim's
`confidence.effective` (already recomputed; if you suspect staleness, the
controller will have run `scientia-audit-wiki` first). Every cited claim is an inline
wiki-link with its `effective` shown, e.g.
`- [[claim-x | supports]] (effective 0.85)`.

1. **context-from-kg** — claims with `effective >= thresholds.proposal_seed_min`
   (0.70) AND within 2 hops of the topic entity.
2. **prior-art-from-kg** — claims sourced from at least one Source page tagged
   `kind: publication`. Relaxed floor `thresholds.prior_art_floor` (0.60) to
   broaden the related-work set.
3. **candidate-problems** — (i) low-confidence claims
   `effective < thresholds.low_confidence_floor` (0.45), (ii) claims with active
   `contradicts` edges, (iii) Question pages within 2 hops. Present each as a
   problem statement citing its `effective`.
4. **constraints-from-kg** — claims with `kind: constraint` frontmatter, or at
   the end of a `refines` chain from a constraints-root entity.

Add your authoring layer (`# Why`, `## Proposed Change`, `## Open Questions`) on
top of the KG-sourced subsections; preserve every provenance link.

## Decision rules

- Inclusion/exclusion is strictly by threshold + hop distance — a claim at 0.55
  with `proposal_seed_min` 0.70 does **not** appear in context.
- A publication-sourced claim at 0.63 **does** appear in prior art (relaxed
  floor 0.60).
- Use `scientia.paths` for all paths; read thresholds from `config.yaml`.

## Low-confidence handling (mode key: `seed_proposal`, default `autonomous`)

- `autonomous`: if no claim qualifies for a subsection, emit it **present but
  empty** with an explicit note —
  `_KG provided no high-confidence content for this subsection._` Never silently
  omit a subsection.
- `pause_and_ask`: emit `question-for-operator.md` asking for a tighter topic
  hint.

## Acceptance behavior (spec: kg-seed-proposal)

- A neighborhood claim at 0.85 with `proposal_seed_min` 0.70 is cited in
  context-from-kg with its effective shown inline.
- A claim at 0.55 is excluded from context.
- A claim at 0.32 (below `low_confidence_floor`) is surfaced as a candidate
  problem citing its effective.
- A publication-sourced claim at 0.63 is cited in prior-art (floor 0.60).
- An empty subsection is emitted with the explicit empty-note in autonomous mode.
