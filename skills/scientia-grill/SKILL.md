---
name: scientia-grill
description: Depth-first design interrogation. Interview the user about every aspect of a plan or design, asking one question per turn, walking down each branch of the decision tree, resolving dependencies one-by-one, until shared understanding is reached. Use when stress-testing a plan, drafting an OpenSpec proposal or ADR, or whenever the user says "grill me" or "interview me." Do not use for free-form ideation — this skill narrows; use a separate brainstorming workflow to widen.
license: MIT
metadata:
  bundle: scientia
  role: utility
---

# scientia-grill

Interview the user relentlessly about every aspect of the plan or design
in front of you until you reach shared understanding. Walk down each
branch of the decision tree. Resolve dependencies between decisions
one-by-one. For each question, **provide your recommended answer**. Ask
the questions **one at a time**. If a question can be answered by
exploring the codebase, **explore the codebase instead** of asking.

## The four rules

1. **One question per turn.** Never batch questions. Depth-first
   traversal only works if the user can answer each branch in isolation
   before the next one opens.
2. **Recommend an answer with every question.** Surface your own best
   guess so the user can react to a concrete option rather than
   free-associate into the void.
3. **Codebase over question.** Anything answerable by reading code or
   docs is answered there, not asked. Questions are reserved for
   genuine ambiguity.
4. **Park don't loop.** If the user says *"I don't know yet"*, *"park
   this"*, or *"skip"*, drop the question into an internal
   `## Open Questions` list and move on. Never block on a parked item.

## Format per question

When presenting a question, structure it as:

- **The decision** in one sentence.
- **2–4 concrete options** (a, b, c, …), each described in 1–3 lines
  with its tradeoffs.
- **Your recommendation** with 2–5 reasons.
- One closing line inviting the user to choose, push back, or park.

## When to declare done

When every branch of the decision tree has been resolved (chosen,
parked, or made moot by an earlier choice), produce a structured
summary of the agreed design and stop asking. The summary should be
suitable to lift directly into a `proposal.md` or `design.md`.

## When called from other scientia skills

- `scientia-intent-proposal` invokes this skill to interrogate the
  *why* and *what changes* before drafting `proposal.md`.
- `scientia-intent-adr` may invoke this skill to stress-test a
  significant decision before writing the immutable ADR body.
- `scientia-wiki-grill` invokes this skill against the wiki itself to
  surface knowledge gaps relevant to a forthcoming change.

The invoking skill provides the *target* (a proposal draft, an ADR
draft, a manifest core, a wiki slice). This skill provides the *method*.
