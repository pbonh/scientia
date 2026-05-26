# Brief input schema — what scientia-jobhunt-brief reads from the wiki

`scientia-jobhunt-brief` reads exactly two kinds of human-authored wiki
pages and pins them into a campaign brief. The full frontmatter templates
for every job-hunt page type live in
`[[scientia-jobhunt-ingest]]/references/PAGE_TEMPLATES.md`; this file
records only the fields the brief consumes, so the contract stays explicit.

## `jobhunt-user-profile` — `wiki/jobhunt/profile/<user>.md`

The brief resolves the profile page in this order: `--profile` flag →
`jobhunt.user_profile_page` in `development/config.yaml` → the single page
under `wiki/jobhunt/profile/` (refuses if there is more than one and none
was specified).

Consumed:

| Source | Used for |
|---|---|
| frontmatter `resume_source:` | the brief's `## 3 — Résumé Source` (what authoring tasks tailor from) |
| `## Contact` section | inlined into `## 1 — User Profile` (drives form-fill) |
| `## Skills` section | inlined; later used for posting-match scoring |
| `## Experience` section | inlined; résumé tailoring context |
| `## Preferences` section | inlined; always-on constraints |

Missing sections are rendered as `_(empty on profile page)_` rather than
failing — a thin profile still produces a valid brief.

## `jobhunt-target-criteria` — `wiki/jobhunt/criteria/<slug>.md`

The brief resolves criteria pages from `--criteria <slug,slug>` or, by
default, every page under `wiki/jobhunt/criteria/`. At least one must
exist or the brief refuses.

Consumed (all from frontmatter):

| Field | Type | Used for |
|---|---|---|
| `roles:` | list | one search query per role |
| `locations:` | list | search filter, recorded in the brief |
| `seniority:` | scalar | recorded for the worker's filter pass |
| `comp_floor:` / `comp_currency:` | scalar | recorded; worker discards below-floor postings |
| `boards:` | list | one search task per (board × role) pair |
| `exclusions:` | list | recorded; worker skips matching companies/industries |

## Output

`development/job-hunt/briefs/<campaign-id>/brief.md` — frontmatter pins
`wiki_snapshot` (the wiki's git HEAD), `provider` (from
`jobhunt.browser.provider`), `user_profile_page`, and `criteria_pages`;
the body carries slices `## 1 — User Profile`, `## 2 — Target Criteria`,
`## 3 — Résumé Source`, `## 4 — Search Plan`. `scientia-jobhunt-emit`
reads this file and nothing else from the wiki.
