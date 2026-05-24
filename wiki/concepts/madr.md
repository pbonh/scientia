---
title: "MADR (Markdown Architectural Decision Records)"
type: concept
tags: [concept, architecture, adr, documentation, template]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/skills.md", "raw/intent-driven-template/intent-driven-schema.md"]
confidence: medium
---

## Definition

**MADR** — Markdown Any/Architectural Decision Records — is a Markdown template
family for writing [[concepts/architectural-decision-record|ADRs]]. It standardizes
the sections of a decision record (status, context, considered options, decision,
consequences) so that records are uniform and machine-readable while staying
lightweight. The [[entities/intent-driven-template]]'s ADR skill offers MADR in two
sizes — **MADR-full** (detailed trade-off record) and **MADR-minimal** (concise
trade-off record) — and the [[concepts/intent-driven-schema|`intent-driven` schema]]
defaults its `adr` stage to the **MADR-short** template.

## How It Works

A MADR-style record captures one decision with a fixed skeleton. The minimal shape
demonstrated by the bundled ADR skill is:

```markdown
# ADR-012: Use PostgreSQL for Orders

## Status
Accepted

## Context
Orders need relational constraints, consistency, and reporting joins...

## Considered Options
- PostgreSQL: integrity, SQL reporting, familiar operations; migrations required.
- MongoDB: flexible schema; weaker fit for consistency and joins.

## Decision
We will use PostgreSQL because consistency, joins, and operational familiarity
matter more than schema flexibility.

## Consequences
- Positive: Integrity and reporting align with needs.
- Negative: Schema changes need migrations.
- Follow-up: Define migration practice.
```

MADR-full adds richer trade-off analysis (more detail per option, explicit quality
attributes) for high-stakes decisions, while MADR-minimal trims to the essential
sections. Both are alternatives to other ADR templates the skill offers — the
classic lightweight [Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions.html)
format, the one-sentence [[concepts/y-statement-format|Y-statement]], and a
project-specific `custom` template. The ADR skill records the chosen template in a
`preferences.md` `preferred-style` field so it is reused consistently across a
project.

## Key Parameters

| Variant | Use when |
|---------|----------|
| `madr-full` | Detailed trade-off record for a high-impact decision |
| `madr-minimal` / `madr-short` | Concise trade-off record (schema default) |
| `nygard` | Classic lightweight ADR |
| `y-statement` | One-sentence summary (see [[concepts/y-statement-format]]) |
| `custom` | Project-specific style |

Like all [[concepts/architectural-decision-record|ADRs]] under this workflow, a
MADR record is immutable once **Accepted** — a changed decision is recorded as a
new superseding ADR, never an edit (see the iron rule in
[[concepts/intent-driven-schema]]).

## When To Use

- When a project wants a uniform, Markdown-native ADR layout with explicit
  considered-options and consequences sections.
- As the default ADR format for the [[concepts/intent-driven-schema|intent-driven]]
  schema's `adr` stage.
- Choose **full** for decisions with many competing options and quality-attribute
  trade-offs; **minimal/short** for routine but still significant decisions.

## Risks & Pitfalls

- **Sales-pitch records** — listing only the chosen option defeats the format;
  MADR requires rejected options and negative consequences.
- **Over-formatting trivial decisions** — MADR-full on a reversible choice is
  friction; downgrade to minimal or skip the ADR.
- **Single-source provenance** — this page is drawn from the bundled ADR skill's
  template list and example rather than the upstream MADR specification, so exact
  field-by-field structure of MADR-full should be confirmed against
  [madr.org](https://adr.github.io/madr/); hence medium confidence.

## Related Concepts

- [[concepts/architectural-decision-record]] — the artifact MADR is a template for
- [[concepts/y-statement-format]] — a sibling one-line ADR template
- [[concepts/decision-log]] — the aggregate MADR records form
- [[concepts/intent-driven-schema]] — the schema that defaults to MADR-short
- [[concepts/architecturally-significant-requirement]] — what justifies writing one

## Sources

- [architectural-decision-records skill](https://github.com/intent-driven-dev/intent-driven-template/tree/main/.agents/skills/architectural-decision-records) (`raw/intent-driven-template/skills.md`)
- [intent-driven schema adr stage](https://github.com/intent-driven-dev/intent-driven-template/tree/main/openspec/schemas/intent-driven) (`raw/intent-driven-template/intent-driven-schema.md`)
- ADR template catalog: [adr.github.io](https://adr.github.io) / [MADR](https://adr.github.io/madr/)
