# 04 — Job-hunt browser automation (optional sub-loop)

**Audience.** Someone running their own job search who wants the agent to
do the legwork — search boards, tailor a résumé/cover letter from their
profile, pre-fill applications — while keeping the actual *submit* under
human control.

**Setting.** Dana keeps a scientia repo as a personal knowledge base on a
**private** git remote. She wants to drive a focused Rust/backend search.
The job-hunt sub-loop is optional and off by default; this walkthrough
turns it on and runs one campaign end to end.

This sub-loop is parallel to — never through — the OpenSpec intent phase.
It reuses Hermes for durable execution and the browser, and the wiki as the
source of truth.

```
wiki/jobhunt/ ─► brief ─► emit ─► [search] ─► ingest ─► postings in wiki
                          └─► emit --apply ─► [author → form-fill(gate) → submit] ─► ingest ─► application: applied
                                                                                                   │
                                                       development/job-hunt/pipeline.sqlite ◄───────┘
```

## 0. Prerequisites

- The host is Hermes-ready (`scientia-kanban-init` has been run at least
  once; the gateway is up).
- A Chrome you're logged into the job sites with, launched for remote
  debugging:

  ```bash
  google-chrome --remote-debugging-port=9222 \
    --user-data-dir="$HOME/.cache/jobhunt-chrome"
  # log in to LinkedIn / Greenhouse / etc. in this window once
  ```

## 1. Enable the feature

Uncomment the `jobhunt:` block in `development/config.yaml`:

```yaml
jobhunt:
  user_profile_page: wiki/jobhunt/profile/me.md
  browser:
    provider: cdp
    cdp_endpoint: http://127.0.0.1:9222
  index:
    format: sqlite
```

Re-run `scientia-kanban-init`. With the block present it also: creates the
`scientia-jobhunt-agent` profile, symlinks the scientia skills into it,
enables its browser toolset (`apply_browser_toolset.py`), and preflights
the CDP endpoint (`check_browser_provider.py` — refuses if Chrome isn't
listening on 9222).

## 2. Author your profile + criteria

These are the only hand-written job-hunt pages; everything else is
generated. Schema: `scientia-jobhunt-ingest/references/PAGE_TEMPLATES.md`.

`wiki/jobhunt/profile/me.md` (`jobhunt-user-profile`) — Contact / Skills /
Experience / Preferences, plus a `resume_source:` pointing at the base
résumé to tailor from.

`wiki/jobhunt/criteria/senior-rust.md` (`jobhunt-target-criteria`):

```yaml
---
title: "Target criteria — senior-rust"
type: jobhunt-target-criteria
roles: ["Senior Rust Engineer", "Staff Backend Engineer"]
locations: ["Remote (US)"]
seniority: senior
comp_floor: 200000
comp_currency: USD
boards: ["linkedin", "greenhouse"]
exclusions: ["crypto"]
---
```

Commit them (the brief pins the wiki's git rev — that's why
`wiki/jobhunt/` is committed, on a private remote).

## 3. Bind the brief

```bash
# via the orchestrator: "use scientia-jobhunt-brief for campaign senior-rust"
python3 skills/scientia-jobhunt-brief/scripts/brief.py \
    --campaign senior-rust --repo-root "$(pwd)"
```

Writes `development/job-hunt/briefs/2026-05-25-senior-rust/brief.md` with a
`## 4 — Search Plan` (one line per board × role) pinned at the wiki rev.

## 4. Emit search tasks

```bash
python3 skills/scientia-jobhunt-emit/scripts/jobhunt_emit.py \
    --campaign 2026-05-25-senior-rust --repo-root "$(pwd)"
```

One `search` task per board × role lands on the `jobhunt` kanban tenant,
assigned to `scientia-jobhunt-agent`. The dispatcher spawns workers that
drive your Chrome, collect matching postings, and write captures under
`development/job-hunt/captures/2026-05-25-senior-rust/search/`.

Poll: `hermes kanban list --tenant jobhunt` (or
`scientia-kanban-status --tenant jobhunt`).

## 5. Ingest the postings

```bash
python3 skills/scientia-jobhunt-ingest/scripts/jobhunt_ingest.py \
    --campaign 2026-05-25-senior-rust --repo-root "$(pwd)"
```

Turns captures into `wiki/jobhunt/companies/*` and
`wiki/jobhunt/postings/*` pages, refreshes the `## Job-Hunt` section of
`wiki/index.md`, and rebuilds `development/job-hunt/pipeline.sqlite`.
Review the postings in the wiki and pick which to apply to.

## 6. Apply (author → form-fill → human gate → submit)

```bash
python3 skills/scientia-jobhunt-emit/scripts/jobhunt_emit.py \
    --campaign 2026-05-25-senior-rust \
    --apply acme-senior-rust,globex-staff-backend
```

For each chosen posting this emits a three-stage chain:

1. **author** — tailors résumé + cover letter into
   `development/job-hunt/artifacts/<slug>/`.
2. **form-fill** (`--triage`) — fills the application form, screenshots it
   to `…/captures/<campaign>/<slug>/preview.png`, and **blocks**. It never
   clicks Submit.
3. **submit** (`--parent` form-fill) — cannot run until you release the
   gate.

`scientia-jobhunt-emit` then surfaces the gated tasks (state
`jobhunt.phase == "gated"`).

## 7. The human gate

For each blocked form-fill:

```bash
hermes kanban show <form-fill-id>          # read its handoff
open development/job-hunt/captures/2026-05-25-senior-rust/acme-senior-rust/preview.png
```

If the filled form looks right, record approval and release the gate:

```bash
printf '%s\n' "- $(date -u +%Y-%m-%dT%H:%M:%SZ) — orchestrator — jobhunt-submit-approved — 2026-05-25-senior-rust — app=acme-senior-rust" >> development/log.md
hermes kanban unblock <form-fill-id>
```

Once the form-fill reaches `done`, Hermes dispatches the parented `submit`
task, which clicks Submit and captures the confirmation. (The
`jobhunt-submit-approved` line is what `gate_jobhunt` checks; skipping it
makes `verify_all.py` fail CRITICAL on the resulting `applied` page.)

## 8. Ingest results and read the funnel

```bash
python3 skills/scientia-jobhunt-ingest/scripts/jobhunt_ingest.py \
    --campaign 2026-05-25-senior-rust --repo-root "$(pwd)"
python3 skills/scientia-jobhunt-index/scripts/rebuild_index.py \
    --repo-root "$(pwd)" --report
```

Application pages now read `status: applied` with an append-only
`## Status History`. As recruiters reply, drop `interview` / `contact`
captures (or re-run search ingest) and the funnel updates. Later status
changes (`applied → screening → interviewing → offer → accepted`) come in
through the same ingest, validated against the transition graph in
`STATUS_ENUM.md`.

## 9. Verify

```bash
skills/scientia/scripts/verify_all.py --repo "$(pwd)"
```

`gate_jobhunt` checks frontmatter + status enum, illegal transitions, the
index-vs-wiki consistency, orphan applications, and — critically — that
every `applied` application has a logged human approval.

## What stays manual

- Choosing which postings to apply to (`--apply`).
- Approving each submit (the gate).
- Any login / 2FA in the attached Chrome (the worker blocks on
  `missing-credential` rather than handling secrets).
