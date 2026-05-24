---
title: "Intent-Driven Dev"
type: entity
tags: [entity, organization, openspec, adr]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/spec-driven-development-with-adr.md", "raw/openspec-schemas/", "raw/intent-driven-template/index.md"]
confidence: medium
---

## Overview

**Intent-Driven Dev** is the project/organization behind the
[intent-driven.dev](https://intent-driven.dev) website and the matching
`intent-driven-dev` GitHub organization. It promotes "intent-driven development" —
the practice of keeping the reasoning behind code close to the code so future
contributors can read the *why*. In practice it publishes writing (a blog,
including [[entities/hari-krishnan|Hari Krishnan]]'s post on spec-driven
development with ADRs) and tooling that extends [[entities/openspec|OpenSpec]],
most notably the [[entities/openspec-schemas|openspec-schemas]] repository and the
clone-and-go [[entities/intent-driven-template|intent-driven-template]] starter.

## Characteristics

| Attribute | Detail |
|-----------|--------|
| Website | https://intent-driven.dev |
| GitHub org | https://github.com/intent-driven-dev |
| Flagship repo | `openspec-schemas` (MIT-licensed custom OpenSpec schemas) |
| Related repo | [[entities/intent-driven-template]] — OpenSpec + [[entities/opencode]] starter bundling the `intent-driven` schema and engineering skills |
| Stance | Vendor-adjacent to OpenSpec/Fission AI; customizes rather than forks |

## Common Strategies

- **Customize, don't fork OpenSpec.** Ships its ideas as drop-in
  [[concepts/custom-workflow-schema|custom workflow schemas]] (e.g.
  [[concepts/spec-driven-with-adr-schema]]) rather than maintaining a competing
  framework.
- **Pair writing with tooling.** A blog post explains the motivation
  (durable ADRs) and a repository provides the runnable schema that implements it.
- **Externalize ADR templates into skills.** Keeps the ADR format in the
  [[entities/intent-driven-template]]'s `.agents/skills/architectural-decision-records`
  folder (offering [[concepts/madr|MADR]], [[concepts/y-statement-format|Y-statement]],
  and Nygard variants) so multiple schemas can share it.
- **Ship a batteries-included starter.** Beyond the schema catalog, it publishes a
  clone-and-go template that pre-wires [[entities/opencode|OpenCode]],
  [[entities/superpowers]], the [[concepts/intent-driven-schema|`intent-driven`]]
  schema, and skills for [[concepts/c4-model|C4]], [[concepts/gherkin|Gherkin]], ADRs,
  [[concepts/design-interrogation|grill-me]], and
  [[concepts/openspec-git-discipline|git discipline]].

## Sources

- [intent-driven.dev blog](https://intent-driven.dev/blog/2026/04/29/spec-driven-development-with-adr/) (`raw/spec-driven-development-with-adr.md`)
- [github.com/intent-driven-dev/openspec-schemas](https://github.com/intent-driven-dev/openspec-schemas) (`raw/openspec-schemas/`)
- [github.com/intent-driven-dev/intent-driven-template](https://github.com/intent-driven-dev/intent-driven-template) (`raw/intent-driven-template/index.md`)
