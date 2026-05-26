# Detected-state → next-action map

Reference table the orchestrator consults to recommend the next phase
skill. Read in conjunction with `scripts/state_detect.py`'s JSON output.

`state_detect.py` emits a JSON object with these keys:

```jsonc
{
  "wiki_present": true,
  "openspec_present": true,
  "development_present": true,
  "hermes_available": true,
  "scientia_schema_version_repo": 1,
  "scientia_schema_version_bundle": 1,
  "tenants": {
    "billing": {
      "active_change": "2026-05-19-add-refunds",
      "stage": "design",                  // see Stage enum below
      "wiki_snapshot_resolves": true,
      "verify_status": "pending",         // pending | clean | warning | critical
      "kanban_status": "none"             // none | running | blocked | done | mixed
    }
  },
  "lint_status": "clean",                 // clean | warning | critical
  "jobhunt": {                            // OPTIONAL — present only when the
                                          // job-hunt sub-loop has artifacts
    "enabled": true,                      // `jobhunt:` block in config.yaml
    "active_campaign": "2026-05-25-rust",
    "phase": "gated",                     // none|briefed|emitted|running|gated|ingested
    "kanban_status": "blocked",           // none|running|blocked|done|mixed
    "gated_count": 2                      // form-fills parked awaiting human submit
  }
}
```

The `jobhunt` key is **absent** unless the optional job-hunt
browser-automation sub-loop has on-disk artifacts (`development/job-hunt/`
or `wiki/jobhunt/`). When absent, ignore the Job-Hunt appendix entirely —
nothing about the mainline pipeline changes.

`stage` enum (in order):

```
absent → bound → proposed → specs → design → adr → tasks → verified → emitted → running → done → archived
```

## Recommendation table

Rows are evaluated top-down; the first match wins. **bold** = strongly
recommended; *italic* = also valid.

| Condition | Recommended next | Alternatives | Gate to check first |
|---|---|---|---|
| `wiki_present == false` | **`scientia-wiki-init`** | — | — |
| `wiki_present && openspec_present == false` | **`scientia-wiki-init`** (will run in upgrade mode) | — | — |
| `lint_status == "critical"` | **`scientia-wiki-lint`** (fix, then re-run) | — | — |
| `scientia_schema_version_repo > scientia_schema_version_bundle` | refuse — surface "upgrade scientia bundle" | — | schema-version |
| User has not chosen a tenant + `tenants` is empty | **`scientia-wiki-strategy`** then ask user to name a change | *`scientia-wiki-ingest`* (if `raw/` has new sources) | — |
| `tenants[t].stage == "absent"` | **`scientia-wiki-grill`** → `scientia-wiki-lint` → `scientia-wiki-bind` | — | wiki must exist |
| `tenants[t].stage == "bound"` | **`scientia-intent-proposal`** | — | single-change-per-tenant |
| `tenants[t].stage == "proposed"` | **`scientia-intent-spec`** | — | — |
| `tenants[t].stage == "specs"` | **`scientia-intent-design`** | — | — |
| `tenants[t].stage == "design"` | **`scientia-intent-adr`** | — | — |
| `tenants[t].stage == "adr"` | **`scientia-intent-tasks`** | — | — |
| `tenants[t].stage == "tasks"` | **`scientia-intent-verify`** | — | — |
| `tenants[t].stage == "verified"` && `tenants[t].verify_status in ["clean","warning"]` | **`scientia-kanban-emit`** | — | git:spec-on-trunk |
| `tenants[t].stage == "verified"` && `verify_status == "critical"` | refuse — direct user to fix verify findings | *override gate verify* | verify |
| `tenants[t].stage == "emitted"` && `kanban_status == "running"` | **`scientia-kanban-status`** (poll) | *wait* | — |
| `tenants[t].stage == "emitted"` && `kanban_status == "blocked"` | **`scientia-kanban-status`** (read comments; user unblocks) | — | — |
| `tenants[t].kanban_status == "done"` && evidence not appended | **`scientia-ingest-evidence`** | — | — |
| Evidence current, all tasks done | **`scientia-ingest-synthesize`** → user reviews | — | — |
| Synthesis approved | **`scientia-ingest-archive`** | — | git:worker-branch-merged |
| `tenants[t].stage == "archived"` | (this tenant is idle) — pick another or new change | — | — |
| User says "verify" / "what's broken" | **`scripts/verify_all.py`** | — | — |
| User says "grill me" | **`scientia-grill`** | — | — |
| User says "show status" | **`scientia-kanban-status`** + read `development/log.md` | — | — |

## Multi-tenant case

When more than one tenant has an active change, present them as a list
with each tenant's current stage and recommended next action. Ask the
user which tenant to advance. **Never** advance two tenants in the same
orchestrator turn — sequential delegation only.

## Gate-override protocol

If the user requests a gate override (e.g., *"emit anyway, verify is
still warning"*):

1. Confirm explicitly: *"You're asking to override the verify gate at
   threshold WARNING. Confirm with: override gate verify."*
2. On confirmation, append to `development/log.md`:
   ```bash
   printf '%s\n' '- 2026-05-19T17:00:00Z — orchestrator — gate-override — billing/2026-05-19-add-refunds — verify@WARNING' >> development/log.md
   ```
3. Proceed with the requested delegation.

CRITICAL findings are not overridable through this protocol; require a
fix or an explicit `--force` flag from a phase skill invocation.

## Appendix: Job-Hunt sub-loop (optional)

**Consult this table only when `state_detect.py` emits a `jobhunt` key.**
The job-hunt browser-automation sub-loop is parallel to — never through —
the OpenSpec intent phase; it has its own dedicated `jobhunt` Hermes tenant
and never appears in `tenants`. Rows evaluated top-down, first match wins.

| Condition (`jobhunt` key present) | Recommended next |
|---|---|
| `jobhunt.enabled == false` (artifacts exist but config has no `jobhunt:` block) | tell the user to uncomment `jobhunt:` and re-run `scientia-kanban-init` |
| `jobhunt.phase == "none"` | **`scientia-jobhunt-brief`** (author `wiki/jobhunt/profile` + `criteria` first) |
| `jobhunt.phase == "briefed"` | **`scientia-jobhunt-emit`** (search tasks) |
| `jobhunt.phase == "emitted"` or `"running"` | **`scientia-kanban-status --tenant jobhunt`** (poll) |
| `jobhunt.phase == "gated"` (`gated_count > 0`) | **human review** — open each blocked form-fill's `preview.png`, confirm, log `jobhunt-submit-approved`, then `hermes kanban unblock <form-fill-id>` to release the parented submit |
| `jobhunt.phase == "ingested"` & jobhunt kanban `done` | **`scientia-jobhunt-ingest`** → **`scientia-jobhunt-index --report`**; then `scientia-jobhunt-emit --apply <slug>` for newly-found postings |

The human gate is a hard stop: never `hermes kanban unblock` a form-fill
without viewing its preview and appending a `jobhunt-submit-approved` line
to `development/log.md`. `verify_all.py`'s `gate_jobhunt` flags any
`applied` application lacking that approval as CRITICAL.
