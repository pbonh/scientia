---
title: "Agent Skills Standard"
type: context
tags: [context, bounded-context, core]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

The portable, cross-vendor specification for *agent skills* — Markdown
`SKILL.md` files with YAML frontmatter, loaded into an agent's context
on demand via progressive disclosure, and validated by tooling. This
context owns the *skill-as-artifact* vocabulary (*frontmatter,
progressive disclosure, skill validation, readable skill*) and the
ecosystem of agents that consume the format. It is the mechanism scientia
itself is built from: every pipeline phase is a skill.

## Subdomain Classification

**Core.** Scientia ships as a bundle of skills; the agent-skills format
is the substrate the entire orchestrator and its phase skills are
authored in. Differentiating and foundational — distinct from any single
agent runtime that *executes* skills.

## In-Scope Concepts

- [[concepts/agent-skills-format]]
- [[concepts/progressive-disclosure]]
- [[concepts/skill-validation]]
- [[concepts/readable-skill]]

## In-Scope Entities

- [[entities/agentskills-io]]
- [[entities/skills-ref]]
- [[entities/anthropic]]
- [[entities/cursor]]
- [[entities/claude-code]]
- [[entities/github-copilot]]
- [[entities/vscode]]
- [[entities/openai-codex]]
- [[entities/roo-code]]
- [[entities/goose]]
- [[entities/spring-ai]]
- [[entities/superpowers]]

## Ubiquitous Language (Glossary)

- **Skill** — a self-contained capability packaged as `SKILL.md` plus
  optional scripts/assets/references, portable across agents.
- **Frontmatter** — the YAML header (name, description, triggers) the
  agent reads to decide relevance.
- **Progressive disclosure** — loading only a skill's summary until
  invoked, then its body, then referenced files — to conserve context.
- **Skill validation** — tooling (e.g. skills-ref) that checks a skill's
  structure and frontmatter conform to the spec.
- **Readable skill** — the authoring discipline of writing skill bodies
  as clear procedural prose an LLM can follow.
- **Trigger** — the phrase or condition that activates a skill.

## False Cognates with Adjacent Contexts

- **"skill"** here is the portable artifact/standard; in
  [[contexts/autonomous-agent-orchestration]] `hermes-skills-system` is
  one runtime's procedural-memory loader, and `pi-skill` in
  [[contexts/coding-agent-platform]] is another runtime's notion. The
  standard is upstream of both — see [[context-maps/agent-ecosystem]].
- **"progressive disclosure"** here (skill loading) is a near-cognate of
  [[concepts/progressive-rigor]] in
  [[contexts/spec-driven-development]] — both ration effort/context, but
  one is about *loading* and the other about *specifying*.
- **"validation"** here is structural skill-linting; in
  [[contexts/spec-driven-development]] *verify* scores a change's
  completeness/correctness — different gate, different artifact.

## Sources

- [[summaries/agentskills-io-home]]
- [[summaries/agentskills-io-specification]]
