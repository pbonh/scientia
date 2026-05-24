---
title: "Intent Shared Kernel (Spec ↔ ADR)"
type: context-map
tags: [context-map]
contexts: [spec-driven-development, architecture-decision-records]
created: 2026-05-24
updated: 2026-05-24
---

## Relationships

- **Shared Kernel.** [[contexts/spec-driven-development]] and
  [[contexts/architecture-decision-records]] jointly depend on
  [[concepts/intent-driven-schema]] — the scientia OpenSpec schema that
  threads ADRs and specs through one change. Changes to the kernel
  require agreement from both contexts.
- The bridging concept pages
  [[concepts/spec-driven-with-adr-schema]],
  [[concepts/spec-adr-dual-representation]], and
  [[concepts/durable-artifacts-vs-scaffolding]] live in the Spec-Driven
  context but describe how specs and ADRs co-represent a change; ADR
  readers should follow them.
- [[concepts/c4-model]] (ADR context, used in `design.md`) feeds the
  decisions that ADRs record and that specs then reference — a
  supplier relationship from design framing to both artifacts.

## False Cognates

- **"design"** — Spec-Driven's `design.md` *stage* vs ADR's
  design-interrogation *activity* ([[concepts/design-interrogation]]).
  The stage produces the artifact; the activity stress-tests the
  decisions inside it.
- **"decision"** — appears in both, but in Spec-Driven it is informal
  ("we decided to spec X this way"), while in ADR it is the formal,
  numbered, immutable record.

## Duplicate Concepts

- None to merge. The contexts deliberately keep distinct vocabularies
  (*capability/scenario/delta* vs *ADR/ASR/Y-statement*); the only
  genuinely shared artifact is the kernel concept, which is singly
  defined.

## Open Questions

- Should [[concepts/spec-adr-dual-representation]] be promoted into the
  shared kernel itself (referenced by both contexts) rather than owned
  by Spec-Driven? Deferred — current single-context assignment holds
  until a change forces the question.
