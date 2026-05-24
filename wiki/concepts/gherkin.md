---
title: "Gherkin"
type: concept
tags: [concept, bdd, specification, testing, behaviour-driven]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/skills.md", "raw/intent-driven-template/intent-driven-schema.md"]
confidence: high
---

## Definition

**Gherkin** is a structured, near-natural-language notation for describing
software behaviour as *executable examples*. A specification is organized into a
`Feature` containing one or more `Scenario`s, and each scenario states behaviour
in `Given` / `When` / `Then` steps — a known starting state, a triggering event,
and an observable outcome. Gherkin is the language of Behaviour-Driven Development
(BDD) and Cucumber-style tooling. The [[entities/intent-driven-template]] bundles a
`gherkin-authoring` skill and its [[concepts/intent-driven-schema|`intent-driven`
schema]] requires behaviour specs to be written in Gherkin style.

## How It Works

Behaviour is expressed with a small vocabulary of keywords:

| Construct | Use for | Syntax note |
|-----------|---------|-------------|
| `Feature:` | One high-level capability | Requires `:` |
| `Rule:` | Group scenarios under one business rule | Requires `:` |
| `Scenario:` / `Example:` | One concrete example | Requires `:` |
| `Background:` | Short shared context | One per `Feature`/`Rule` |
| `Scenario Outline:` + `Examples:` | Same behaviour, varied data | Uses `<parameter>` placeholders |
| `Given` | Known state / precondition | No `:` |
| `When` | One meaningful event | No `:` |
| `Then` | Observable outcome | No `:` |
| `And` / `But` | Continue the previous step type | No `:` |
| `@tag`, `#`, `"""`, `\|` | Tag, comment, Doc String, Data Table | — |

The core authoring discipline: **use the language domain experts use**, keeping
UI clicks, HTTP calls, database rows, queues, and mocks out of the scenario and
inside the step definitions. `Given` puts the system in a known state (no user
interaction), `When` describes exactly one event, and `Then` asserts an outcome
visible to a user or external system — not hidden database state, unless that
state *is* the external contract. Scenarios stay concrete and short (typically 3-5
steps).

Gherkin can live in standalone `.feature` files or be embedded in Markdown. When
embedded, the surrounding wrapper (fences, headings, prose) is preserved and only
the Gherkin region is edited. The `intent-driven` schema relies on exactly this:
OpenSpec Markdown headings (`### Requirement:`, `#### Scenario:`) form the merge
wrapper while the requirement and scenario bodies are written in Gherkin
`GIVEN`/`WHEN`/`THEN` — and the schema deliberately does **not** emit `.feature`
files.

## Key Parameters

- **Smallest expressive structure**: prefer a plain `Scenario` over a
  `Scenario Outline`; use an outline only when examples differ solely by data.
- **Two-space indentation** (unless preserving existing style).
- **Short `Background`**: if it grows beyond ~4 lines, raise the abstraction or
  split by `Rule`/`Feature`.
- **Escaping in Data Tables**: escape `|` as `\|`, newline as `\n`, backslash as
  `\\`.

## When To Use

- Capturing acceptance criteria as concrete, testable examples a domain expert can
  read.
- Authoring the behaviour specs in the [[concepts/intent-driven-schema|intent-driven]]
  (or `behaviour-driven`) OpenSpec schema.
- Reviewing or improving existing BDD scenarios for clarity and observability.

## Risks & Pitfalls

- **Implementation leakage** — `Given I click the checkout button` belongs in
  `When`/step definitions; `Then an order row exists in the database` should be an
  observable result like an order confirmation.
- **Missing/extra colons** — `Feature` and `Scenario` titles require a `:`; step
  keywords do not take one.
- **Reusing step text across keywords** — Cucumber ignores `Given`/`When`/`Then`
  when matching step definitions, so identical text under different keywords
  collides.
- **Returning only the fenced block** when the input was Markdown — preserve the
  wrapper and change only the Gherkin.
- **Long UI-action scripts and large `Background`s** — raise the abstraction; keep
  the scenario about the behaviour.

## Related Concepts

- [[concepts/intent-driven-schema]] — the schema that mandates Gherkin-style specs
- [[concepts/test-driven-development]] — the test-first discipline BDD examples support
- [[concepts/delta-spec]] — the OpenSpec spec representation Gherkin bodies live inside
- [[concepts/spec-adr-dual-representation]] — Gherkin specs are the "what" half

## Sources

- [gherkin-authoring skill](https://github.com/intent-driven-dev/intent-driven-template/tree/main/.agents/skills/gherkin-authoring) (`raw/intent-driven-template/skills.md`)
- [intent-driven schema spec format](https://github.com/intent-driven-dev/intent-driven-template/tree/main/openspec/schemas/intent-driven) (`raw/intent-driven-template/intent-driven-schema.md`)
