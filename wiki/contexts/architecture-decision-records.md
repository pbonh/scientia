---
title: "Architecture Decision Records"
type: context
tags: [context, bounded-context, core]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Capturing significant architectural decisions as immutable,
sequence-numbered records — their context, the decision, consequences,
and supersession chain. This context owns the *decision* vocabulary
(*ADR, ASR, Y-statement, status, supersession, decision log*) plus the
design artifacts that distill which decisions are significant (C4
diagrams, design interrogation). It shares the **intent-driven-schema**
kernel with [[contexts/spec-driven-development]] but its language is
about *recording why*, not *specifying what*.

## Subdomain Classification

**Core.** ADRs are the decision substrate of the intent phase. Scientia
treats in-force ADRs (resolved via supersession walk) as first-class
manifest inputs that every spec and task must honor. Differentiating and
invested.

## In-Scope Concepts

- [[concepts/architectural-decision]]
- [[concepts/architecturally-significant-requirement]]
- [[concepts/architectural-decision-record]]
- [[concepts/decision-log]]
- [[concepts/architectural-knowledge-management]]
- [[concepts/y-statement-format]]
- [[concepts/madr]]
- [[concepts/c4-model]]
- [[concepts/design-interrogation]]

## In-Scope Entities

- [[entities/adr-github-org]]
- [[entities/michael-nygard]]
- [[entities/michael-keeling]]
- [[entities/mark-richards]]

## Ubiquitous Language (Glossary)

- **ADR (Architectural Decision Record)** — an immutable, numbered
  document recording one decision and its consequences.
- **ASR (Architecturally Significant Requirement)** — a requirement
  whose satisfaction forces an architectural decision.
- **Y-statement** — the terse "In the context of … we decided … to
  achieve … accepting …" decision format.
- **Status** — an ADR's lifecycle marker: proposed / accepted /
  deprecated / superseded.
- **Supersession** — replacing a decision by writing a *new* ADR that
  supersedes the old; accepted ADRs are never edited.
- **Decision log** — the ordered set of all ADRs; the project's
  architectural memory.
- **MADR** — Markdown Any Decision Records, a popular ADR template.
- **C4 model** — Context/Container/Component/Code diagram levels used in
  `design.md` to frame decisions.
- **Design interrogation** — depth-first questioning (grilling) that
  stress-tests a decision before it is recorded.

## False Cognates with Adjacent Contexts

- **"decision"** here is an architectural record; in
  [[contexts/llm-reasoning]] a *decision* is a model's inference-time
  choice — unrelated.
- **"context"** is overloaded: here the ADR's *In the context of…*
  preamble; in [[contexts/autonomous-agent-orchestration]] and
  [[contexts/coding-agent-platform]] *context* means the LLM context
  window. See [[context-maps/intent-shared-kernel]].
- **"status"** here is an ADR lifecycle value; in
  [[contexts/autonomous-agent-orchestration]] *status* is a kanban task
  state (todo/running/blocked/done). The emit policy maps ADR-status →
  kanban collaboration pattern — see [[context-maps/scientia-pipeline]].

## Sources

- [[summaries/adr-github-home]]
- [[summaries/spec-driven-development-with-adr]]
