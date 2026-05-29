---
name: ingest-source
description: Ingests a single raw source (PDF, markdown, HTML) into the KG wiki. Creates Source/Entity/Claim/Question pages with an LLM-rated base confidence, runs inline contradiction checks against immediate wiki neighbors, dedupes near-duplicate claims in place, and records bidirectional contradicts edges non-destructively. Activate when adding a new document to the knowledge base, or when the user says "ingest this", "add this source", or "read this into the wiki".
metadata:
  stage: ingest
  version: "1.0"
---

# ingest-source

Turn ONE raw source document into typed knowledge-graph pages. You supply the
judgment (what the claims are, how confident each is, what contradicts what);
the deterministic `kg_pipeline` package owns every derived number. You never set
`effective` by hand — `kg_pipeline.confidence.recompute` does that.

## Inputs

- A single path to a raw file under `sources/` (resolve via
  `kg_pipeline.paths.sources_dir()`).

## Outputs

- One `wiki/source-<slug>.md` registering the source.
- Zero or more new `wiki/entity-*.md`, `wiki/claim-*.md`, `wiki/question-*.md`.
- Updates to existing pages (added links, added sources to a claim's
  `sources:` list).

## Page types and frontmatter

Every page MUST set `type` (an untyped page fails `wiki.validate_page`). File
names are kebab-case and type-prefixed: `claim-rag-rediscovers-knowledge.md`.

```yaml
# entity / source / question — no confidence block
type: entity            # or: source | question
id: entity-llm-wiki
title: "LLM Wiki"
created: 2026-05-28
sources:
  - source-karpathy-2026
```

A **source** page additionally carries `kind:` (`publication` | `post-mortem` |
`article` | …) — `seed-proposal` and `grill-proposal` key off it. A **claim**
page carries the confidence block, with **only `base` set by you**:

```yaml
type: claim
id: claim-rag-rediscovers-knowledge
title: "RAG rediscovers knowledge on every query"
created: 2026-05-28
sources:
  - source-karpathy-2026
confidence:
  base: 0.85            # YOUR LLM rating in [0,1], set once, never edited
# source_count / contradicted / effective / inputs_hash are written by recompute
```

Edges are wiki-links in the body; the kind is in the alias slot (ADR-0002):
`[[claim-x | supports]]`, `[[claim-y | contradicts]]`, `[[entity-z]]` (mentions).

## Procedure

1. **Read the whole source.** Resolve its path under `sources/`.
2. **Register the source page** (`type: source`, set `kind:` when known).
3. **Extract atomic claims, entities, and open questions.** One claim per
   distinct assertion — never bundle unrelated ideas (avoids page sprawl).
4. **For each candidate claim, check for a near-duplicate** among existing claim
   pages (`kg_pipeline.wiki.list_pages(wiki_dir, type="claim")`). If it closely
   matches one (your judgment), **update that page in place**: append this
   source to its `sources:` list. Do **not** mint a duplicate.
5. **Otherwise create the claim page** and set `confidence.base` to your rating.
6. **Inline contradiction check** against immediate neighbors
   (`kg_pipeline.wiki.neighbors(page, wiki_dir, hops=1)`). On a real
   contradiction, append a **bidirectional** `contradicts` edge — add
   `[[other | contradicts]]` to this claim's body AND `[[this | contradicts]]`
   to the other's body. **Never rewrite the older claim's text** (ADR-0009).
7. **Recompute confidence** for every claim you created or whose `sources:` /
   contradiction state changed: `confidence.recompute(claim, wiki_dir, config)`
   then `wiki.write_page(claim)`. This fills `effective`, `source_count`,
   `contradicted`, and `inputs_hash`.
8. **Update `wiki/index.md`** (if present) and append a one-line entry to
   `wiki/log.md` per page touched.

Use `kg_pipeline.paths` for every path; never hard-code one.

## Decision rules

- Dedupe-in-place over near-duplicates (LLM judgment + token similarity).
- A detected contradiction adds a bidirectional `contradicts` edge; the older
  claim is left intact.
- Set `base` only; `effective` is always derived. Wiki growth is monotonic — you
  never delete a page.

## Low-confidence handling (mode key: `ingest_source`, default `autonomous`)

- `autonomous`: create the page with your estimated `base`. Continue.
- `pause_and_ask`: if `base < thresholds.low_confidence_floor` (0.45), emit
  `proposals/<change-id>/question-for-operator.md` via
  `kg_pipeline.paths.question_for_operator_path` and halt.

## Acceptance behavior (spec: wiki-maintenance)

- Ingesting a source registers the source page and sets `base` on each new
  claim — never `effective` directly.
- A near-duplicate claim updates the existing page (new source appended) rather
  than creating a new one.
- A detected contradiction adds a bidirectional `contradicts` edge and leaves
  the older claim's text intact.
