---
title: "ADR-0002: Encode edge kind in the wiki-link alias slot"
adr_id: ADR-0002
status: accepted
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Provenance: edges carry a typed kind without a separate edge store (ASR-7)."
shared_types: []
tags: [spec-driven-development, knowledge-graph, edges]
created: 2026-05-27
---

# ADR-0002: Encode edge kind in the wiki-link alias slot

## Y-Statement

**In the context of** a wiki whose edges are ordinary markdown wiki-links and
must carry a semantic kind (`mentions`, `supports`, `contradicts`, `refines`),
**facing** the constraint that edges have no storage outside the page body and
must stay human-authorable and renderable in Obsidian-style tools,
**we decided for** encoding the edge kind in the link's alias slot —
`[[target-id | kind]]` — with any unrecognized alias defaulting to `mentions`,
**and against** a separate frontmatter edge list or a bespoke link syntax,
**to achieve** typed provenance at zero extra storage with a graceful default,
**accepting** that the alias slot is thereby spent on kind (not free display
text) and that authors/LLMs must learn the convention.

## Architecturally Significant Requirement

The confidence model (ASR-4) and the seeding/grill stages (ASR-7) depend on
distinguishing a `supports` edge from a `contradicts` edge; the contradiction
floor fires only on `contradicts`. The edge kind must therefore be a
first-class, parseable property of every link, recovered deterministically by
`parse_links`.

## Options Considered

### Option A — Frontmatter edge list
List typed edges in each page's frontmatter (`edges: [{to, kind}]`).
*Pros:* explicit, easy to parse.
*Cons:* duplicates the body's links; drifts from the prose; two places to keep
in sync; not how wiki authors think.

### Option B — Bespoke link syntax (e.g. `-->supports[[target]]`)
A custom inline notation for kinded edges.
*Pros:* unambiguous.
*Cons:* breaks wiki-link rendering in standard tools; a custom parser; hostile
to human authoring.

### Option C — Kind in the alias slot, default mentions (chosen)
`[[target | kind]]`; unknown alias ⇒ `mentions`.
*Pros:* renders in standard tools; no extra storage; graceful default keeps
plain `[[target]]` links valid. **Chosen.**
*Cons:* the alias can no longer double as display text.

## Consequences

- `parse_links(body)` recovers `(target_id, kind)` and maps any unknown alias
  to `mentions`, so legacy/plain links remain valid edges.
- The canonical edge-kind vocabulary is fixed at `mentions | supports |
  contradicts | refines`; adding a kind is a convention change, not a schema
  migration.
- Authors lose alias-as-display-text; acceptable since these wikis are
  machine-and-human-read, not presentation artifacts.

## Supersession

Supersedes nothing.
