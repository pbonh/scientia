---
title: "Software Design Principles"
type: context
tags: [context, bounded-context, supporting]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

The craft of structuring maintainable code: separation of concerns,
abstraction, encapsulation, decomposition, coupling/cohesion, testing
discipline, and the object-oriented design vocabulary (inheritance,
Liskov substitution, composition-over-inheritance, abstract base
classes). Anchored in *Practices of the Python Pro*; the language is
Python-flavored but principle-level. Owns the *code-quality* vocabulary
(complexity metrics, test pyramid).

## Subdomain Classification

**Supporting.** These principles shape the quality of code scientia's
implementer workers produce and the standards reviewers enforce, but
they are general engineering craft, not a scientia differentiator.

## In-Scope Concepts

- [[concepts/separation-of-concerns]]
- [[concepts/abstraction]]
- [[concepts/encapsulation]]
- [[concepts/decomposition]]
- [[concepts/big-o-notation]]
- [[concepts/lazy-evaluation]]
- [[concepts/test-driven-development]]
- [[concepts/test-pyramid]]
- [[concepts/command-pattern]]
- [[concepts/extensibility]]
- [[concepts/inversion-of-control]]
- [[concepts/loose-coupling]]
- [[concepts/inheritance]]
- [[concepts/liskov-substitution-principle]]
- [[concepts/cyclomatic-complexity]]
- [[concepts/abstract-base-class]]
- [[concepts/composition-over-inheritance]]

## In-Scope Entities

- [[entities/dane-hillard]]
- [[entities/pytest]]
- [[entities/sqlite]]
- [[entities/requests]]
- [[entities/manning-publications]]

## Ubiquitous Language (Glossary)

- **Separation of concerns** — partitioning a system so each part has
  one responsibility.
- **Abstraction** — exposing intent while hiding mechanism to reduce
  cognitive load.
- **Encapsulation** — bundling data with the operations that guard it.
- **Decomposition** — breaking a problem into smaller, independently
  reasoned parts.
- **Loose coupling** — minimizing how much one module depends on
  another's internals.
- **Inversion of control** — handing dependency wiring to a caller or
  container rather than constructing inline.
- **Test pyramid** — the ratio guidance: many unit, fewer integration,
  fewest end-to-end tests.
- **Cyclomatic complexity** — a count of independent paths through code;
  a maintainability metric.
- **Liskov substitution** — subtypes must be usable wherever their base
  type is expected.

## False Cognates with Adjacent Contexts

- **"command pattern"** here (`command-pattern`) vs the
  *command/CQRS*-flavored patterns elsewhere; here it is the GoF design
  pattern. The functional-flavored sibling patterns (visitor, strategy,
  decorator, iterator) live in [[contexts/type-theory]] — see
  [[context-maps/language-and-types]].
- **"inheritance" / "abstract base class" / "composition over
  inheritance"** overlap with OO concepts in [[contexts/type-theory]]
  and [[contexts/typescript]]; here they are framed as *design* advice,
  there as *type-system* mechanics.
- **"extensibility"** (`extensibility`) is a near-duplicate of
  [[contexts/type-theory]]'s decorator/strategy extensibility and the
  plugin-system extensibility in several tool contexts.
- **"sqlite"** as an entity here (a Python data store in the book) also
  underpins [[contexts/autonomous-agent-orchestration]]'s `kanban.db`
  and session storage — same engine, different role.

## Sources

- [[summaries/practices-of-the-python-pro]]
