---
name: scientia-jobhunt-ingest
description: The browser→wiki seam of the optional job-hunt sub-loop. Reads the JSON capture files written by scientia-jobhunt-agent workers under development/job-hunt/captures/<campaign>/ and upserts wiki/jobhunt/{companies,postings,applications,interviews,contacts} pages. Application status transitions are append-only and validated against STATUS_ENUM.md (illegal transitions refused). Regenerates the wiki/index.md "## Job-Hunt" section, appends wiki/log.md, and rebuilds the pipeline analytics index. Mirrors scientia-wiki-ingest (raw→wiki) and scientia-ingest-evidence (handoff parsing). Use after job-hunt kanban tasks complete.
license: MIT
metadata:
  bundle: scientia
  phase: jobhunt
  order: "3"
---

# scientia-jobhunt-ingest

Closes the job-hunt loop: turns what the browser workers captured into
durable wiki knowledge. This is to the job-hunt sub-loop what
`scientia-wiki-ingest` is to `raw/` — capture files in, wiki pages out.

## Inputs

JSON capture files under `development/job-hunt/captures/<campaign>/`,
written by the workers (schema: `references/CAPTURE_SCHEMA.md`). Four
kinds: `search`, `application`, `interview`, `contact`.

## Procedure

Prefer the script:

```bash
python3 skills/scientia-jobhunt-ingest/scripts/jobhunt_ingest.py \
    --campaign <campaign-id> --repo-root "$(pwd)" [--no-index]
```

It:

1. Scans the campaign's capture dir for `*.json`, dispatches by `kind`.
2. **Upserts** the relevant `wiki/jobhunt/<type>/<slug>.md` page — preserves
   any existing body, merges frontmatter, bumps `updated:`. Page schema:
   `references/PAGE_TEMPLATES.md`.
3. For **applications**, advances `status` only along a legal edge in
   `references/STATUS_ENUM.md`, appending one line to the append-only
   `## Status History`. Illegal transitions are refused (reported, status
   left unchanged) — the history stays monotonic and audit-clean.
4. **Regenerates** the `## Job-Hunt` section of `wiki/index.md` from the
   current `wiki/jobhunt/` contents (idempotent, complete — so every page
   is listed for `scientia-wiki-lint`).
5. Appends one `wiki/log.md` line per page touched.
6. Rebuilds `development/job-hunt/pipeline.*` via `scientia-jobhunt-index`
   (skip with `--no-index`; the format follows `jobhunt.index.format`).

## Discipline

- **Source-of-truth is the wiki.** This skill writes wiki pages; the
  pipeline index is a derived projection.
- **Never invents a status.** A capture whose `status` is outside the enum
  is reported as an error, not written.
- **Never edits `wiki/concepts/` or `wiki/entities/`** — job-hunt records
  live only under `wiki/jobhunt/`.
- **PII** in captures (names, emails) lands in `wiki/jobhunt/`, which is
  committed to a private remote (see README). Secrets must never appear in
  a capture; this skill writes whatever the (redacting) worker produced.

## Hand off

After ingest, run/let it run `scientia-jobhunt-index --report` for the
funnel, and `scientia-jobhunt-emit --apply <slug>` to apply to newly-found
postings. `verify_all.py`'s `gate_jobhunt` will validate the pages and the
human-gate audit trail.

## Tests

```bash
cd skills/scientia-jobhunt-ingest && python3 -m unittest discover -s tests
```
