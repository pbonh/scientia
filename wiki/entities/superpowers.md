---
title: "Superpowers"
type: entity
tags: [entity, tool, agent-skills, plugin, opencode]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/index.md", "raw/intent-driven-template/install.md"]
confidence: medium
---

## Overview

**Superpowers** (https://github.com/obra/superpowers, by `obra`) is a collection of
reusable agent skills that encode guided engineering practices. The
[[entities/intent-driven-template]] loads it as an [[entities/opencode|OpenCode]]
plugin (declared in `opencode.json` as
`superpowers@git+https://github.com/obra/superpowers.git`) to provide
practice-driven workflows on top of the template's OpenSpec lifecycle.

## Characteristics

| Attribute | Detail |
|-----------|--------|
| Repository | https://github.com/obra/superpowers |
| Author | `obra` |
| Distribution | git-installable OpenCode/agent plugin |
| Install (here) | `"plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]` in `opencode.json` |
| Practices provided | brainstorming, planning, debugging, TDD ([[concepts/test-driven-development]]), verification, worktrees, subagent-driven parallel work |

## Common Strategies

- **Load it as a plugin for guided practices.** The intent-driven-template pulls
  superpowers in so OpenCode can offer structured brainstorming, planning,
  debugging, TDD, and verification flows rather than ad-hoc prompting.
- **Pair with subagent-driven parallel work.** Among the practices the template
  cites is subagent-driven parallel work, complementing OpenSpec's task
  decomposition.
- **Compose, don't reimplement.** The template references superpowers (and the
  separate `grill-me` design-interrogation skill) instead of re-authoring those
  practices, consistent with [[entities/intent-driven-dev]]'s "customize, don't
  fork" posture.

## Sources

- [intent-driven-template README](https://github.com/intent-driven-dev/intent-driven-template) (`raw/intent-driven-template/index.md`)
- [opencode.json plugin entry](https://github.com/intent-driven-dev/intent-driven-template/blob/main/opencode.json) (`raw/intent-driven-template/install.md`)
- https://github.com/obra/superpowers (named in source; full skill catalog not captured in this ingest)
