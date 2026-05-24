---
title: "Intent-Driven Template"
type: summary
tags: [summary, openspec, opencode, spec-driven-development, agent-skills]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/index.md", "raw/intent-driven-template/intent-driven-schema.md", "raw/intent-driven-template/skills.md", "raw/intent-driven-template/install.md"]
confidence: high
---

## Overview

**intent-driven-template** is a public GitHub repository
(`intent-driven-dev/intent-driven-template`) published by
[[entities/intent-driven-dev|Intent-Driven Dev]]. It is a ready-to-clone starter
project that wires together [[entities/openspec|OpenSpec]], the
[[entities/opencode|OpenCode]] coding agent, a bundled OpenSpec schema, and a set
of reusable engineering skills so that a change starts from clear intent, moves
through explicit behaviour and design artifacts, and ends with implementation
tasks that preserve the reasoning behind the work.

Its centrepiece is a *bundled local copy* of the
[[concepts/intent-driven-schema|`intent-driven`]] OpenSpec schema (the upstream
canonical copy lives in the [[entities/openspec-schemas|openspec-schemas]] repo),
which drives the full `proposal -> specs -> design -> adr -> tasks` lifecycle. The
schema's distinguishing choices are that behaviour specs are written in
[[concepts/gherkin|Gherkin]] style *inside* OpenSpec Markdown delta wrappers
(`### Requirement:` / `#### Scenario:`), and that
[[concepts/architectural-decision-record|ADRs]] are persisted to the repository's
top-level `adr/` folder so they outlive the archived change — the same
[[concepts/durable-artifacts-vs-scaffolding|durable-vs-scaffolding]] discipline its
sibling [[concepts/spec-driven-with-adr-schema|`spec-driven-with-adr`]] schema uses.

Beyond the schema, the template ships five OpenCode/agent skills under
`.agents/skills/`: [[concepts/c4-model|C4 diagrams]] for visualizing architecture
boundaries before detailed design, [[concepts/gherkin|Gherkin authoring]] for
observable behaviour scenarios, [[concepts/architectural-decision-record|ADR
authoring]] (offering MADR, [[concepts/madr|MADR-minimal]],
[[concepts/y-statement-format|Y-statement]], and Nygard template variants),
[[concepts/design-interrogation|grill-me]] design interrogation, and
[[concepts/openspec-git-discipline|OpenSpec git discipline]]. It also loads the
[[entities/superpowers|superpowers]] plugin (via `opencode.json`) for guided
practices — brainstorming, planning, debugging, [[concepts/test-driven-development|
TDD]], verification, worktrees, and subagent-driven parallel work — and provides
`.opencode/commands/opsx-*.md` slash commands plus an `INSTALL_TEMPLATE.md` recipe
for grafting the template onto an existing project.

## Key Claims

- **The repository is a batteries-included intent-driven starter.** It bundles an
  OpenSpec config, the [[concepts/intent-driven-schema|`intent-driven`]] schema,
  `opsx-*` OpenCode commands, and reusable skills so a team can adopt the full
  intent-to-tasks lifecycle by cloning one repo.
- **Behaviour specs are Gherkin inside an OpenSpec wrapper.** The Markdown
  headings (`### Requirement:`, `#### Scenario:`) are the OpenSpec merge wrapper;
  the requirement and scenario bodies are written in [[concepts/gherkin|Gherkin]]
  `GIVEN`/`WHEN`/`THEN`. No `.feature` files are produced.
- **ADRs are durable and immutable.** The schema's `adr` stage writes
  `NNNN-kebab-title.md` files to the repo's top-level `adr/` folder; accepted ADRs
  are never edited — a changed decision is recorded as a new superseding ADR, and
  design steps derive what is in force by walking `Supersedes:` links. See
  [[concepts/architectural-decision-record]] and [[concepts/madr]].
- **Design must honor in-force ADRs.** Before writing `design.md` the schema
  requires listing every ADR, building the supersession graph, and constraining
  the design only by accepted, non-superseded ADRs — a concrete instance of
  [[concepts/architectural-knowledge-management]].
- **Git history gates the lifecycle.** The bundled
  [[concepts/openspec-git-discipline|OpenSpec git-discipline]] skill requires every
  OpenSpec state change to cross `main` before the next phase: a proposal must
  reach `main` before apply, and archive may run only from `main` after
  implementation merges back.
- **It composes rather than reinvents.** The template depends on OpenCode,
  [[entities/superpowers|superpowers]], and the upstream
  [[entities/openspec-schemas|openspec-schemas]] catalog — a vendor-adjacent
  "customize, don't fork" posture consistent with [[entities/intent-driven-dev]].

## Source Metadata

| Field | Value |
|-------|-------|
| Type | GitHub repository (template project) |
| Full name | `intent-driven-dev/intent-driven-template` |
| Owner | [[entities/intent-driven-dev|Intent-Driven Dev]] |
| URL | https://github.com/intent-driven-dev/intent-driven-template |
| Walkthrough | https://intent-driven.dev/blog/2026/05/10/spec-driven-development-openspec-opencode/ |
| License | Not stated in fetched files |
| Ingested | 2026-05-23 (via GitHub API) |

## Relevant Concepts

- [[concepts/intent-driven-schema]] — the bundled OpenSpec schema the template runs
- [[concepts/gherkin]] — the behaviour-spec style the schema mandates
- [[concepts/c4-model]] — the architecture-diagram skill shipped with the template
- [[concepts/openspec-git-discipline]] — the main-crossing git gate it enforces
- [[concepts/design-interrogation]] — the bundled grill-me practice
- [[concepts/madr]] — the default ADR template family the ADR skill offers
- [[concepts/architectural-decision-record]] — the durable artifact the `adr` stage produces
- [[concepts/durable-artifacts-vs-scaffolding]] — why ADRs persist outside the change
- [[concepts/custom-workflow-schema]] — the OpenSpec mechanism the schema is an instance of

## Relevant Entities

- [[entities/intent-driven-template]] — the repository itself
- [[entities/intent-driven-dev]] — its publisher
- [[entities/opencode]] — the coding agent the template targets
- [[entities/superpowers]] — the skills plugin it loads
- [[entities/openspec]] — the framework it configures
- [[entities/openspec-schemas]] — the upstream source of the bundled schema
