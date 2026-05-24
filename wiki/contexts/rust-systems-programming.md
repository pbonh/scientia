---
title: "Rust Systems Programming"
type: context
tags: [context, bounded-context, supporting]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

The Rust language and its systems-programming model: ownership,
borrowing, lifetimes, the type system (structs, enums, traits,
generics), fearless concurrency, unsafe, macros, smart pointers, and the
Cargo build/packaging/registry toolchain. Also home to the Rust
error-handling patterns ingested via zellij (anyhow/miette/thiserror,
fatal vs non-fatal propagation, panic handling) because they share the
Rust `Result`/`?`/panic vocabulary. The *application* of Rust to a
terminal multiplexer lives in [[contexts/terminal-workspace]].

## Subdomain Classification

**Supporting.** Rust is a likely implementation language for scientia's
own components and a recurring subject of worker tasks, but the language
itself is engineering substrate, not a scientia differentiator.

## In-Scope Concepts

- [[concepts/rust-ownership]]
- [[concepts/rust-borrowing]]
- [[concepts/rust-slice-type]]
- [[concepts/rust-struct]]
- [[concepts/rust-enum]]
- [[concepts/rust-pattern-matching]]
- [[concepts/rust-generics]]
- [[concepts/rust-traits]]
- [[concepts/rust-lifetimes]]
- [[concepts/rust-error-handling]]
- [[concepts/rust-closure]]
- [[concepts/rust-iterator]]
- [[concepts/rust-concurrency]]
- [[concepts/rust-unsafe]]
- [[concepts/rust-macros]]
- [[concepts/rust-smart-pointers]]
- [[concepts/rust-cargo-workspaces]]
- [[concepts/rust-modules]]
- [[concepts/error-propagation]]
- [[concepts/error-context]]
- [[concepts/fatal-error-handling]]
- [[concepts/non-fatal-error-handling]]
- [[concepts/panic-handling]]
- [[concepts/custom-error-types]]
- [[concepts/cargo-registry]]
- [[concepts/release-simulation]]

## In-Scope Entities

- [[entities/rust]]
- [[entities/cargo]]
- [[entities/crates-io]]
- [[entities/ktra]]
- [[entities/anyhow]]
- [[entities/miette]]
- [[entities/thiserror]]

## Ubiquitous Language (Glossary)

- **Ownership** — the rule that each value has a single owner
  responsible for freeing it.
- **Borrowing** — taking a reference (`&`/`&mut`) without taking
  ownership, governed by the borrow checker.
- **Lifetime** — the compile-time scope for which a reference is valid.
- **Trait** — a named set of methods a type can implement; Rust's
  interface/polymorphism mechanism.
- **Enum** — a sum type whose variants may carry data, matched with
  `match`.
- **`Result` / `?`** — the fallible-return type and the propagation
  operator; the spine of Rust error handling.
- **Panic** — an unrecoverable error that unwinds the stack; distinct
  from recoverable `Result` errors.
- **Fearless concurrency** — the guarantee that data races are caught at
  compile time.
- **Cargo registry** — a package index (crates.io, or self-hosted via
  ktra) Cargo publishes/fetches from.

## False Cognates with Adjacent Contexts

- **"enum" / "generics" / "closure" / "iterator"** all have
  language-specific pages here that duplicate ideas in
  [[contexts/type-theory]] and [[contexts/typescript]] — see
  [[context-maps/language-and-types]].
- **"trait"** vs TypeScript *interface* ([[concepts/interfaces-in-typescript]])
  vs an ADT-style contract — same role, different semantics.
- **"error handling"** here (Rust `Result`/anyhow/miette) is a false
  cognate of [[concepts/ansible-error-handling]] in
  [[contexts/infrastructure-automation]] — one is type-level, the other
  is declarative playbook control flow.
- **"registry"** (`cargo-registry`/crates.io) vs *registry* in
  [[contexts/autonomous-agent-orchestration]]
  (`hermes-tool-registry`) — both lookup tables, unrelated domains.

## Sources

- [[summaries/rust-book]]
- [[summaries/zellij-error-handling]]
- [[summaries/zellij-release-process]]
