# Refactor plan: make scientia's browser work agnostic — capability = "browser", job-hunt = example/test

> **Status:** planned, not yet implemented. Work continues on branch `job_pipeline`.
> This is an internal working doc for a later session — not a shipped/user-facing artifact.
> Decide separately whether to commit it (currently lives on `job_pipeline`).

---

## Why this change

The current branch (`job_pipeline`, commit `b5cd28f`) added browser automation to
scientia **as a job-hunt feature**, and baked job-specific vernacular into the
**core/shared** skills: a `jobhunt:` config key, a `JOBHUNT_ROLE`, a
`scientia-jobhunt-agent` profile, and `detect_jobhunt`/`gate_jobhunt`/a SKILL_MAP
appendix inside the orchestrator and verify gate.

The user wants the **core** to speak only of the generic new **capability — "browser"**,
and to keep the whole job pipeline as the bundle's **example and test**, not a core
feature.

> User's words: *"I don't like the job-specific vernacular in scientia. I would prefer
> that it be more agnostic, namely 'browser', since that is the new capability that we
> added. I like having the job pipeline as an example and test for scientia."*

### Decisions locked (do not revisit)
1. **Job-hunt vertical stays in `skills/scientia-jobhunt-*`**, reframed as the canonical
   example/test that *consumes* the browser capability. (Not moved to an `examples/` tree.)
2. **Core strips back to mainline** — `state_detect.py` / `verify_all.py` /
   `SKILL_MAP.md` / `scientia/SKILL.md` carry **zero** job knowledge. The job-hunt
   example **owns its own** verify gate and state introspection.

Net: mostly mechanical rename + extract-generic + revert-core, plus one new generic
skill. Stays config-gated and purely additive vs. mainline. **No `scientia_schema_version`
bump.**

---

## Background: what exists today (inventory)

The five `skills/scientia-jobhunt-*` skills + the core wiring contain three layers:

| Layer | What | Classification |
|---|---|---|
| **Browser capability** | browser profile + toolset, CDP/provider preflight, `JOBHUNT_ROLE`, ~50% of worker discipline (headless rules, CDP attach, snapshot/vision, capture-then-ingest, the irreversible-action human-gate mechanic, PII redaction) | **generic** → promote to core, rename to "browser" |
| **Sub-loop shape** | brief→emit→worker→ingest→index, idempotency keys, append-only history, rebuild-derived-index, wiki-snapshot pinning | generic, but lives in the example skills (fine) |
| **Job-hunt domain** | 8-state status funnel `draft→applied→screening→interviewing→offer→accepted/rejected/withdrawn`; page types companies/postings/applications/interviews/contacts; task kinds search/author/form-fill/submit; résumé/cover authoring; conversion analytics | **job-specific** → stays in the example |

### Core touchpoints to change (exact, verified against b5cd28f)
- `skills/scientia/scripts/state_detect.py` — `detect_jobhunt()`, `_jobhunt_enabled()`,
  `_jobhunt_kanban()`, the `state["jobhunt"]` assignment, and the `scan_tenants()`
  `if tenant == "jobhunt": continue` guard. (Added +119 lines in b5cd28f — isolated block.)
- `skills/scientia/scripts/verify_all.py` — `JOBHUNT_STATUSES`, `JOBHUNT_LEGAL`,
  `gate_jobhunt()`, `_jobhunt_feature_on()`, `_jobhunt_frontmatter()`,
  `_jobhunt_transitions()`, and `gate_jobhunt(report, repo)` in `main()`. (Added +144 lines.)
- `skills/scientia-kanban-emit/scripts/profile_models.py` — `JOBHUNT_ROLE="jobhunt"`,
  `JOBHUNT_PROFILE_DEFAULT="scientia-jobhunt-agent"`, `ALLOWED_ROLES`, the branch in
  `resolve_profile_name`. `check_profiles_exist` deliberately iterates only the 4
  mainline `ROLES` — keep that. (Added +26 lines.)
- `skills/scientia-kanban-init/SKILL.md` — step "3d" + description (the optional 5th
  profile); `scripts/apply_browser_toolset.py` + `scripts/check_browser_provider.py`
  (read `jobhunt.browser.*`); `assets/profiles/scientia-jobhunt-agent.md`;
  `tests/test_browser_provider.py`.
- `skills/scientia/references/SKILL_MAP.md` — `jobhunt` JSON-key doc + "Appendix:
  Job-Hunt sub-loop" table.
- `skills/scientia/SKILL.md` — the "if state reports a `jobhunt` key…" sentence.
- `skills/scientia-wiki-init/assets/templates/development/config.yaml.tmpl` — commented
  `jobhunt:` block + `hermes.profiles.jobhunt` example.
