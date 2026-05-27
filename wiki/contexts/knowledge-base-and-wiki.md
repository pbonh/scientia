---
title: "Knowledge Base & Wiki"
type: context
tags: [context, bounded-context, core]
created: 2026-05-24
updated: 2026-05-26
confidence: high
---

## Boundary

The construction, curation, and querying of a Markdown knowledge base
that an LLM reads and writes. This context owns the *wiki phase* of the
scientia pipeline: turning `raw/` sources into linked concept/entity
pages, linting structural integrity, and serving the wiki as the
single source of truth that every downstream change manifest pins to.
Tooling for headless note management (obsidian-cli and friends) lives
here because it shares the vocabulary of *vaults, pages, links, and
ingest*.

## Subdomain Classification

**Core.** The wiki is the head of the scientia loop
(`wiki → intent → kanban → ingest → wiki`). Knowledge compounding is the
project's central bet: every change is born from the wiki and flows back
into it. This is where scientia invests and differentiates, not a
commodity.

## In-Scope Concepts

- [[concepts/llm-wiki-pattern]]
- [[concepts/compounding-knowledge]]
- [[concepts/wiki-ingest]]
- [[concepts/wiki-query]]
- [[concepts/wiki-lint]]
- [[concepts/agent-schema-document]]
- [[concepts/obsidian-cli]]
- [[concepts/obsidian-cli-tui]]
- [[concepts/obsidian-cli-developer-commands]]

## In-Scope Entities

- [[entities/obsidian]]
- [[entities/obsidian-headless]]
- [[entities/dataview]]
- [[entities/obsidian-web-clipper]]
- [[entities/marp]]
- [[entities/notebooklm]]
- [[entities/qmd]]
- [[entities/memex]]
- [[entities/andrej-karpathy]]

## Ubiquitous Language (Glossary)

- **Wiki** — the curated, linked corpus under `wiki/`; the durable
  knowledge store, distinct from `raw/` sources.
- **Concept page** — a page defining one domain idea, tagged and
  confidence-rated, linked bidirectionally to related pages.
- **Entity page** — a page describing a concrete tool, library, person,
  or organization referenced by concepts.
- **Summary page** — a per-source digest of one `raw/` document.
- **Ingest** — the act of turning a single raw source into a summary
  plus zero or more concept/entity pages.
- **Lint** — read-only validation of frontmatter, link resolution, and
  index completeness; never mutates the wiki.
- **Compounding knowledge** — the property that each ingested source
  makes future ingests and queries cheaper and richer.
- **Vault** — obsidian-cli's term for a wiki root directory.
- **Confidence** — a per-page metadata field (high/medium/low) recording
  how settled the knowledge is.

## False Cognates with Adjacent Contexts

- **"ingest"** here means *raw-source → wiki page*; in
  [[contexts/spec-driven-development]] the analogous flow is the *ingest
  phase* that folds kanban handoffs back into the wiki. Same English
  word, different mechanism — see [[context-maps/scientia-pipeline]].
- **"index"** here is `wiki/index.md` (a page catalog); in
  [[contexts/fuzzy-finder]] an *index* is a search-time match structure.
- **"query"** here is the wiki-query reading pattern; in
  [[contexts/knowledge-base-and-wiki]]'s neighbour
  [[contexts/shell-and-data-pipeline]] a query is a structured-data
  operation over tables.
- **"confidence"** here is a *per-page, qualitative* metadata field
  (`high`/`medium`/`low`). The in-flight KG-seeded rewrite
  (`spec-driven-development/2026-05-26-kg-seeded-intent-skills`) defines
  a *per-claim, quantitative* `[0,1]` model (base score × source-count
  multiplier, clamped by a contradiction floor → `effective`) used to
  gate automation. Same word, different mechanism; the quantitative
  model applies only to wikis that rewrite produces, not this corpus.

## Sources

- [[summaries/llm-wiki]]
- [[summaries/obsidian-cli-help]]
