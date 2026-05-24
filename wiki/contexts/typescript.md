---
title: "TypeScript"
type: context
tags: [context, bounded-context, supporting]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

The TypeScript language and toolchain as a concrete realization of
static typing, anchored in *Essential TypeScript 5* (Adam Freeman):
annotations and inference, the union/intersection/literal type
machinery, guards and assertions, generics and conditional types,
declaration files, `tsconfig`, JSX, and the structural type system.
Owns TS-syntax-specific vocabulary. Stands in a Shared-Kernel
relationship to [[contexts/type-theory]] (the language-agnostic source)
— see [[context-maps/language-and-types]].

## Subdomain Classification

**Supporting.** TypeScript is one concrete typed language scientia's
agents may work in (and the language of the Pi ecosystem's extensions),
but it is reference craft, not a differentiator.

## In-Scope Concepts

- [[concepts/static-typing-in-typescript]]
- [[concepts/type-annotations]]
- [[concepts/type-inference]]
- [[concepts/type-unions]]
- [[concepts/type-assertions]]
- [[concepts/type-guards]]
- [[concepts/unknown-type]]
- [[concepts/nullable-types]]
- [[concepts/type-aliases]]
- [[concepts/literal-value-types]]
- [[concepts/type-intersections]]
- [[concepts/shape-types]]
- [[concepts/interfaces-in-typescript]]
- [[concepts/typescript-generics]]
- [[concepts/generic-constraints]]
- [[concepts/conditional-types]]
- [[concepts/decorators-in-typescript]]
- [[concepts/declaration-files]]
- [[concepts/tsconfig-configuration]]
- [[concepts/jsx-in-typescript]]
- [[concepts/structural-typing]]
- [[concepts/tuples-in-typescript]]
- [[concepts/enums-in-typescript]]

## In-Scope Entities

- [[entities/typescript]]
- [[entities/node-js]]
- [[entities/npm]]
- [[entities/adam-freeman]]
- [[entities/angular]]
- [[entities/react]]

## Ubiquitous Language (Glossary)

- **Type annotation** — explicit `: T` syntax declaring a value's type.
- **Type inference** — the compiler deriving a type without annotation.
- **Structural typing** — compatibility judged by shape, not by name.
- **Union / intersection type** — `A | B` and `A & B` compositions.
- **Type guard** — a runtime check that narrows a value's static type.
- **Generic constraint** — `<T extends U>` bounding a type parameter.
- **Conditional type** — `T extends U ? X : Y` type-level branching.
- **Declaration file** — `.d.ts` describing the types of JS code.
- **tsconfig** — the compiler configuration file.

## False Cognates with Adjacent Contexts

- **Duplicate concepts with [[contexts/type-theory]]:**
  `typescript-generics`↔`higher-kinded-types`/generics,
  `enums-in-typescript`↔`algebraic-data-types`,
  `structural-typing`↔`nominal-subtyping`. The two contexts share a
  kernel of type concepts; these pages are the language-specific vs
  language-agnostic faces of the same ideas. See
  [[context-maps/language-and-types]].
- **"generics"** also collides with
  [[concepts/rust-generics]] in
  [[contexts/rust-systems-programming]] — three takes on parametric
  polymorphism.
- **"enum"** (`enums-in-typescript`) vs [[concepts/rust-enum]]: TS enums
  are nominal integer/string sets; Rust enums are sum types. A classic
  false cognate.
- **"decorators-in-typescript"** vs [[concepts/decorator-pattern]] in
  [[contexts/type-theory]] / [[contexts/software-design-principles]]:
  language feature vs design pattern.
- **"interface"** (`interfaces-in-typescript`) vs Rust *traits*
  ([[concepts/rust-traits]]) — both name a contract, different
  semantics.

## Sources

- [[summaries/essential-typescript-5-book]]