- `scientia.json` — 5 jobhunt skills + `scientia-jobhunt-agent` profile.
- `README.md` — phase-table row, counts, "## Job-hunt browser automation (optional)".
- `docs/04-jobhunt-browser-automation.md` — the walkthrough.

### Two facts that make the design clean
- `scientia-kanban-init` symlinks **all** `scientia-*` skills into both the host-global
  `~/.hermes/skills/` and each profile-local `~/.hermes/profiles/<name>/skills/`
  (`for skill in "$BUNDLE_ROOT"/skills/scientia-*`). So the example's worker is always
  resolvable by emit's per-task `--skill scientia-jobhunt-worker` — **the generic
  profile never needs to list it.**
- The shared YAML reader is `emit._parse_yaml_subset` (in
  `skills/scientia-kanban-emit/scripts/emit.py`): supports nested 2-space mappings,
  scalars, inline `[lists]`; does **NOT** support inline `{maps}` or trailing `#`
  comments (it keeps them in the value). Config template blocks must keep comments on
  their own lines. `brief.py` carries its own slightly richer parser.

---

## Target architecture (two clean layers)

**Core scientia — generic browser capability (config-gated on a `browser:` block):**
- `scientia-browser-worker` (NEW skill) — generic browser worker discipline.
- `scientia-browser-agent` (renamed profile) — generic browser worker; loads only
  generic skills; vertical workers ride in per-task via emit's `--skill`.
- top-level `browser:` config block (provider / cdp_endpoint / key_env) + a `browser`
  profile role.
- `check_browser_provider.py` / `apply_browser_toolset.py` (already generic — repoint
  config reads from `jobhunt.browser` → `browser`).
- Orchestrator + verify: **no job vernacular**.

**Job-hunt example/test — `skills/scientia-jobhunt-*` (config-gated on a `jobhunt:` block, requires `browser:`):**
- `scientia-jobhunt-{brief,emit,ingest,index}` — domain logic unchanged; config reads
  split (capability ← `browser.*`, vertical ← `jobhunt.*`); profile/role refs point at
  the generic `browser` role.
