---
title: "ADR-0009: Keep all wiki operations non-destructive"
adr_id: ADR-0009
status: accepted
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Non-destructive wiki: no skill deletes a page or rewrites an older claim (ASR-8)."
shared_types: []
tags: [spec-driven-development, wiki-maintenance, provenance]
created: 2026-05-27
---

# ADR-0009: Keep all wiki operations non-destructive

## Y-Statement

**In the context of** `ingest-source` and `audit-wiki` mutating the KG as new
sources arrive and confidence is recomputed,
**facing** the risks of false contradictions, stale synthesis, and lost
provenance,
**we decided for** non-destructive operations only — dedupe updates an existing
claim in place, a contradiction appends a *bidirectional* `contradicts` edge
while leaving the older claim's text intact, and orphans are flagged rather
than removed,
**and against** overwrite-on-conflict, automatic contradiction resolution, or
auto-pruning of orphaned pages,
**to achieve** durable provenance, compounding knowledge, and human
adjudication of genuine conflicts (ASR-8),
**accepting** that the wiki grows monotonically and that contradictions and
orphans accumulate until a human prunes them — there is no automatic garbage
collection.

## Architecturally Significant Requirement

ASR-8: ingest and audit never delete pages; a contradiction is recorded as an
edge, not a rewrite; a flagged orphan remains on disk. This protects against
the wiki-lint pitfall of "resolving" a flagged contradiction that is actually a
nuanced distinction, and the compounding-knowledge pitfall of entrenching stale
information by silent overwrite.

## Options Considered

### Option A — Overwrite older claim on conflict / auto-resolve contradictions
*Pros:* keeps the wiki "clean" and small.
*Cons:* destroys provenance; an LLM-misjudged contradiction silently loses the
earlier, possibly-correct claim. Fails ASR-8.

### Option B — Auto-prune orphans during audit
*Pros:* tidy index.
*Cons:* a page that looks orphaned may be a hub the link-checker missed;
deletion is irreversible. The wiki-lint pitfall warns against exactly this.

### Option C — Non-destructive: append, flag, never delete (chosen)
Dedupe-in-place; bidirectional `contradicts` edge; orphans flagged in the audit
report.
*Pros:* full provenance; human stays in the loop; reversible. **Chosen.**
*Cons:* monotonic growth; manual pruning needed eventually.

## Consequences

- The older side of a contradiction is never rewritten; both claims persist,
  linked by a `contradicts` edge, and the floor caps their `effective`
  (ADR-0003).
- `audit-wiki` produces an `audit-report.md` listing orphans and cross-page
  contradictions; it edits confidence rollups but deletes nothing.
- A future "prune/refactor" capability, if needed, is a separate
  human-initiated change — never an automatic step.

## Supersession

Supersedes nothing.
