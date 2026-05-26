---
name: scientia-jobhunt-emit
description: Read a job-hunt campaign brief and emit Hermes browser tasks for the optional job-hunt sub-loop. Two steps — (1) one search task per (board × role) in the brief's Search Plan, and (2) on demand, an author→form-fill→submit chain for human-chosen postings, where the form-fill is emitted with --triage and BLOCKS before the irreversible submit (a separate --parent-gated row). Mirrors scientia-kanban-emit's verified Hermes CLI shape but with a flat, non-Gherkin model. Idempotent. Use after scientia-jobhunt-brief; re-run with --apply once postings have been found and ingested.
license: MIT
metadata:
  bundle: scientia
  phase: jobhunt
  order: "2"
---

# scientia-jobhunt-emit

The mutator of the job-hunt sub-loop. Turns a campaign brief into durable
rows on the Hermes kanban board, assigned to `scientia-jobhunt-agent`.

Applying to a job is consequential, so emit is **two steps**:

1. **Search** (default). One `search` task per `board × role` line in the
   brief's `## 4 — Search Plan`. Workers find postings and write captures;
   `scientia-jobhunt-ingest` turns those into `wiki/jobhunt/postings/`
   pages.
2. **Apply** (`--apply <slug,…>` or `--apply-all`). For postings **you
   choose**, emit an `author → form-fill → submit` chain. You pick which
   postings to apply to after reviewing what search found — emit never
   auto-applies to everything by default.

## The chain and the human gate

For each chosen posting (identified by its `wiki/jobhunt/postings/<slug>`
page):

```
author ─▶ form-fill (--triage, BLOCKS) ─▶[human approves]─▶ submit (--parent form-fill)
```

- **author** — tailor résumé + cover letter, write artifacts.
- **form-fill** — fill the form, screenshot it, then **block**. Emitted
  with `--triage` so it parks for a human. Parented to `author`.
- **submit** — the irreversible click. Emitted with `--parent <form-fill>`,
  so the dispatcher cannot run it until the form-fill reaches `done` — i.e.
  until a human reviews the preview and promotes it (logged as
  `jobhunt-submit-approved`). This dependency edge *is* the gate.

## Idempotency keys

- search: `jobhunt-search:<campaign>:<board>:<sha16(query)>`
- author / form-fill / submit:
  `jobhunt-<stage>:<company>:<sha16(posting-url)>`

The application is the unit of work; the shared `sha16(posting-url)` ties
its three stages together and is stable across re-emits, so re-running emit
never double-applies (Hermes returns the existing task id for a known key).

## Preflight gates (skipped under --dry-run)

- `jobhunt:` block present in `development/config.yaml` (else refuse).
- The brief exists and its `wiki_snapshot` still resolves.
- **Browser provider reachable** — `check_browser_provider.py` (CDP
  endpoint answers, or the cloud key_env is set).
- The `scientia-jobhunt-agent` profile is registered with Hermes (else
  run `scientia-kanban-init` with jobhunt enabled).
- The Hermes gateway is running (else tasks sit in `todo` forever).
- Model-config drift, when `hermes.profiles` is declared (reuses
  `scientia-kanban-emit`'s drift check).

## Running

```bash
# Step 1 — search (after scientia-jobhunt-brief):
python3 skills/scientia-jobhunt-emit/scripts/jobhunt_emit.py \
    --campaign <campaign-id> --repo-root "$(pwd)" [--dry-run]

# Step 2 — apply to chosen postings (after search + ingest):
python3 skills/scientia-jobhunt-emit/scripts/jobhunt_emit.py \
    --campaign <campaign-id> --apply <posting-slug>[,<slug>...] [--dry-run]
#   or --apply-all  (power user: every known posting)
```

The Hermes CLI shape is identical to `scientia-kanban-emit` (verified):
title is **positional**, `--body` is inline, dependency edges are
`--parent` (no `--depends-on`), the human gate is `--triage` (no
`--require-approval`), workspace is `dir:<abs repo>` (absolute only). The
script writes per-task index files under
`development/job-hunt/tasks/<campaign>/` and appends an `emitted` line to
`development/log.md`.

## Hand off

Stage transitions to `emitted`. Poll with `scientia-kanban-status --tenant
jobhunt`. When `form-fill` tasks block awaiting approval, review the
preview screenshot and promote (see `scientia-jobhunt-worker` and the
README "Job-hunt" section). When tasks are `done`, run
`scientia-jobhunt-ingest`.

## What this skill never does

- Submit an application without the human gate (the `--parent` edge makes
  it impossible — `gate_jobhunt()` also enforces it post-hoc).
- Write wiki pages (ingest's job) or drive the browser (the worker's job).
- Spawn workers or start the gateway (the dispatcher / the user).
