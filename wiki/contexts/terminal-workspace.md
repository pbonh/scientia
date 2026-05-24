---
title: "Terminal Workspace"
type: context
tags: [context, bounded-context, generic]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Terminal multiplexing as embodied by zellij: organizing a terminal into
panes, tabs, and sessions; the PTY substrate and ANSI/VT byte stream
(CSI/OSC) that drives terminal emulation; scroll buffers and character
rendering; layouts, themes, keybindings, input modes; and the
WebAssembly plugin system. The *Rust language* used to build it lives in
[[contexts/rust-systems-programming]].

## Subdomain Classification

**Generic.** A terminal multiplexer is commodity infrastructure
(zellij/tmux/screen are interchangeable for scientia's purposes). The
wiki catalogs it as reference knowledge, not as something scientia
builds or differentiates on.

## In-Scope Concepts

- [[concepts/screen-zellij]]
- [[concepts/terminal-pane]]
- [[concepts/scroll-buffer]]
- [[concepts/terminal-character]]
- [[concepts/ansi-vt-stream]]
- [[concepts/pane-boundaries]]
- [[concepts/pty-bus]]
- [[concepts/terminal-multiplexer]]
- [[concepts/layout-system]]
- [[concepts/plugin-system]]
- [[concepts/input-modes]]
- [[concepts/keybindings]]
- [[concepts/pane]]
- [[concepts/tab]]
- [[concepts/session]]
- [[concepts/theme-system]]
- [[concepts/csi]]
- [[concepts/osc]]
- [[concepts/pty]]

## In-Scope Entities

- [[entities/zellij]]
- [[entities/tmux]]
- [[entities/gnu-screen]]
- [[entities/webassembly]]

## Ubiquitous Language (Glossary)

- **Multiplexer** — a program that splits one terminal into many
  independent sessions/panes.
- **Pane** — a rectangular region running one terminal program.
- **Tab** — a named collection of panes (a workspace screen).
- **Session** — a persistent, detachable multiplexer instance.
- **PTY** — the pseudo-terminal pair connecting the multiplexer to child
  shells.
- **ANSI/VT stream** — the byte protocol (CSI/OSC escape sequences) that
  controls cursor, color, and layout.
- **Scroll buffer** — retained off-screen output for a pane.
- **Layout** — a declarative arrangement of panes/tabs.
- **Plugin** — a WebAssembly module extending zellij.

## False Cognates with Adjacent Contexts

- **"session"** here (a detachable multiplexer instance) collides with
  `pi-session-format` ([[contexts/coding-agent-platform]]) and
  `hermes-session-storage`
  ([[contexts/autonomous-agent-orchestration]]) — three unrelated
  "sessions". See [[context-maps/terminal-tooling]].
- **"plugin"** (WebAssembly modules) collides with
  `nushell-plugin-system` ([[contexts/shell-and-data-pipeline]]) and
  `hermes-plugin-system` — all extensibility, none interchangeable.
- **"theme"** (`theme-system`) collides with `pi-theme`.
- **"pane" / "tab"** are reused loosely in other TUI tools
  ([[contexts/fuzzy-finder]], [[contexts/editor-extensibility]]) but
  zellij's are the canonical multiplexer senses.

## Sources

- [[summaries/zellij-architecture]]
- [[summaries/zellij-terminology]]
- [[summaries/zellij-manpage]]
- [[summaries/zellij-third-party-install]]
