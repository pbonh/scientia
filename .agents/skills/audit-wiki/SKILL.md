---
name: audit-wiki
description: Performs a full-wiki sweep for cross-page contradictions, stale confidence rollups, and orphan pages, writing an audit-report.md. Optional and non-destructive — never deletes a page. Activate periodically, when ingest-source has been called many times since the last audit, or when the pipeline-controller detects the wiki is older than the configured staleness window.
metadata:
  stage: maintenance
  version: "1.0"
---

# audit-wiki

A periodic, non-destructive health check over the whole knowledge graph. It
refreshes every claim's derived confidence, looks for contradictions that
single-source ingest missed, and flags structural problems — but it **deletes
nothing** (ADR-0009). Pages are edited or flagged, never removed.

## Inputs

- The whole `wiki/` directory (`kg_pipeline.paths.wiki_dir()`).

## Outputs

- Updated claim pages (refreshed `effective` rollups) written in place.
- `wiki/audit-report.md` summarizing what changed and what needs attention.

## Procedure

1. **Recompute all confidence.** Call
   `kg_pipeline.confidence.recompute_all(wiki_dir, config)`. It rewrites only
   claims whose derived block changed and returns the count updated (a clean
   wiki returns 0 — the operation is idempotent).
2. **Batch contradiction scan.** For each claim, compare against the other
   claims (your judgment) for semantic contradiction. When you find a real one,
   add a **bidirectional** `contradicts` edge between the two Claim pages only
   — never between non-claim pages, and never rewrite the older claim. Then
   recompute the two affected claims.
3. **Flag orphans.** A page with no inbound wiki-links is an orphan. **List it
   in the report; do not delete it.**
4. **Flag broken links and missing pages** (a `[[target]]` that resolves to no
   page; a concept/entity mentioned inline with no page of its own).
5. **Write `audit-report.md`**: claims recomputed, new contradiction edges,
   orphans, broken links, missing pages — with `kg_pipeline.paths` used for
   every path.

## Decision rules

- Add new `contradicts` edges only between Claim pages.
- Do not delete pages, even when orphaned — flag them.
- All confidence changes go through `recompute_all`; never hand-edit
  `effective`.

## Low-confidence handling (mode key: `audit_wiki`, default `autonomous`)

Audit is read-mostly and revisable; it runs `autonomous` by default. Surface
anything ambiguous (a suspected-but-uncertain contradiction) in the report for a
human to adjudicate rather than asserting an edge you are unsure of.

## Acceptance behavior (spec: wiki-maintenance)

- `audit-wiki` recomputes all claims and **flags an orphan in the report while
  the orphan page remains on disk.**
