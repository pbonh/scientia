# Browser capture schema — what scientia-jobhunt-ingest reads

The `scientia-jobhunt-agent` worker writes structured **capture files** as
it works; `scientia-jobhunt-ingest` reads them and upserts `wiki/jobhunt/`
pages. This is the browser→wiki seam, mirroring how `raw/` feeds
`scientia-wiki-ingest`.

Captures are JSON files under
`development/job-hunt/captures/<campaign-id>/`. Each file has a `kind` and
the fields for that kind. Ingest scans the campaign directory recursively
for `*.json`, dispatches by `kind`, and is tolerant of extra fields.

Screenshots (`preview.png`, confirmation captures) live alongside the JSON;
the JSON references them by path. Never put passwords/tokens in a capture.

## kind: search

Written by a **search** task. One file per search; lists found postings.

```json
{
  "kind": "search",
  "board": "linkedin",
  "postings": [
    {
      "slug": "acme-senior-rust",
      "company": "Acme",
      "company_slug": "acme",
      "url": "https://acme.example/jobs/123",
      "role": "Senior Rust Engineer",
      "comp": "$200k–$240k",
      "location": "Remote (US)"
    }
  ]
}
```

`slug` and `company_slug` are kebab-case; if omitted, ingest derives them
from `role`/`company`. Each posting upserts a `jobhunt-company` page and a
`jobhunt-posting` page.

## kind: application

Written by **form-fill** (status `draft`) and **submit** (status
`applied`) tasks. Drives the pipeline-bearing application page.

```json
{
  "kind": "application",
  "slug": "acme-senior-rust",
  "company_slug": "acme",
  "posting_slug": "acme-senior-rust",
  "url": "https://acme.example/jobs/123",
  "role": "Senior Rust Engineer",
  "status": "applied",
  "applied_at": "2026-05-25T18:00:00Z",
  "screenshot_path": "development/job-hunt/captures/2026-05-25-rust/acme-senior-rust/preview.png",
  "resume_artifact": "development/job-hunt/artifacts/acme-senior-rust/resume.pdf",
  "resume_sha256": "…",
  "cover_letter_artifact": "development/job-hunt/artifacts/acme-senior-rust/cover.md",
  "cover_letter_sha256": "…",
  "kanban_task_id": "t_ff01",
  "submit_task_id": "t_sub01",
  "note": "submitted via Greenhouse portal"
}
```

`status` must be a member of `STATUS_ENUM.md`. Ingest validates the
transition from the page's current status and refuses illegal ones (the
history stays monotonic). The application page slug is the posting slug
(1:1 posting↔application).

## kind: interview

```json
{
  "kind": "interview",
  "slug": "acme-senior-rust-phone",
  "application_slug": "acme-senior-rust",
  "interview_type": "technical",
  "scheduled_at": "2026-06-02T17:00:00Z",
  "format": "video",
  "status": "scheduled"
}
```

## kind: contact

```json
{
  "kind": "contact",
  "slug": "jane-doe-acme",
  "company_slug": "acme",
  "name": "Jane Doe",
  "role_in_process": "recruiter",
  "email": "jane@acme.example",
  "linkedin_url": "https://linkedin.com/in/janedoe"
}
```

## What ingest does with captures

- Upserts the relevant `wiki/jobhunt/<type>/<slug>.md` page (preserving
  prior body, merging frontmatter).
- For applications: appends one append-only line to `## Status History`
  per legal transition; refuses illegal transitions.
- Regenerates the `## Job-Hunt` section of `wiki/index.md` from the
  current `wiki/jobhunt/` contents (idempotent, complete).
- Appends one `wiki/log.md` line per page touched.
- Rebuilds `development/job-hunt/pipeline.*` via scientia-jobhunt-index.
