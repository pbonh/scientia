---
title: "Scientia Domain Landscape"
type: context-map
tags: [context-map]
contexts: [knowledge-base-and-wiki, spec-driven-development, architecture-decision-records, autonomous-agent-orchestration, agent-skills-standard, llm-reasoning, coding-agent-platform, software-design-principles, type-theory, typescript, rust-systems-programming, terminal-workspace, shell-and-data-pipeline, editor-extensibility, fuzzy-finder, infrastructure-automation]
created: 2026-05-24
updated: 2026-05-24
---

## Relationships

The master map of all 16 bounded contexts, classified by subdomain. The
five **core** contexts are scientia's own pipeline and the mechanism it
is built from; the rest are reference knowledge the wiki catalogs.

| Context | Subdomain | Role relative to scientia |
|---|---|---|
| [[contexts/knowledge-base-and-wiki]] | core | the wiki phase (head of the loop) |
| [[contexts/spec-driven-development]] | core | the intent phase (what changes) |
| [[contexts/architecture-decision-records]] | core | the intent phase (why) |
| [[contexts/autonomous-agent-orchestration]] | core | the kanban execution phase |
| [[contexts/agent-skills-standard]] | core | the build substrate (every phase is a skill) |
| [[contexts/llm-reasoning]] | supporting | agent reasoning quality |
| [[contexts/coding-agent-platform]] | supporting | reference agent runtime (Pi) |
| [[contexts/software-design-principles]] | supporting | implementation craft |
| [[contexts/type-theory]] | supporting | type-driven design (agnostic) |
| [[contexts/typescript]] | supporting | typed-language realization |
| [[contexts/rust-systems-programming]] | supporting | implementation language |
| [[contexts/terminal-workspace]] | generic | commodity multiplexer |
| [[contexts/shell-and-data-pipeline]] | generic | commodity shell |
| [[contexts/editor-extensibility]] | generic | commodity editor |
| [[contexts/fuzzy-finder]] | generic | commodity interactive search |
| [[contexts/infrastructure-automation]] | generic | commodity config management |

**Detailed maps** decompose the relationships that actually touch:

- [[context-maps/scientia-pipeline]] — the core five as a closed loop.
- [[context-maps/intent-shared-kernel]] — Spec-Driven ↔ ADR.
- [[context-maps/agent-ecosystem]] — Agent Skills ↔ Hermes ↔ Pi ↔ Reasoning.
- [[context-maps/language-and-types]] — Rust ↔ Type Theory ↔ TypeScript ↔ Software Design.
- [[context-maps/terminal-tooling]] — Terminal ↔ Shell ↔ Editor ↔ Fuzzy Finder.

## False Cognates

The recurring collisions across the whole wiki (detailed in the focused
maps below): **session**, **plugin**, **skill**, **subagent**,
**provider**, **template**, **context**, **status**, **archive**,
**delegation**, **error-handling**, **generics/enum/closure/iterator/
decorator**, **immutability**, **diagnostic**, **registry**, **index**,
**query**, **channel**, **pipeline**.

## Duplicate Concepts

Cross-context duplicates are concentrated on the language/type axis
(Type Theory ↔ TypeScript ↔ Rust) and are an accepted cost of the
"keep Type Theory and TypeScript separate" decision. See
[[context-maps/language-and-types]].

## Open Questions

- **No-overlap assertion.** Context pairs not named in any focused map
  are asserted to have *no shared ubiquitous language* (e.g.
  Infrastructure-Automation ↔ Type-Theory, Fuzzy-Finder ↔ ADR,
  Editor-Extensibility ↔ Spec-Driven). Revisit if a future ingest adds
  bridging concepts.
- **Tenant mapping.** Each context is a candidate scientia *tenant*
  (`tenants:` in `development/config.yaml` is still empty). Which
  contexts will actually host in-flight changes is a product decision,
  not settled here.
- **manning-publications** (entity) supplies books in both
  [[contexts/software-design-principles]] (assigned home) and
  [[contexts/type-theory]] (Programming with Types). Assigned to one per
  the single-context rule; flagged as a spanning entity.
