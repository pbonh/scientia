---
title: "Shell & Data Pipeline"
type: context
tags: [context, bounded-context, generic]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Nushell as a structured-data shell: pipelines that pass typed tables
rather than byte streams, static parsing, scoped/immutable environment
and variables, a typed data model, custom commands, modules, the plugin
system, and dataframe analytics. Owns the *structured-pipeline*
vocabulary.

## Subdomain Classification

**Generic.** A shell is commodity tooling. Nushell's structured-data
model is interesting reference knowledge but not something scientia
builds; it is replaceable by any shell for scientia's purposes.

## In-Scope Concepts

- [[concepts/nushell-structured-pipeline]]
- [[concepts/nushell-implicit-return]]
- [[concepts/nushell-static-parsing]]
- [[concepts/nushell-scoped-environment]]
- [[concepts/nushell-immutable-variables]]
- [[concepts/nushell-data-types]]
- [[concepts/nushell-custom-command]]
- [[concepts/nushell-module-system]]
- [[concepts/nushell-plugin-system]]
- [[concepts/nushell-dataframe]]

## In-Scope Entities

- [[entities/nushell]]
- [[entities/reedline]]
- [[entities/polars]]
- [[entities/nana]]

## Ubiquitous Language (Glossary)

- **Structured pipeline** — a pipeline whose stages pass typed values
  (tables, records) instead of raw text.
- **Static parsing** — parsing the whole script before execution,
  enabling early error detection.
- **Scoped environment** — environment changes confined to a block's
  scope rather than leaking globally.
- **Immutable variable** — a binding that cannot be reassigned after
  declaration.
- **Custom command** — a user-defined function extending the shell's
  verb set.
- **Module** — a unit grouping commands/env for reuse.
- **Dataframe** — a columnar, analytics-oriented table (Polars-backed).
- **Plugin** — a separate process extending Nushell's command set.

## False Cognates with Adjacent Contexts

- **"plugin"** (`nushell-plugin-system`) collides with zellij
  WebAssembly plugins ([[contexts/terminal-workspace]]) and
  `hermes-plugin-system`. See [[context-maps/terminal-tooling]].
- **"immutable variable"** here is a near-cognate of *immutability* in
  [[contexts/type-theory]] and Rust's binding immutability — same
  principle, shell-specific framing.
- **"pipeline"** here (shell data pipeline) is unrelated to the
  *artifact-dependency / impl→review→integrate pipeline* in
  [[contexts/spec-driven-development]] and
  [[contexts/autonomous-agent-orchestration]].
- **"dataframe"** (Polars) overlaps conceptually with analytics
  tooling but has no cognate elsewhere in the wiki.

## Sources

- [[summaries/nushell-book]]
