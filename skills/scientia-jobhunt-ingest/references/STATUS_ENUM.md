# Job-hunt application status enum

The `status:` frontmatter field on every `jobhunt-application` page
(`wiki/jobhunt/applications/<slug>.md`) is drawn from this fixed enum,
mirroring OB1's job-hunt pipeline. The enum is the spine of the funnel
analytics in `development/job-hunt/pipeline.sqlite`.

## States

| Status | Meaning | Terminal? |
|---|---|---|
| `draft` | Application is being prepared (résumé/cover authored, form pre-filled) but not yet submitted. | no |
| `applied` | Application was submitted (the human-gated submit completed). | no |
| `screening` | Recruiter/HR screen in progress (phone screen, take-home, ATS triage). | no |
| `interviewing` | One or more substantive interviews scheduled or underway. | no |
| `offer` | An offer has been extended. | no |
| `accepted` | Offer accepted — the search succeeded for this role. | **yes** |
| `rejected` | Declined by the employer, or the candidate withdrew after a rejection. | **yes** |
| `withdrawn` | Candidate withdrew before a decision. | **yes** |

`draft` is the only status a brand-new application page may carry before
the submit task runs. `accepted`, `rejected`, and `withdrawn` are
terminal — no transition out of them is legal.

## Legal transition graph

A status change is legal only if the `(from → to)` edge appears below.
`scientia-jobhunt-ingest` validates every transition before appending to
a page's `## Status History`; `gate_jobhunt()` re-checks the recorded
history. Illegal transitions are CRITICAL findings.

```
draft        → applied | withdrawn
applied      → screening | interviewing | offer | rejected | withdrawn
screening    → interviewing | offer | rejected | withdrawn
interviewing → offer | rejected | withdrawn
offer        → accepted | rejected | withdrawn
accepted     → (terminal)
rejected     → (terminal)
withdrawn    → (terminal)
```

Notes:

- Forward skips are allowed (e.g. `applied → interviewing` when there is
  no separate recruiter screen, or `applied → offer` for a fast process).
- Backward edges are **not** legal (e.g. `interviewing → screening`). If
  the real-world process genuinely regresses, withdraw and open a new
  application page rather than rewinding status — the audit trail stays
  monotonic.
- `withdrawn` is reachable from every non-terminal state (the candidate
  can always pull out).

## Machine-readable form

`rebuild_index.py` and `gate_jobhunt()` both import this table. The
canonical encoding (kept in sync with the prose above) is:

```python
LEGAL_TRANSITIONS = {
    "draft":        {"applied", "withdrawn"},
    "applied":      {"screening", "interviewing", "offer", "rejected", "withdrawn"},
    "screening":    {"interviewing", "offer", "rejected", "withdrawn"},
    "interviewing": {"offer", "rejected", "withdrawn"},
    "offer":        {"accepted", "rejected", "withdrawn"},
    "accepted":     set(),
    "rejected":     set(),
    "withdrawn":    set(),
}
TERMINAL = {"accepted", "rejected", "withdrawn"}
```

## Status History block

Each application page carries an append-only `## Status History` section.
Every transition is one line:

```
- <ISO-Z> — <from> → <to> — <source> — <note>
```

where `<source>` is the skill or actor that drove the change
(`scientia-jobhunt-ingest`, `human`, …) and `<note>` is a short free-text
reason (e.g. a kanban task id, an interview id, "recruiter email"). The
first line of a freshly-created page records `(none) → draft`.
