# Job-hunt wiki page templates

The optional job-hunt sub-loop stores its operational records as wiki
pages under a dedicated `wiki/jobhunt/` subtree — deliberately **outside**
`wiki/concepts/` and `wiki/entities/` so they do not pollute the
strategic-DDD pass (`scientia-wiki-strategy`), the manifest binder
(`scientia-wiki-bind`), or the synthesis loop. These are records, not
domain knowledge.

```
wiki/jobhunt/
  profile/<user>.md       # jobhunt-user-profile     (brief INPUT — human-authored)
  criteria/<slug>.md      # jobhunt-target-criteria  (brief INPUT — human-authored)
  companies/<slug>.md     # jobhunt-company          (ingest output)
  postings/<slug>.md      # jobhunt-posting          (ingest output)
  applications/<slug>.md  # jobhunt-application      (ingest output — pipeline-bearing)
  interviews/<slug>.md    # jobhunt-interview        (ingest output)
  contacts/<slug>.md      # jobhunt-contact          (ingest output)
```

Every page keeps the **base scientia frontmatter** that
`scientia-wiki-lint` and `verify_all.py`'s `gate_wiki_lint` expect
(`title`, `type`, `tags`, `created`, `updated`, `sources`, `confidence`)
plus the type-specific keys below. `sources:` lists the provenance of the
record (a `raw/` path, a `development/job-hunt/captures/...` path, or a
posting URL) so every record is traceable back to its browser capture.

PII note: these pages contain personal data (your contact details,
recruiter names/emails). The repo is expected to live on a **private
remote**. Do not store passwords or tokens here — only handles. Generated
artifacts (résumé/cover PDFs, form screenshots) live under
`development/job-hunt/artifacts/` and `development/job-hunt/captures/`,
which are `.gitignore`'d; the application page records only their path +
a `*_sha256` for integrity.

---

## jobhunt-user-profile  (brief input)

`wiki/jobhunt/profile/<user>.md`. Human-authored seed; the brief reads it.

```yaml
---
title: "<Your Name> — job-hunt profile"
type: jobhunt-user-profile
tags: [jobhunt, profile]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
sources: ["self"]
confidence: high
resume_source: development/job-hunt/artifacts/base/resume.md   # canonical résumé to tailor from
---

## Contact
<!-- name, email, phone, location, links — used to fill application forms -->

## Skills
<!-- bulleted skills, used for posting match scoring and résumé tailoring -->

## Experience
<!-- reverse-chronological roles; each a short bullet block -->

## Preferences
<!-- visa/relocation/comp constraints that always apply -->
```

## jobhunt-target-criteria  (brief input)

`wiki/jobhunt/criteria/<slug>.md`. Human-authored; one page per campaign
or search theme. The brief's Search Plan is computed from these.

```yaml
---
title: "Target criteria — <slug>"
type: jobhunt-target-criteria
tags: [jobhunt, criteria]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
sources: ["self"]
confidence: high
roles: ["Senior Rust Engineer", "Staff Backend Engineer"]
locations: ["Remote (US)", "San Francisco, CA"]
seniority: senior            # junior | mid | senior | staff | principal
comp_floor: 180000           # integer, in comp_currency
comp_currency: USD
remote_policy: [remote, hybrid]   # subset of remote | hybrid | onsite
boards: ["linkedin", "greenhouse", "lever"]
exclusions: ["crypto", "defense"]
---

## Notes
<!-- free-text nuance the structured fields can't capture -->
```

---

## jobhunt-company  (ingest output)

`wiki/jobhunt/companies/<slug>.md`.

```yaml
---
title: "<Company Name>"
type: jobhunt-company
tags: [jobhunt, company]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
sources: ["<posting-url-or-capture-path>"]
confidence: high|medium|low
careers_url: "https://..."
ats: greenhouse              # greenhouse | lever | workday | ashby | other | unknown
industry: "<industry>"
remote_policy: remote        # remote | hybrid | onsite | unknown
location: "<HQ or primary location>"
---

## Overview
## Notes
```

## jobhunt-posting  (ingest output)

`wiki/jobhunt/postings/<slug>.md`.

