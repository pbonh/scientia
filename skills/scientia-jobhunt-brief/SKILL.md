---
name: scientia-jobhunt-brief
description: Bind wiki/jobhunt knowledge into a campaign brief for the optional job-hunt browser-automation sub-loop. Reads the human-authored user-profile and target-criteria pages, pins the wiki's current git rev, and writes development/job-hunt/briefs/<campaign-id>/brief.md — the single artifact scientia-jobhunt-emit reads to materialise browser tasks (job search, résumé/cover authoring, form pre-fill, human-gated submit). The wiki→browser seam, modelled on scientia-wiki-bind. Use once per campaign, after authoring at least one wiki/jobhunt/criteria page and a profile page, and only when development/config.yaml declares a jobhunt block.
license: MIT
metadata:
  bundle: scientia
  phase: jobhunt
  order: "1"
---

# scientia-jobhunt-brief

The wiki→browser seam of the job-hunt sub-loop. This is to the job-hunt
phase what `scientia-wiki-bind` is to the intent phase: it freezes a slice
of wiki knowledge — your profile and what you're looking for — into a
pinned brief that drives every downstream browser task.

The brief lives under `development/job-hunt/briefs/`, deliberately **not**
`development/manifests/`. A job-hunt campaign is not an OpenSpec tenant;
keeping briefs out of `manifests/` is what stops the mainline orchestrator
from offering `scientia-intent-proposal` for a phantom "jobhunt" tenant.

## Inputs

1. `campaign` — a slug; the campaign-id becomes `<today>-<slug>` (or is
   used verbatim if it already starts `YYYY-MM-DD-`).
2. *(resolved)* the user-profile page and one or more target-criteria
   pages — see `references/WIKI_SOURCE_SCHEMA.md`.

## Preflight gates

Refuse to bind if any of:

- `development/config.yaml` has no `jobhunt:` block (the sub-loop is OFF —
  uncomment it and re-run `scientia-kanban-init` first).
- No profile page resolves (set `jobhunt.user_profile_page` or pass
  `--profile`, or have exactly one page under `wiki/jobhunt/profile/`).
- No `wiki/jobhunt/criteria/<slug>.md` page exists.
- The wiki has uncommitted changes — the snapshot pin would be ambiguous.
  Override by committing, or pass `--allow-dirty` (records `wiki_dirty:
  true` in the brief frontmatter). Because `wiki/jobhunt/` is committed
  (it lives on a private remote — see the README PII note), a clean commit
  before binding is the norm.
- A brief already exists for the campaign-id (start a new campaign with a
  fresh `--campaign` slug rather than overwriting an audit artifact).

## Procedure

Prefer the script — it owns the preflights, the snapshot pin, the slice
assembly, the Search Plan, and the `development/log.md` append:

```bash
python3 skills/scientia-jobhunt-brief/scripts/brief.py \
    --campaign <slug> \
    --repo-root "$(pwd)" \
    [--profile wiki/jobhunt/profile/<user>.md] \
    [--criteria <slug,slug>] \
    [--allow-dirty]
```

It writes `development/job-hunt/briefs/<campaign-id>/brief.md` with
frontmatter (`type: jobhunt-brief`, `campaign_id`, `wiki_snapshot`,
`wiki_dirty`, `user_profile_page`, `criteria_pages`, `provider`,
`scientia_schema`, `created`) and four slices:

- **## 1 — User Profile** — Contact / Skills / Experience / Preferences,
  inlined from the profile page.
- **## 2 — Target Criteria** — one bullet per criteria page with its
  structured fields.
- **## 3 — Résumé Source** — the `resume_source:` the authoring tasks
  tailor from.
- **## 4 — Search Plan** — one `board × role` search line per pair; emit
  turns each into a search task.

Then it appends to `development/log.md`:

```
- <ISO-Z> — scientia-jobhunt-brief — brief-bound — <campaign-id> — wiki_snapshot=<rev8> provider=<p>
```

## Hand off

Stage transitions to `briefed`. Recommended next skill:
`scientia-jobhunt-emit`.

## What this skill never does

- Edits the wiki, or the profile/criteria pages it reads.
- Drives the browser or talks to Hermes — that's emit + the worker.
- Writes under `development/manifests/` (would pollute the OpenSpec tenant
  scanner — see above).
