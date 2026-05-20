---
name: scientia-wiki-ingest
description: Turn one source document in raw/ into a summary page plus zero or more concept and entity pages in wiki/. Updates wiki/index.md and appends to wiki/log.md. Use whenever a new raw source (article, PDF, transcript, README) lands in raw/ and its knowledge should enter the wiki. Do not use for synthesizing across multiple sources — that is scientia-ingest-synthesize's job.
license: MIT
metadata:
  bundle: scientia
  phase: wiki
  order: "2"
---

# scientia-wiki-ingest

Ingest one `raw/<source>` document into the wiki, producing:

1. **One summary page** at `wiki/summaries/<source-slug>.md` — what the
   source says, in your own words, with key terms wiki-linked.
2. **Zero or more concept pages** at `wiki/concepts/<slug>.md` — one per
   distinct concept the source introduces or substantially refines.
3. **Zero or more entity pages** at `wiki/entities/<slug>.md` — one per
   distinct tool, product, person, or organization the source names.
4. **Updates** to `wiki/index.md` (new rows in the relevant tables) and
   `wiki/log.md` (one append per page created or updated).

## Procedure

1. Read the source from `raw/<source>` fully. PDFs/HTML may need
   conversion; use whatever tool is available to your client (the
   scientia bundle does not ship its own extractor in v0.1).

2. Identify the distinct claims, concepts, and entities. Apply the
   **atomic-claim** discipline: each concept page is one claim, one
   page; do not bundle unrelated ideas.

3. Write the summary first. Use this frontmatter:

   ```yaml
   ---
   title: "<source title>"
   type: summary
   tags: [summary, <domain-tags>]
   created: <YYYY-MM-DD>
   sources: ["raw/<source-filename>"]
   confidence: high|medium|low
   ---
   ```

   Body sections (recommended):
   - `## Overview` — 2–5 paragraphs, in your own words.
   - `## Key Claims` — bulleted, each with `[[concepts/<slug>]]` links.
   - `## Source Metadata` — type, owner, URL, license, ingested-on.
   - `## Relevant Concepts` — bullet list of `[[concepts/<slug>]]`
     pages created or extended by this ingest.

4. Write each new concept page using this template:

   ```yaml
   ---
   title: "<Concept Name>"
   type: concept
   tags: [concept, <domain-tags>]
   created: <YYYY-MM-DD>
   updated: <YYYY-MM-DD>
   sources: ["raw/<source>"]
   confidence: high|medium|low
   ---

   ## Definition
   ## How It Works
   ## Key Parameters
   ## When To Use
   ## Risks & Pitfalls
   ## Related Concepts
   ## Sources
   ```

   For each concept the source *extends* (rather than introduces),
   update the existing concept page and add the new source to its
   `sources:` list. Bump `updated:`. Append to that page's relevant
   section, preserving prior content.

5. Write each new entity page using this template:

   ```yaml
   ---
   title: "<Entity Name>"
   type: entity
   tags: [entity, <kind>]
   created: <YYYY-MM-DD>
   updated: <YYYY-MM-DD>
   sources: ["raw/<source>"]
   confidence: high|medium|low
   ---

   ## Overview
   ## Characteristics
   ## Common Strategies
   ## Sources
   ```

6. Update `wiki/index.md`:
   - Add a row to the **Summaries** table for the new summary page.
   - Add rows to **Concepts** and **Entities** tables for new pages.
   - Bump the `updated:` frontmatter date.

7. Append to `wiki/log.md` one line per page touched:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-wiki-ingest — created — concepts/<slug>.md — from raw/<source>' >> wiki/log.md
   ```

## Quality bar

- Every concept page must explain *what* and *when to use* in plain
  prose; agents downstream rely on this.
- Every entity page must include at least one common strategy or
  representative usage.
- Wiki-links (`[[concepts/<slug>]]`, `[[entities/<slug>]]`) must
  resolve. Run `scientia-wiki-lint` after a batch ingest to verify.
- `confidence:` is honest. Use `medium` or `low` when the source is
  speculative or single-witness.

## What this skill never does

- Synthesizes across multiple sources — that is
  `scientia-ingest-synthesize`'s job, and produces `wiki/syntheses/`
  pages as *proposed edits*, not direct writes to concepts/entities.
- Touches `development/` or `openspec/`.
- Removes pages — pages are only edited, never deleted, by ingest.
