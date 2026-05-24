---
title: "Coding Agent Platform"
type: context
tags: [context, bounded-context, supporting]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

The Pi coding agent and its extension surface: skills, themes, TUI
components, prompt templates, providers, packaging, RPC/headless mode,
SDK, custom tools, and the subagent delegation model (forked contexts,
recursion guards, worktree isolation). This context owns Pi's specific
extensibility vocabulary and the entities in its ecosystem.

## Subdomain Classification

**Supporting.** Pi is a reference terminal coding agent — an alternative
runtime alongside claude-code that informs scientia's agent design, but
scientia does not build it. Its subagent/worktree patterns directly
inform how kanban workers are isolated.

## In-Scope Concepts

- [[concepts/pi-extension]]
- [[concepts/pi-skill]]
- [[concepts/pi-theme]]
- [[concepts/pi-tui-component]]
- [[concepts/pi-compaction]]
- [[concepts/pi-session-format]]
- [[concepts/pi-provider]]
- [[concepts/pi-prompt-template]]
- [[concepts/pi-package]]
- [[concepts/pi-rpc-mode]]
- [[concepts/pi-sdk]]
- [[concepts/pi-custom-tool]]
- [[concepts/pi-subagent]]
- [[concepts/pi-agent-definition]]
- [[concepts/pi-subagent-chain]]
- [[concepts/pi-subagent-execution-mode]]
- [[concepts/pi-forked-context]]
- [[concepts/pi-subagent-recursion-guard]]
- [[concepts/pi-subagent-child-safety-boundary]]
- [[concepts/pi-worktree-isolation]]

## In-Scope Entities

- [[entities/pi]]
- [[entities/earendil-works]]
- [[entities/pi-subagents]]
- [[entities/pi-intercom]]
- [[entities/pi-web-access]]
- [[entities/pi-mcp-adapter]]
- [[entities/pi-prompt-template-model]]
- [[entities/opencode]]

## Ubiquitous Language (Glossary)

- **Extension** — a unit that augments Pi (skill, theme, tool, etc.).
- **Subagent** — a delegated child agent spawned with a forked context.
- **Forked context** — a child's copy-on-spawn conversation state,
  isolated from the parent.
- **Recursion guard** — the depth limit preventing runaway subagent
  nesting.
- **Worktree isolation** — running a subagent in its own git worktree so
  concurrent work does not collide.
- **Provider** — a configured LLM backend Pi routes requests to.
- **RPC mode** — Pi's headless JSONL request/response interface.
- **Prompt template** — a reusable slash-command-invoked prompt.

## False Cognates with Adjacent Contexts

- **"skill" / "subagent" / "provider" / "session"** all collide with
  [[contexts/autonomous-agent-orchestration]] (Hermes) — Pi and Hermes
  are sibling agent runtimes with parallel-but-distinct vocabularies.
  See [[context-maps/agent-ecosystem]].
- **"theme"** (`pi-theme`) collides with zellij `theme-system`
  ([[contexts/terminal-workspace]]) — both terminal theming, different
  configs.
- **"compaction"** (`pi-compaction`) is Pi's name for what
  [[contexts/autonomous-agent-orchestration]] calls *context
  compression* and [[contexts/llm-reasoning]] frames as a context-window
  constraint.
- **"worktree isolation"** here is a near-duplicate of
  [[concepts/pi-worktree-isolation]]'s use in scientia kanban emit
  (`--workspace worktree`) — see [[context-maps/agent-ecosystem]].

## Sources

- [[summaries/pi-coding-agent-docs]]
- [[summaries/pi-subagents-readme]]
