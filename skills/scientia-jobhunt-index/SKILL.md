---
name: scientia-jobhunt-index
description: Rebuild the derived job-hunt pipeline analytics index (development/job-hunt/pipeline.sqlite or .yaml) from the wiki/jobhunt/ frontmatter. The wiki is source-of-truth; this index is a pure, rebuildable projection that powers OB1-style funnel analytics — conversion rate, stage distribution, upcoming interviews. Part of the optional job-hunt browser-automation sub-loop. Use after scientia-jobhunt-ingest writes new pages, or any time the analytics look stale. Read-only with respect to the wiki — never edits a wiki page.
license: MIT
metadata:
  bundle: scientia
  phase: jobhunt
  order: "4"
---

# scientia-jobhunt-index

Maintain the analytics index for the job-hunt sub-loop. The index is the
scientia equivalent of OB1's SQL pipeline queries, but the durable record
lives in the wiki — this index is a derived projection that can be deleted
and rebuilt at any time.

## When to run

- After `scientia-jobhunt-ingest` writes or updates `wiki/jobhunt/` pages
  (ingest triggers this skill automatically as its last step).
- When `verify_all.py`'s `gate_jobhunt` reports the index is stale.
- Ad hoc, when you want a funnel report: `--report`.

## Procedure

Prefer the script — it owns the full rebuild, the sqlite/yaml writers, the
`pipeline.sha256` consistency sidecar, and the report:

```bash
python3 skills/scientia-jobhunt-index/scripts/rebuild_index.py \
    --repo-root "$(pwd)" \
    [--format sqlite|yaml] \
    [--report] \
    [--check]
```

The format defaults to `sqlite`; it follows `jobhunt.index.format` in
`development/config.yaml` when set. The script:

1. Walks every page under `wiki/jobhunt/{applications,interviews,contacts}`
   and parses frontmatter + the append-only `## Status History` section.
2. Rebuilds the index **from scratch** (tables: `applications`,
   `status_history`, `interviews`, `contacts`) — so it can never drift
   incrementally.
3. Writes `development/job-hunt/pipeline.<fmt>` plus a
   `development/job-hunt/pipeline.sha256` sidecar holding the sha256 of the
   canonical record set.

`--check` does not write; it recomputes the hash from the current wiki and
compares it to the sidecar, exiting `1` when they differ (or the index is
missing). This is the single divergence signal `gate_jobhunt` consumes, so
the consistency logic lives in exactly one place.

`--report` prints the funnel: current-status distribution, stage-to-stage
conversion (based on the statuses each application has *ever* reached, read
from `## Status History`), and upcoming scheduled interviews.

## Analytics powered

- **Conversion rate** — `applied → screening → interviewing → offer →
  accepted` ratios, computed from status history (so a fast process that
  skips `screening` is still counted correctly).
- **Stage funnel** — count of applications by current `status`.
- **Upcoming interviews** — `jobhunt-interview` pages with a future
  `scheduled_at` and `status: scheduled`, ordered soonest-first.

## What this skill never does

- Writes to `wiki/` (the wiki is source-of-truth; this is a one-way
  projection).
- Invents records. If a `status:` value is outside the enum in
  `[[scientia-jobhunt-ingest]]/references/STATUS_ENUM.md`, that is a
  `gate_jobhunt` CRITICAL — fix the page, then rebuild.

## Tests

```bash
cd skills/scientia-jobhunt-index && python3 -m unittest discover -s tests
```
