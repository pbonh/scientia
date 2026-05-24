---
title: "Editor Extensibility"
type: context
tags: [context, bounded-context, generic]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Neovim as a programmable editor: Lua scripting, the built-in LSP client,
Tree-sitter syntax integration, async jobs/channels, and the diagnostic
framework. Owns the *editor-extension* vocabulary (buffers, LSP clients,
parsers, async jobs).

## Subdomain Classification

**Generic.** A text editor is commodity tooling. Neovim's extensibility
model is reference knowledge; scientia neither builds nor differentiates
on it.

## In-Scope Concepts

- [[concepts/nvim-lua-scripting]]
- [[concepts/nvim-lsp-client]]
- [[concepts/nvim-treesitter-integration]]
- [[concepts/nvim-async-jobs]]
- [[concepts/nvim-diagnostic-framework]]

## In-Scope Entities

- [[entities/neovim]]
- [[entities/tree-sitter]]
- [[entities/nvim-lspconfig]]
- [[entities/nvim-treesitter]]
- [[entities/luajit]]

## Ubiquitous Language (Glossary)

- **Lua scripting** — Neovim's embedded configuration/extension
  language (run on LuaJIT).
- **LSP client** — Neovim's built-in consumer of Language Server
  Protocol servers for completion, diagnostics, navigation.
- **Tree-sitter** — an incremental parser producing concrete syntax
  trees for highlighting and structural editing.
- **Async job** — a non-blocking external process managed over a
  channel.
- **Diagnostic** — a structured problem (error/warning) surfaced from an
  LSP server or linter.

## False Cognates with Adjacent Contexts

- **"diagnostic"** here (LSP problem report) is a near-cognate of
  zellij/Rust *error reporting* ([[contexts/rust-systems-programming]])
  and miette's *diagnostics* — same English word, different layer.
- **"LSP" / "language server"** is editor-specific and has no cognate
  elsewhere, but the *parsing* it relies on (Tree-sitter) overlaps with
  Nushell's [[concepts/nushell-static-parsing]] conceptually.
- **"async job / channel"** overlaps conceptually with
  [[concepts/async-await]] / [[concepts/promises]] in
  [[contexts/type-theory]] and Rust concurrency — all concurrency, none
  the same API.

## Sources

- [[summaries/nvim-core-docs]]
