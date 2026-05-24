---
title: "Autonomous Agent Orchestration"
type: context
tags: [context, bounded-context, core]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

The Hermes platform: durable multi-agent execution driven by a SQLite
Kanban board, with profile-isolated workers, a provider-resolution
layer, persistent memory, and a tool registry. This context owns the
*execution* vocabulary (*board, task, tenant, profile, dispatcher,
handoff, gateway*). It is the engine of the scientia kanban phase, where
verified specs become durable tasks that workers run to done or blocked.

## Subdomain Classification

**Core.** Hermes Kanban *is* scientia's execution substrate. The
concurrency model (one in-flight change per tenant), the impl→review→
integrate pipeline, and the durable handoff back to ingest are all
Hermes mechanisms. Heavily invested and differentiating.

## In-Scope Concepts

- [[concepts/hermes-agent-loop]]
- [[concepts/hermes-context-compression]]
- [[concepts/hermes-cron-scheduler]]
- [[concepts/hermes-gateway]]
- [[concepts/hermes-kanban-board]]
- [[concepts/hermes-mcp-integration]]
- [[concepts/hermes-persistent-memory]]
- [[concepts/hermes-plugin-system]]
- [[concepts/hermes-profile-isolation]]
- [[concepts/hermes-provider-resolution]]
- [[concepts/hermes-session-storage]]
- [[concepts/hermes-skills-system]]
- [[concepts/hermes-subagent-delegation]]
- [[concepts/hermes-tool-registry]]
- [[concepts/hermes-kanban-dispatcher]]
- [[concepts/hermes-kanban-orchestrator-profile]]
- [[concepts/hermes-kanban-tenant]]

## In-Scope Entities

- [[entities/hermes-agent]]
- [[entities/nous-research]]

## Ubiquitous Language (Glossary)

- **Kanban board** — the durable SQLite-backed task store
  (`kanban.db`); the canonical execution state.
- **Task** — one durable unit of work with a state
  (todo/running/blocked/done/archived) and a body following the scientia
  schema.
- **Tenant** — a namespace partitioning the board; in scientia, a
  tenant *is* a bounded-context slug, enforcing one in-flight change per
  context.
- **Profile** — an isolated agent home (model, skills, config); scientia
  uses implementer / reviewer / integrator / aggregator profiles.
- **Dispatcher** — the component that moves ready tasks to workers,
  honoring dependencies and concurrency caps.
- **Handoff** — the structured Required-Handoff block a worker fills on
  completion; the unit ingested back into the wiki.
- **Gateway** — the messaging adapter connecting agents to platforms.
- **Provider resolution** — routing a model request to a concrete LLM
  endpoint (e.g. `custom:fireworks`).
- **Context compression** — summarizing conversation history to fit the
  model's context window.

## False Cognates with Adjacent Contexts

- **"skill"** in Hermes (`hermes-skills-system`, procedural memory) vs
  *skill* in [[contexts/agent-skills-standard]] (the portable SKILL.md
  format) vs `pi-skill` in [[contexts/coding-agent-platform]]: three
  related-but-distinct notions — see [[context-maps/agent-ecosystem]].
- **"subagent"** (`hermes-subagent-delegation`) vs `pi-subagent`: both
  delegation, different runtimes. See [[context-maps/agent-ecosystem]].
- **"provider"** (`hermes-provider-resolution`) vs `pi-provider`: same
  concept, two implementations.
- **"session"** here is `hermes-session-storage` (agent conversation
  persistence) — a false cognate of zellij *session*
  ([[contexts/terminal-workspace]]) and `pi-session-format`.
- **"plugin"** (`hermes-plugin-system`) collides with nushell, zellij,
  and obsidian plugins — all extensibility, none interchangeable.
- **"tenant"/"profile"/"archive"/"status"** are kanban terms that
  bridge into [[contexts/spec-driven-development]] — see
  [[context-maps/scientia-pipeline]].

## Sources

- [[summaries/hermes-agent-docs]]
- [[summaries/hermes-kanban-v1-spec]]
