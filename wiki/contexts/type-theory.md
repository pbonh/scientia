---
title: "Type Theory"
type: context
tags: [context, bounded-context, supporting]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Language-agnostic type-system theory and type-driven design, anchored in
*Programming with Types* (Vlad Riscutia): algebraic data types, type
safety, the type lattice (unit/bottom/top types), variance, subtyping,
and the functional abstractions (functor, monad, higher-kinded types)
plus the functional design patterns expressed through them. Owns the
*conceptual* type vocabulary; its concrete realization in a specific
language lives in [[contexts/typescript]] (a Shared-Kernel relationship —
see [[context-maps/language-and-types]]).

## Subdomain Classification

**Supporting.** Type-driven design informs how scientia's workers model
domains and avoid whole classes of bugs, but it is foundational
engineering theory, not a scientia differentiator.

## In-Scope Concepts

- [[concepts/algebraic-data-types]]
- [[concepts/primitive-obsession]]
- [[concepts/type-safety]]
- [[concepts/first-class-functions]]
- [[concepts/closure]]
- [[concepts/map-filter-reduce]]
- [[concepts/visitor-pattern]]
- [[concepts/strategy-pattern]]
- [[concepts/decorator-pattern]]
- [[concepts/state-machine]]
- [[concepts/iterator-pattern]]
- [[concepts/promises]]
- [[concepts/async-await]]
- [[concepts/short-circuit-evaluation]]
- [[concepts/unit-type]]
- [[concepts/bottom-type]]
- [[concepts/top-type]]
- [[concepts/nominal-subtyping]]
- [[concepts/variance]]
- [[concepts/functor]]
- [[concepts/monad]]
- [[concepts/higher-kinded-types]]
- [[concepts/immutability]]
- [[concepts/composability]]

## In-Scope Entities

- [[entities/vlad-riscutia]]

## Ubiquitous Language (Glossary)

- **Algebraic data type** — a composite type built by product (struct)
  and sum (union/enum) construction.
- **Type safety** — the guarantee that well-typed programs cannot reach
  certain classes of error.
- **Unit / bottom / top type** — the lattice extremes: the single-value
  type, the uninhabited type, and the universal supertype.
- **Variance** — how subtyping of components relates to subtyping of
  containers (covariant/contravariant/invariant).
- **Functor / monad** — abstractions for mapping over and sequencing
  computations in a type-preserving way.
- **Higher-kinded type** — a type that abstracts over type constructors.
- **First-class function / closure** — functions as values that capture
  their defining scope.
- **Composability** — designing types and functions to combine cleanly.
- **Primitive obsession** — the antipattern of modeling domain values
  with bare primitives instead of dedicated types.

## False Cognates with Adjacent Contexts

- **Duplicate concepts with [[contexts/typescript]]:** *generics*,
  *enums*, *structural typing*, *type unions* exist as concept pages in
  both contexts — here language-agnostic, there TS-specific. These are
  the planned cost of keeping the two contexts separate (Shared Kernel).
  See [[context-maps/language-and-types]].
- **Duplicate concepts with [[contexts/rust-systems-programming]]:**
  `closure`↔`rust-closure`, `iterator-pattern`↔`rust-iterator`,
  `algebraic-data-types`↔`rust-enum`, `immutability`↔Rust ownership
  immutability — same ideas, language-specific pages.
- **"decorator-pattern"** here (functional/GoF) vs
  [[concepts/decorators-in-typescript]] (TS language feature) vs
  [[concepts/decorator-pattern]]'s use in
  [[contexts/software-design-principles]] — three senses of "decorator".
- **"state machine"** here is a type-driven modeling technique;
  unrelated to the kanban task *state* transitions in
  [[contexts/autonomous-agent-orchestration]].

## Sources

- [[summaries/programming-with-types-book]]
