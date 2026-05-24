---
title: "Terminal Tooling (Multiplexer ↔ Shell ↔ Editor ↔ Finder)"
type: context-map
tags: [context-map]
contexts: [terminal-workspace, shell-and-data-pipeline, editor-extensibility, fuzzy-finder]
created: 2026-05-24
updated: 2026-05-24
---

## Relationships

- **Separate Ways.** The four generic terminal tools (zellij, nushell,
  neovim, television) coexist on a developer's terminal but do not share
  a ubiquitous language or integrate at the domain level. They are
  catalogued together only because they collide on surface vocabulary.
- All four are *downstream consumers* of
  [[contexts/rust-systems-programming]] in the sense that zellij,
  nushell, and television are Rust programs (neovim is C/Lua) — an
  implementation-language relationship, not a domain one.

## False Cognates

| Term | Terminal Workspace | Shell | Editor | Fuzzy Finder |
|---|---|---|---|---|
| **plugin** | WebAssembly module ([[concepts/plugin-system]]) | separate process ([[concepts/nushell-plugin-system]]) | Lua plugin (lspconfig, treesitter) | — |
| **session** | detachable multiplexer instance ([[concepts/session]]) | shell session | — | — |
| **channel** | — | — | async job channel ([[concepts/nvim-async-jobs]]) | search source ([[concepts/television-channel]]) |
| **template** | — | — | — | string-pipeline ([[concepts/television-template-system]]) |
| **pane / tab** | canonical multiplexer panes/tabs | — | editor windows/buffers (loose) | finder UI panes (loose) |
| **theme** | [[concepts/theme-system]] | — | colorscheme | — |

"session", "plugin", and "channel" are the load-bearing false cognates —
each means something genuinely different per tool.

## Duplicate Concepts

- **Parsing.** [[concepts/nvim-treesitter-integration]] (Tree-sitter
  CST) and [[concepts/nushell-static-parsing]] (whole-script parse)
  are both "parse before act" but are unrelated implementations — not a
  duplicate to merge.
- **"template".** television's string-pipeline templating is unrelated
  to `pi-prompt-template` ([[contexts/coding-agent-platform]]) and
  Ansible Jinja2 ([[contexts/infrastructure-automation]]); cross-listed
  here for the reader chasing "template".

## Open Questions

- Television's [[entities/string-pipeline]] and
  [[entities/nucleo-matcher]] are Rust crates; should the
  implementation-language tie to
  [[contexts/rust-systems-programming]] be a first-class relationship or
  remain incidental? Treated as incidental (generic tools), revisit only
  if scientia adopts one of these tools as a dependency.