- `scientia-jobhunt-worker` — slimmed to a thin extension of `scientia-browser-worker`.
- NEW `scientia-jobhunt-ingest/scripts/verify.py` — the former `gate_jobhunt` checks,
  self-contained (the example's "test").
- `docs/04-*` walkthrough updated to the two-block config + the browser capability.

---

## Part A — Core changes (strip job vernacular, expose generic "browser")

### A1. New skill `skills/scientia-browser-worker/SKILL.md`
Distill the **generic** half of the current `scientia-jobhunt-worker` (read it in full
first): headless-execution discipline; browser/CDP discipline (attach to endpoint from
`## Browser Plan`, `cdp-attach-failed` block, prefer `browser_snapshot`, stay
on-domain); capture-then-ingest discipline; the **irreversible-action human gate**
stated generically ("for any task that performs an irreversible external action:
prepare everything, screenshot, then BLOCK; never perform the action — a separate
`--parent`'d task does it after a human approves the `--triage` block"); PII redaction.
No job task kinds, no `# @jobhunt-brief:` header, no résumé/posting fields.
Frontmatter `metadata: {bundle: scientia, phase: browser, role: worker-discipline}`.

### A2. Rename profile asset → `assets/profiles/scientia-browser-agent.md`
`git mv` `scientia-jobhunt-agent.md` → `scientia-browser-agent.md`. Rewrite SOUL to a
generic browser worker: `name: scientia-browser-agent`, `toolsets: [browser]`,
`skills: [scientia-browser-worker, scientia-kanban-worker, scientia-grill]`. Drop the
four job task kinds and résumé/posting language; keep the generic irreversible-action
gate, browser discipline, headless discipline, PII.

### A3. `skills/scientia-kanban-emit/scripts/profile_models.py`
`JOBHUNT_ROLE="jobhunt"` → `BROWSER_ROLE="browser"`;
`JOBHUNT_PROFILE_DEFAULT` → `BROWSER_PROFILE_DEFAULT="scientia-browser-agent"`;
update `ALLOWED_ROLES` + `resolve_profile_name` (`browser` → `scientia-browser-agent`).
Keep `check_profiles_exist` iterating only the 4 mainline `ROLES`. Update
`tests/test_profile_models.py`.

### A4. `skills/scientia-kanban-init/` — generic browser profile step
- `apply_browser_toolset.py` / `check_browser_provider.py`: repoint config reads
  `jobhunt.browser.*` → top-level `browser.*`; resolve `BROWSER_ROLE` →
  `scientia-browser-agent`. Update `tests/test_browser_provider.py`.
- `SKILL.md`: reword step "3d" + description ("optional `scientia-browser-agent` browser
  profile … when `browser:` block"); gate on `browser:` (not `jobhunt:`). Log line
  `jobhunt-profile-ready` → `browser-profile-ready`.

### A5. Strip job vernacular from core orchestrator + verify (revert to mainline)
- `state_detect.py`: delete `detect_jobhunt`, `_jobhunt_enabled`, `_jobhunt_kanban`, the
  `state["jobhunt"]` assignment, and the `scan_tenants()` jobhunt guard (no
  `manifests/jobhunt/` is ever created — guard unneeded). 21 tests still pass.
- `verify_all.py`: delete `JOBHUNT_STATUSES`, `JOBHUNT_LEGAL`, `gate_jobhunt`,
  `_jobhunt_feature_on`, `_jobhunt_frontmatter`, `_jobhunt_transitions`, and the
  `main()` call.
- `SKILL_MAP.md`: delete the `jobhunt` JSON-key block + the appendix table.
- `scientia/SKILL.md`: delete the Job-Hunt-appendix sentence.

### A6. Config template — split capability from vertical
`development/config.yaml.tmpl`: replace the single commented `jobhunt:` block with **two**
commented blocks (expanded form, comments on their own lines):
- `browser:` (capability): `provider`, `cdp_endpoint`, `key_env`.
- `jobhunt:` (example vertical, "requires the `browser:` block above"):
  `user_profile_page`, `index.format`.
- `hermes.profiles.jobhunt` example → `hermes.profiles.browser`.

### A7. `scientia.json` + `README.md`
- `scientia.json`: add `scientia-browser-worker` to `skills[]`; rename
  `scientia-jobhunt-agent` → `scientia-browser-agent` in `profiles[]` (keep the 4 jobhunt
  skills). 27 → **28 skills**, profiles stay 5.
- `README.md`: replace the job-hunt section with a generic **"Browser automation
  (optional capability)"** section (the `browser:` block, `scientia-browser-agent`,
  CDP-attach default, the irreversible-action human gate as a *generic* safety pattern),
  then point to the job-hunt example. Add a "Browser (optional capability)" phase-table
  row (`scientia-browser-worker`); keep a "Job-hunt (example vertical)" row. Fix the
  stale skill counts (README currently says both "22" and "27" — make consistent at 28).

---

## Part B — Job-hunt example/test (stays in `skills/scientia-jobhunt-*`)

### B1. `scientia-jobhunt-worker/SKILL.md` — slim to an extension
Reframe as "the job-hunt vertical's worker, layered on `[[scientia-browser-worker]]`."
Keep only job-specific content: the 4 task kinds (search/author/form-fill/submit), the
`# @jobhunt-brief:` body header, the job handoff fields (posting_url, application_status,
screenshot_path, gate_state, interview_datetime, contacts), résumé/cover artifact paths,
and the concrete gate detail ("never click Submit/Apply/Send"). Replace duplicated
headless/browser/PII prose with a one-line "inherits all discipline from
`scientia-browser-worker`."

### B2. Config reads split (capability vs. vertical)
- `scientia-jobhunt-brief/scripts/brief.py`: read `jobhunt.user_profile_page` (vertical)
  and `browser.provider` (capability) — currently both under `jobhunt:`. Update its
  embedded `load_jobhunt`/`cfg_get` + tests.
- `scientia-jobhunt-emit/scripts/jobhunt_emit.py`: preflight via the updated
  `check_browser_provider` (reads `browser:`); assign tasks to
  `resolve_profile_name("browser")` → `scientia-browser-agent`; keep `--tenant jobhunt`,
  `--skill scientia-jobhunt-worker`, the search/apply chain, idempotency keys. Update tests.
- `scientia-jobhunt-index`: reads `jobhunt.index.format`. Domain logic unchanged.

### B3. Relocate the verify gate into the example — `scientia-jobhunt-ingest/scripts/verify.py`
Move the former `gate_jobhunt` logic here (ingest already owns `LEGAL_TRANSITIONS` +
`references/STATUS_ENUM.md`): frontmatter validity + `status ∈ enum` (CRITICAL); illegal
`## Status History` transitions (CRITICAL); human-gate-not-bypassed — every `applied`
app has a logged `jobhunt-submit-approved — app=<slug>` line (CRITICAL); orphan apps
(WARNING); index staleness via `rebuild_index.py --check` (WARNING). Self-contained
exit-code gate (its own small severity aggregation; honor `--block-on-severity`). Add
`tests/test_verify.py`. This is the example's "test."

### B4. Drop core orchestration of the example; document manual driving
`detect_jobhunt` is gone from core (A5); the example is driven via its walkthrough.
State introspection = `rebuild_index.py --report` + `hermes kanban list --tenant jobhunt`
(already in docs/04). No orphan state script.

### B5. `docs/04-jobhunt-browser-automation.md`
Retitle to frame it as **the worked example of the browser capability**. Step 1: uncomment
**both** the `browser:` (capability) and `jobhunt:` (vertical) blocks; re-run
`scientia-kanban-init` (creates `scientia-browser-agent`, enables the toolset, preflights
the provider). Step 9 "Verify" calls `scientia-jobhunt-ingest/scripts/verify.py` instead
of `verify_all.py`.

---

## Verification

1. **Core tests unchanged.** `python3 -m unittest discover -s tests` in each touched
   skill. Targeted: `scientia-kanban-emit` (profile_models rename), `scientia-kanban-init`
   (browser_provider), `scientia/scripts` (state_detect 21 / verify_all) — all green.
2. **Feature-off regression (the key check).** In a repo with no `browser:`/`jobhunt:`
   blocks: `state_detect.py` emits no `jobhunt`/`browser` key and matches pre-jobhunt
   shape; `verify_all.py` has no job gate; a normal wiki→intent→kanban flow is unchanged.
   Diff core scripts against `3abc53a` semantics.
3. **Capability-on, vertical-off.** Only a `browser:` block: `scientia-kanban-init`
   creates `scientia-browser-agent`, enables the toolset, `check_browser_provider` passes;
   no job artifacts implied.
4. **Example end-to-end (no live browser), as before.** Both blocks: brief → emit (search)
   → ingest → emit `--apply` (author→form-fill `--triage`→submit `--parent`) → log approval
   → ingest (`applied`) → `rebuild_index.py --report` funnel →
   `scientia-jobhunt-ingest/scripts/verify.py` passes (gate-bypass CRITICAL on a missing
   approval). All job tests green.
5. **Grep gate.** `grep -ri 'jobhunt\|job-hunt\|résumé\|posting\|applied' skills/scientia
   skills/scientia-kanban-emit skills/scientia-kanban-init skills/scientia-wiki-init`
   → only generic `browser` references; no job vernacular outside
   `skills/scientia-jobhunt-*` and `docs/04`.

---

## Critical files

- **New:** `skills/scientia-browser-worker/SKILL.md`;
  `skills/scientia-jobhunt-ingest/scripts/verify.py` (+ test).
- **Renamed:** `scientia-kanban-init/assets/profiles/scientia-jobhunt-agent.md` →
  `scientia-browser-agent.md`.
- **Core edits (strip/rename):** `skills/scientia/scripts/state_detect.py`,
  `skills/scientia/scripts/verify_all.py`, `skills/scientia/references/SKILL_MAP.md`,
  `skills/scientia/SKILL.md`, `skills/scientia-kanban-emit/scripts/profile_models.py`,
  `skills/scientia-kanban-init/SKILL.md` + `scripts/{apply_browser_toolset,check_browser_provider}.py`,
  `skills/scientia-wiki-init/assets/templates/development/config.yaml.tmpl`,
  `scientia.json`, `README.md`.
- **Example edits:** `skills/scientia-jobhunt-worker/SKILL.md` (slim),
  `scientia-jobhunt-brief/scripts/brief.py`, `scientia-jobhunt-emit/scripts/jobhunt_emit.py`,
  `docs/04-jobhunt-browser-automation.md` (+ touched tests).

---

## Carry-over caveats to verify against a live Hermes (unchanged from the original work)

These don't block the refactor's structure but should be confirmed when a live instance
is available:
- **Browser-toolset enable syntax** — the exact dotted key / JSON shape
  `apply_browser_toolset.py` writes via `hermes -p <name> config set toolsets '<json>'`.
- **CDP-attach in a headless worker** — whether the browser toolset accepts a
  *config-declared* `cdp_endpoint` for non-interactive `chat -q` workers, or whether
  interactive `/browser connect` is the only attach path (highest-uncertainty point).
- **Kanban row shape** — `--triage` (human-in-loop) + `--parent` (dependency edge)
  semantics for the form-fill→submit gate, as used by the example's emit.

## Branch note

All work continues on `job_pipeline`. The generic `scientia-browser-*` capability becomes
mainline-clean and could be promoted to `main` separately later; the `scientia-jobhunt-*`
example stays on the branch. Confirm before any commit/merge.
