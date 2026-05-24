---
title: "Agent Ecosystem (Skills ↔ Hermes ↔ Pi ↔ Reasoning)"
type: context-map
tags: [context-map]
contexts: [agent-skills-standard, autonomous-agent-orchestration, coding-agent-platform, llm-reasoning]
created: 2026-05-24
updated: 2026-05-24
---

## Relationships

- **Agent Skills Standard → Hermes, Pi** — *Conformist.* Both runtimes
  implement skill-loading; the standard is the upstream spec they
  conform to. `hermes-skills-system` and `pi-skill` are downstream
  realizations.
- **Hermes ↔ Pi** — *Separate Ways / parallel runtimes.* Two coding-agent
  platforms with near-identical concept sets (subagent, provider,
  session, compaction) but no shared code or kernel. Scientia *uses*
  Hermes for execution and *studies* Pi as a reference design.
- **LLM Reasoning → Hermes, Pi** — *Supplier.* Reasoning techniques
  (heavy-thinking, deliberation) and the context-window constraint they
  navigate are consumed by both runtimes' loops
  (`hermes-context-compression`, `pi-compaction`).

## False Cognates

| Term | Agent Skills | Hermes | Pi |
|---|---|---|---|
| **skill** | the portable SKILL.md artifact/spec | `hermes-skills-system` procedural-memory loader | `pi-skill` extension |
| **subagent** | — | `hermes-subagent-delegation` | `pi-subagent` (forked context) |
| **provider** | — | `hermes-provider-resolution` | `pi-provider` |
| **session** | — | `hermes-session-storage` | `pi-session-format` |
| **plugin** | — | `hermes-plugin-system` | `pi-extension` |
| **compaction / context compression** | (progressive disclosure) | `hermes-context-compression` | `pi-compaction` |

All are *related-but-distinct*: same problem space, runtime-specific
mechanisms. None are interchangeable across the boundary.

## Duplicate Concepts

- **Worktree isolation.** [[concepts/pi-worktree-isolation]] (Pi) and
  the `--workspace worktree` mechanism scientia-kanban-emit drives on
  the Hermes side are the *same technique* (isolate concurrent agent
  work in a git worktree) expressed in two runtimes. Not merged — each
  documents its own runtime.
- **"session"** as conversation persistence is conceptually one idea
  split across `hermes-session-storage` and `pi-session-format`; kept
  separate because formats and storage differ.

## Open Questions

- Is [[entities/nous-research]] best placed in the Orchestration context
  (as Hermes' maker) or LLM Reasoning (as a model-training org)?
  Currently Orchestration, since `hermes-agent.nousresearch.com` is the
  Hermes home; revisit if reasoning-model entities accrue to Nous.
