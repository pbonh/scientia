---
title: "ADR-0001: Use the wiki as the sole KG representation"
adr_id: ADR-0001
status: accepted
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Portability: no dependency on a graph DB, vector store, or SaaS (ASR-1)."
  - "Minimal dependency surface: stdlib + pyyaml, optional networkx (ASR-9)."
shared_types:
  - "kg_pipeline/wiki/__init__.py::Page"
  - "kg_pipeline/wiki/__init__.py::Link"
tags: [spec-driven-development, knowledge-graph, persistence, portability]
created: 2026-05-27
---

# ADR-0001: Use the wiki as the sole KG representation

## Y-Statement

**In the context of** a portable, clean-room rewrite whose novel seam is the
wiki-as-knowledge-graph seeding the proposal and grill stages,
**facing** the need for typed nodes, kinded edges, and confidence traversal
without coupling to any runtime or external service,
**we decided for** treating the `wiki/` markdown tree as the *only* persistent
KG representation, parsed on demand into in-memory `Page` and `Link` values by
`kg_pipeline.wiki`,
**and against** a derived graph database, an embedded SQLite graph, or a vector
store,
**to achieve** portability, a minimal dependency surface, a single
git-versioned source of truth, and human-readable/diffable knowledge,
**accepting** an O(files) parse cost per query, no indexed lookups, and full
re-parse on large wikis.

## Architecturally Significant Requirement

The deliverable must run on any Agent-Skills-compliant runtime with no external
services (ASR-1) and a minimal dependency surface (ASR-9). A persistent graph
store would violate both and split the source of truth between markdown and an
opaque index that can drift. Because this decision also fixes the in-memory
shape every downstream module consumes (`Page`, `Link`), it crosses task
boundaries and must be ratified before consumer tasks emit.

## Options Considered

### Option A — Derived graph database (e.g. SQLite/networkx persisted)
Index the wiki into a queryable graph store rebuilt on change.
*Pros:* fast indexed traversal; scales to large graphs.
*Cons:* second source of truth that drifts from markdown; a dependency and a
build step; opaque, non-diffable state. Violates ASR-1/ASR-9.

### Option B — Vector store / embeddings over pages
Embed pages and retrieve by similarity.
*Pros:* fuzzy semantic recall.
*Cons:* a heavy dependency and/or paid API; non-deterministic retrieval breaks
the golden-file discipline (ASR-2). Explicitly a non-goal in the brief.

### Option C — Wiki is the sole representation, parsed on demand (chosen)
`kg_pipeline.wiki` parses markdown files into `Page`/`Link` per query; no
derived store.
*Pros:* one source of truth; portable; minimal deps; git-diffable; deterministic.
*Cons:* O(files) parse per query; no indexing. **Chosen** — the parse cost is
acceptable at the brief's scale and `networkx` may optionally accelerate
traversal *without* changing results.

## Consequences

- One git-versioned, human-readable source of truth; no index to rebuild or
  drift.
- `Page` (`{frontmatter: dict, body: str}`) and `Link` (`(target_id, kind)`)
  become the shared in-memory contract for every module and skill.
- Queries pay an O(files) parse cost; very large wikis may need the optional
  `networkx` traversal helper, which must produce identical results to the
  pure-Python path (ASR-9).
- No semantic/fuzzy retrieval — recall is structural (links + types) only.

## Supersession

First ADR in the repository; supersedes nothing.
