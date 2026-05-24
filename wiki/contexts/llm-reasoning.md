---
title: "LLM Reasoning"
type: context
tags: [context, bounded-context, supporting]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Test-time-scaling techniques that make a language model reason better at
inference: parallel sampling, sequential deliberation, iterative
refinement, and the agentic-harness machinery (serialized memory caches)
that supports them. This context owns the *reasoning-quality* vocabulary
and catalogs the reasoning models and research that inform it.

## Subdomain Classification

**Supporting.** Reasoning quality shapes how well scientia's agents
plan, review, and synthesize, but scientia does not build reasoning
models — it consumes them. Necessary, not differentiating.

## In-Scope Concepts

- [[concepts/heavy-thinking]]
- [[concepts/parallel-reasoning]]
- [[concepts/sequential-deliberation]]
- [[concepts/serialized-memory-cache]]
- [[concepts/iterative-deliberation]]
- [[concepts/heavy-thinking-rlvr]]

## In-Scope Entities

- [[entities/heavyskill]]
- [[entities/kimi-k2]]
- [[entities/pacore]]
- [[entities/longcat-flash-thinking]]

## Ubiquitous Language (Glossary)

- **Heavy thinking** — allocating extra inference-time compute to a hard
  problem before answering.
- **Parallel reasoning** — sampling multiple independent reasoning
  traces and aggregating.
- **Sequential deliberation** — refining a single trace across
  successive passes.
- **Iterative deliberation** — looping reason→critique→revise until a
  stopping criterion.
- **Serialized memory cache** — persisting intermediate reasoning state
  across an agentic harness's turns.
- **RLVR** — Reinforcement Learning from Verifiable Rewards, used to
  train heavy-thinking behaviour.

## False Cognates with Adjacent Contexts

- **"context window"** here (the model's token budget for reasoning)
  recurs in [[contexts/autonomous-agent-orchestration]]
  (`hermes-context-compression`) and
  [[contexts/coding-agent-platform]] (`pi-compaction`) — same underlying
  constraint, addressed by different mechanisms.
- **"memory"** here is reasoning-trace state; in
  [[contexts/autonomous-agent-orchestration]]
  `hermes-persistent-memory` is durable cross-session storage.
- **"agentic harness"** overlaps with the orchestration context but
  refers specifically to the reasoning-loop scaffolding, not the kanban
  execution substrate.

## Sources

- [[summaries/arxiv-heavyskill]]
