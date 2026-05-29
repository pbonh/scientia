---
skill: seed-proposal
---

# Rubric: seed-proposal

## Setup

Use the `tests/fixtures/wiki-basic` wiki (run `confidence.recompute_all` over a
copy first so claims carry `effective`). Run `seed-proposal` for topic
`entity-llm-wiki`. Save the produced `proposal.md` to `output.md` here.

## Expected behavior

- `context-from-kg` cites the two high-confidence claims with their `effective`
  shown inline (both ≥ 0.70 after recompute).
- `candidate-problems` surfaces the open question
  `question-when-does-the-wiki-drift`.
- `constraints-from-kg` is present but empty, with the explicit empty-note (the
  fixture has no constraint claims).

## Required mentions (output MUST contain)

- ## Context (from KG)
- claim-rag-rediscovers-knowledge
- effective
- ## Candidate Problems
- question-when-does-the-wiki-drift
- ## Constraints (from KG)
- KG provided no high-confidence content

## Forbidden mentions (output MUST NOT contain)

- TODO fill in context
- (omit this section)

## Pass criteria

Every KG-sourced subsection is present (none silently omitted), high-confidence
claims appear in context with `effective` inline, the open question appears as a
candidate problem, and the empty constraints subsection carries the empty-note.
