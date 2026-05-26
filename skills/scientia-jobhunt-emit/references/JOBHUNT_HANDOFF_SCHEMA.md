# Job-hunt Required Handoff schema

Every job-hunt kanban task body inlines this block verbatim. The
`scientia-jobhunt-agent` worker fills it in as part of its
`complete`/`block` result. `scientia-jobhunt-ingest` parses these blocks to
write `wiki/jobhunt/` pages, exactly as `scientia-ingest-evidence` parses
the mainline handoff.

It extends the standard handoff (`scientia-kanban-emit/references/HANDOFF_SCHEMA.md`)
with job-hunt-specific fields.

```markdown
## Required Handoff

Fill in every field. "none" / "none known" / empty are the sentinels for
absence.

- **summary** — Short prose: what you did this task.
- **verification** — What you checked and the outcome (e.g. "captured 7
  postings to search/linkedin-…json"; "form preview screenshot written").
- **changed_files** — YAML list of paths you wrote (captures, artifacts),
  relative to repo root.
- **residual_risk** — Known unknowns for the next reader.

  --- job-hunt fields ---

- **task_kind** — one of: search | author | form-fill | submit.
- **campaign_id** — the `@jobhunt-brief` value from the task body.
- **posting_url** — the target posting URL (search: "none"; one URL for
  author/form-fill/submit).
- **company** — company name/slug for the target (or "none" for search).
- **postings_captured** — YAML list of `{url, company, role}` you found
  (search tasks only; "none" otherwise).
- **application_status** — the status this task moves the application to,
  from STATUS_ENUM.md. `form-fill` → `draft`; a completed `submit` →
  `applied`; otherwise "none".
- **gate_state** — `awaiting-approval` for a blocked form-fill;
  `approved-submitted` for a completed submit; otherwise "none".
- **screenshot_path** — path to the filled-form preview (form-fill) or the
  confirmation capture (submit); "none" otherwise.
- **resume_artifact** / **resume_sha256** — authored résumé path + sha256
  (author tasks; "none" otherwise).
- **cover_letter_artifact** / **cover_letter_sha256** — likewise.
- **interview_datetime** — ISO-8601 of any interview the flow surfaced
  (e.g. a scheduling email seen during submit), else "none".
- **contacts** — YAML list of `{name, role_in_process, email|linkedin}`
  recruiters/HMs encountered, else "none".
- **blocked_reason** — populated only when you `block` (e.g.
  `awaiting human submit approval`, `cdp-attach-failed`,
  `missing-credential`); empty when completing.
```

Notes:

- A **form-fill** task always ends in `block` with
  `gate_state: awaiting-approval` and a `screenshot_path` — never in a
  submitted application. `gate_jobhunt()` enforces this.
- Never put passwords, tokens, or OTP codes in any field.
- Keep `postings_captured` and `contacts` as compact YAML lists so
  `scientia-jobhunt-ingest`'s parser can read them.
