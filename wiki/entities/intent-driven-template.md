---
title: "intent-driven-template"
type: entity
tags: [entity, repository, openspec, opencode, template]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/index.md", "raw/intent-driven-template/intent-driven-schema.md", "raw/intent-driven-template/skills.md", "raw/intent-driven-template/install.md"]
confidence: high
---

## Overview

**intent-driven-template** (`intent-driven-dev/intent-driven-template`) is a public
GitHub template repository published by [[entities/intent-driven-dev|Intent-Driven
Dev]]. It is a clone-and-go starter for "intent-driven software delivery" that
wires together [[entities/openspec|OpenSpec]], the [[entities/opencode|OpenCode]]
coding agent, the [[entities/superpowers|superpowers]] skills plugin, a bundled
[[concepts/intent-driven-schema|`intent-driven`]] OpenSpec schema, and a set of
reusable engineering skills. The intent is that changes start from clear intent,
move through explicit behaviour and design artifacts, and end with implementation
tasks that preserve the reasoning behind the work.

## Characteristics

| Attribute | Detail |
|-----------|--------|
| Full name | `intent-driven-dev/intent-driven-template` |
| URL | https://github.com/intent-driven-dev/intent-driven-template |
| Publisher | [[entities/intent-driven-dev|Intent-Driven Dev]] |
| Target agent | [[entities/opencode|OpenCode]] (`opencode.json`, `.opencode/`) |
| Bundled schema | local copy of [[concepts/intent-driven-schema|`intent-driven`]] from [[entities/openspec-schemas]] |
| Skills (`.agents/skills/`) | c4-diagrams ([[concepts/c4-model]]), gherkin-authoring ([[concepts/gherkin]]), architectural-decision-records, grill-me ([[concepts/design-interrogation]]), [[concepts/openspec-git-discipline]] |
| Commands (`.opencode/`) | `opsx-*` slash commands (propose, apply, archive, verify, sync, …) and `openspec-*` lifecycle skills |
| Plugin | [[entities/superpowers]], loaded via `opencode.json` |
| Walkthrough | https://intent-driven.dev/blog/2026/05/10/spec-driven-development-openspec-opencode/ |
| License | Not stated in fetched files |

## Common Strategies

- **Start a new project from the template.** Clone the repo, open it with
  [[entities/opencode|OpenCode]], and work from the bundled OpenSpec config,
  `opsx-*` commands, skills, and the activated `intent-driven` schema.
- **Graft the template onto an existing project.** Open the project with OpenCode
  and point it at `INSTALL_TEMPLATE.md`: it copies `openspec/`, `.opencode/`,
  `.agents/`, `skills-lock.json`, and `opencode.json` where they are missing,
  *merges* `AGENTS.md` (adding the [[concepts/openspec-git-discipline|git-discipline]]
  instruction without deleting existing instructions), and asks before replacing
  any pre-existing config.
- **Run the full intent-to-tasks lifecycle.** The bundled
  [[concepts/intent-driven-schema|`intent-driven` schema]] enforces
  `proposal → specs → design → adr → tasks` with [[concepts/gherkin|Gherkin]]-style
  behaviour specs and durable [[concepts/architectural-decision-record|ADRs]] in a
  top-level `adr/` folder.
- **Customize, don't fork.** Like its publisher, it composes existing tools
  (OpenSpec, OpenCode, superpowers, openspec-schemas) rather than building a
  competing framework.

## Sources

- [intent-driven-template README](https://github.com/intent-driven-dev/intent-driven-template) (`raw/intent-driven-template/index.md`)
- [bundled intent-driven schema](https://github.com/intent-driven-dev/intent-driven-template/tree/main/openspec/schemas/intent-driven) (`raw/intent-driven-template/intent-driven-schema.md`)
- [bundled `.agents/skills`](https://github.com/intent-driven-dev/intent-driven-template/tree/main/.agents/skills) (`raw/intent-driven-template/skills.md`)
- [INSTALL_TEMPLATE.md + opencode.json](https://github.com/intent-driven-dev/intent-driven-template/blob/main/INSTALL_TEMPLATE.md) (`raw/intent-driven-template/install.md`)
