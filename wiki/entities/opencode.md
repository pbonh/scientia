---
title: "OpenCode"
type: entity
tags: [entity, tool, coding-agent, terminal]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/index.md", "raw/intent-driven-template/install.md"]
confidence: medium
---

## Overview

**OpenCode** (https://opencode.ai/) is a terminal-based AI coding agent. In the
context of this ingest it is the agent the [[entities/intent-driven-template]] is
built for: the template ships an `opencode.json` config, a `.opencode/` directory
of slash commands and skills, and instructions written "for OpenCode" to install
and run the intent-driven workflow. It sits alongside other coding agents in the
wiki such as [[entities/claude-code]], [[entities/cursor]], and
[[entities/openai-codex]].

## Characteristics

| Attribute | Detail |
|-----------|--------|
| Website | https://opencode.ai/ |
| Config | `opencode.json` (schema `https://opencode.ai/config.json`) |
| Plugins | git-installable plugins, e.g. `"plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]` |
| Project assets | `.opencode/commands/*.md` (slash commands) and `.opencode/skills/*/SKILL.md` |
| Skills format | reads `.agents/skills/*/SKILL.md` (agent-skills style frontmatter) |
| Role here | the agent the intent-driven-template targets |

## Common Strategies

- **Open a project and drive the OpenSpec lifecycle.** The template's `opsx-*`
  slash commands under `.opencode/commands/` map to OpenSpec propose / apply /
  archive / verify / sync steps, run by OpenCode.
- **Extend via git plugins.** `opencode.json` declares plugins by git URL; the
  template uses this to load [[entities/superpowers]].
- **Install a template into an existing repo.** OpenCode is the agent that reads
  `INSTALL_TEMPLATE.md` and copies the template's `openspec/`, `.opencode/`, and
  `.agents/` directories into a target project.

## Sources

- [intent-driven-template README](https://github.com/intent-driven-dev/intent-driven-template) (`raw/intent-driven-template/index.md`)
- [opencode.json + INSTALL_TEMPLATE.md](https://github.com/intent-driven-dev/intent-driven-template/blob/main/opencode.json) (`raw/intent-driven-template/install.md`)
- https://opencode.ai/ (named in source; product details not independently captured in this ingest)
