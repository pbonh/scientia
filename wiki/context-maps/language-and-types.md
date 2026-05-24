---
title: "Languages & Type Systems"
type: context-map
tags: [context-map]
contexts: [type-theory, typescript, rust-systems-programming, software-design-principles]
created: 2026-05-24
updated: 2026-05-24
---

## Relationships

- **Type Theory ↔ TypeScript** — *Shared Kernel.* Type Theory is the
  language-agnostic source; TypeScript is a concrete realization. They
  share a kernel of type vocabulary (generics, variance, unions, ADTs),
  kept as separate contexts by explicit decision (2026-05-24) — at the
  cost of the duplicate-concept pairs listed below.
- **Type Theory → Rust** — *Supplier.* Rust's type system instantiates
  many Type-Theory ideas (sum types → `enum`, traits → bounded
  polymorphism, ownership → affine types). Rust's pages are
  language-specific.
- **Software Design Principles ↔ Type Theory** — *Partnership.* The GoF
  patterns split by flavor: `command-pattern` (Software Design,
  Python-OO) vs visitor/strategy/decorator/iterator/state-machine (Type
  Theory, functional). OO-design concepts (inheritance, LSP,
  composition-over-inheritance) sit in Software Design but lean on
  Type-Theory subtyping.

## False Cognates

- **"enum"** — `enums-in-typescript` (nominal int/string sets) vs
  [[concepts/rust-enum]] (sum types) vs [[concepts/algebraic-data-types]]
  (the general construct). Same keyword, materially different semantics.
- **"interface"** — `interfaces-in-typescript` (structural shape) vs
  [[concepts/rust-traits]] (nominal, with default methods). Both
  "contracts", different rules.
- **"decorator"** — `decorators-in-typescript` (language feature) vs
  [[concepts/decorator-pattern]] (design pattern). Unrelated mechanisms.
- **"error handling"** — Rust `Result`/anyhow/miette is *not* the
  Ansible block/rescue sense ([[contexts/infrastructure-automation]]);
  noted here because Rust is on this axis.

## Duplicate Concepts

Planned duplicates from the Type-Theory/TypeScript split and the
language-specific Rust pages:

| Concept (agnostic) | TypeScript face | Rust face |
|---|---|---|
| generics / parametric polymorphism | [[concepts/typescript-generics]], [[concepts/generic-constraints]] | [[concepts/rust-generics]] |
| sum types | [[concepts/enums-in-typescript]] | [[concepts/rust-enum]] |
| structural vs nominal typing ([[concepts/nominal-subtyping]]) | [[concepts/structural-typing]] | (nominal via traits) |
| closures / first-class fns ([[concepts/closure]], [[concepts/first-class-functions]]) | (TS functions) | [[concepts/rust-closure]] |
| iteration ([[concepts/iterator-pattern]]) | — | [[concepts/rust-iterator]] |
| immutability ([[concepts/immutability]]) | — | (ownership/`let`) |

These are not errors to fix — they are the deliberate cost of three
language lenses on shared theory. Any future *merge* would require an
ADR.

## Open Questions

- If a fourth typed language is ingested, does the duplicate matrix grow
  linearly (acceptable) or signal that Type Theory should absorb the
  language-specific pages as sections? Revisit at next typed-language
  ingest.
- **manning-publications** publishes both *Practices of the Python Pro*
  (Software Design) and *Programming with Types* (Type Theory); assigned
  to Software Design, flagged spanning.