```yaml
---
title: "<Role Title> @ <Company>"
type: jobhunt-posting
tags: [jobhunt, posting]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
sources: ["<posting-url>"]
confidence: high|medium|low
company: "[[jobhunt/companies/<slug>]]"
posting_url: "https://..."
posting_id: "<stable ATS id, or sha of url>"
role: "<role title>"
location: "<location>"
comp: "<as advertised, free text>"
source_board: linkedin       # linkedin | greenhouse | lever | company-site | referral | other
found_at: <ISO-Z>
match_score: 0.0             # optional 0..1, set by search task
---

## Summary
## Requirements
## Nice-to-haves
```

## jobhunt-application  (ingest output — pipeline-bearing)

`wiki/jobhunt/applications/<slug>.md`. This is the page the funnel index
is built from. `status` is drawn from `STATUS_ENUM.md`.

```yaml
---
title: "Application — <Role> @ <Company>"
type: jobhunt-application
tags: [jobhunt, application]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
sources: ["<posting-url>"]
confidence: high
posting: "[[jobhunt/postings/<slug>]]"
company: "[[jobhunt/companies/<slug>]]"
status: draft                # see STATUS_ENUM.md
applied_at: null             # ISO-Z once status reaches `applied`, else null
campaign_id: "<YYYY-MM-DD>-<slug>"
kanban_task_id: "<form-fill task id>"
submit_task_id: "<submit task id>"      # the --parent-gated submit row
idempotency_key: "application:<company-slug>:<posting-url-sha16>"
resume_artifact: development/job-hunt/artifacts/<app-slug>/resume.pdf
resume_sha256: "<sha256 | none>"
cover_letter_artifact: development/job-hunt/artifacts/<app-slug>/cover.md
cover_letter_sha256: "<sha256 | none>"
preview_capture: development/job-hunt/captures/<campaign>/<app-slug>/preview.png
---

## Status History
<!-- append-only; one line per transition, see STATUS_ENUM.md -->
- <ISO-Z> — (none) → draft — scientia-jobhunt-ingest — created from posting

## Notes
```

## jobhunt-interview  (ingest output)

`wiki/jobhunt/interviews/<slug>.md`.

```yaml
---
title: "<Type> interview — <Role> @ <Company>"
type: jobhunt-interview
tags: [jobhunt, interview]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
sources: ["<capture-or-email-path>"]
confidence: high|medium|low
application: "[[jobhunt/applications/<slug>]]"
interview_type: phone_screen # phone_screen | technical | behavioral | system_design | hiring_manager | team | final
scheduled_at: <ISO-Z|null>
duration_minutes: 60
format: video                # phone | video | onsite
interviewers: []             # list of names or "[[jobhunt/contacts/<slug>]]" links
status: scheduled            # scheduled | completed | cancelled | no_show
rating: null                 # 1..5 once completed, else null
---

## Prep Notes
## Feedback
```

## jobhunt-contact  (ingest output)

`wiki/jobhunt/contacts/<slug>.md`. The scientia analogue of OB1's
`job_contacts` + its CRM bridge: contacts are first-class wiki pages, so
they are reusable across the whole knowledge base without a separate CRM.

```yaml
---
title: "<Name> — <Company>"
type: jobhunt-contact
tags: [jobhunt, contact]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
sources: ["<capture-or-email-path>"]
confidence: high|medium|low
company: "[[jobhunt/companies/<slug>]]"
name: "<full name>"
role_in_process: recruiter   # recruiter | hiring_manager | referral | interviewer | other
email: "<email | none>"
linkedin_url: "<url | none>"
last_contacted: <ISO-Z|null>
---

## Notes
<!-- interaction history; never store passwords/tokens -->
```

---

## Index updates

On first write of any jobhunt page, `scientia-jobhunt-ingest` appends a
`## Job-Hunt` section to `wiki/index.md` (idempotent — inserted only if the
heading is absent) with one table per page type, and appends one line per
page touched to `wiki/log.md`:

```
- <ISO-Z> — scientia-jobhunt-ingest — <created|updated> — jobhunt/applications/<slug>.md — <detail>
```
