---
title: "Design Interrogation (grill-me)"
type: concept
tags: [concept, design, decision-making, ai-assisted-development, workflow]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/skills.md"]
confidence: medium
---

## Definition

**Design interrogation** — popularized as the "grill-me" skill — is a depth-first
technique for stress-testing a plan or design by interviewing the author one
question at a time, walking down each branch of the decision tree and resolving
dependencies between decisions one-by-one, until shared understanding is reached.
The [[entities/intent-driven-template]] bundles a `grill-me` skill, and the same
practice is implemented in the scientia bundle's `scientia-grill` skill.

## How It Works

The interviewer drives the conversation rather than the author:

- **One question per turn.** Questions are asked individually, not as a batch, so
  each answer can shape the next question.
- **Depth-first traversal.** Walk down each branch of the design tree to its
  conclusion, resolving dependencies between decisions sequentially instead of
  skimming breadth-first.
- **Recommended answer attached.** For every question the interviewer proposes its
  own recommended answer, giving the author something concrete to accept, reject,
  or refine.
- **Explore before asking.** If a question can be answered by reading the codebase,
  the interviewer investigates instead of asking the author.

The result is a design whose assumptions, alternatives, and dependencies have been
made explicit — useful input to a design document, an
[[concepts/architectural-decision-record|ADR]], or an OpenSpec proposal.

## Key Parameters

- **Cadence**: strictly one question at a time.
- **Traversal order**: depth-first down each decision branch; dependencies resolved
  before dependents.
- **Stopping condition**: shared understanding of every branch, not a fixed
  question count.

## When To Use

- Before committing to a design or
  [[concepts/intent-driven-schema|intent-driven]] proposal, to surface unexamined
  assumptions and forced choices.
- When drafting an [[concepts/architectural-decision-record|ADR]] and you need the
  rejected options and trade-offs made explicit.
- Whenever an author asks to "grill me" or to have a plan stress-tested.

This narrows toward a decision; it is the opposite of free-form ideation, which
widens. Use a separate brainstorming practice when the goal is to generate options
rather than resolve them.

## Risks & Pitfalls

- **Premature narrowing** — interrogating before enough options exist can lock in a
  weak design; widen first if the option space is thin.
- **Interviewer bias** — always attaching a recommended answer can anchor the author
  toward the interviewer's preference; treat recommendations as proposals, not
  defaults.
- **Thin source** — the bundled skill is terse; the broader practice here is
  inferred from its description and the parallel `scientia-grill` skill, hence
  medium confidence.

## Related Concepts

- [[concepts/architectural-decision-record]] — interrogation feeds the rationale an ADR records
- [[concepts/architecturally-significant-requirement]] — the kind of decision worth grilling
- [[concepts/intent-driven-schema]] — the proposal/design stages this strengthens
- [[concepts/iterative-deliberation]] — a related reasoning loop that refines through iteration

## Sources

- [grill-me skill](https://github.com/intent-driven-dev/intent-driven-template/tree/main/.agents/skills/grill-me) (`raw/intent-driven-template/skills.md`)
- Inspired by [mattpocock/skills grill-me](https://github.com/mattpocock/skills/blob/main/skills/productivity/grill-me/SKILL.md)
