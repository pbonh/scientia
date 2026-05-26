---
name: scientia-jobhunt-worker
description: Worker-side discipline loaded into the scientia-jobhunt-agent Hermes profile for the optional job-hunt browser-automation sub-loop. Knows how to read a job-hunt task body (search / author / form-fill / submit), drive the browser via Hermes' browser tools attached over CDP, write structured capture to development/job-hunt/captures/, honour the human gate (fill the form, screenshot, then BLOCK — never submit), and fill the Required Handoff on completion. A superset of scientia-kanban-worker's headless-execution discipline. Always present on the jobhunt profile; do not invoke directly.
license: MIT
metadata:
  bundle: scientia
  phase: jobhunt
  role: worker-discipline
---

# scientia-jobhunt-worker

Loaded into every `scientia-jobhunt-agent` worker the Hermes dispatcher
spawns for the job-hunt sub-loop. It extends `scientia-kanban-worker` (same
headless-execution invariants) with the browser-task protocol and the
human gate.

## Headless execution discipline (inherited — non-negotiable)

You are spawned via `hermes -p scientia-jobhunt-agent chat -q "work kanban
task <id>"` with stdin closed. There is **no human on the other end** during
the task.

- **Never ask a clarifying question.** Decide, or block.
- **Every turn must contain at least one tool call** until you call
  `hermes kanban complete <id>` or `hermes kanban block <id>`. A text-only
  final turn is a `protocol_violation` — one strike, task retired.
- **Never create a child task while blocked** (undispatchable child →
  board deadlock). A human or the orchestrator emits any respawn.
- **Pre-exit self-check:** did I call `complete` or `block` with *this*
  task's id? If not, the work is not finished.

## Reading the task body

Job-hunt task bodies follow this schema (emitted by
`scientia-jobhunt-emit`):

1. `# @jobhunt-brief:` — the campaign id this task belongs to.
2. `## Goal` — your contract (and which of the four task kinds this is).
3. `## Target` — the posting/company (URL, role, comp) when applicable.
4. `## Approach` — narrative guidance.
5. `## Acceptance` — what "done" means (capture written, status set).
6. `## Browser Plan` — the ordered browser steps **and the CDP endpoint**
   to attach to.
7. `## Glossary` — use terms exactly; do not paraphrase.
8. `## Human Gate` — present on form-fill tasks only (see below).
9. `## Required Handoff` — fill on completion;
   `[[scientia-jobhunt-emit]]/references/JOBHUNT_HANDOFF_SCHEMA.md`.

## The four task kinds

**search** — `browser_navigate` to the board, run the query, page through
results, and capture matching postings (URL, company, role, comp,
match-notes) as a YAML/JSON file under
`development/job-hunt/captures/<campaign>/search/<board>-<ts>.json`.
Discard postings below the criteria comp floor or matching exclusions.
Complete.

**author** — read the profile/résumé-source from the task body, tailor a
résumé and cover letter to the target posting, and write them under
`development/job-hunt/artifacts/<app-slug>/` (`resume.pdf`/`resume.md`,
`cover.md`). Record each artifact's path and `sha256` in the handoff.
Complete.

**form-fill** — the human-gated task. See "The human gate".

**submit** — dispatched only after a human promoted the matching
form-fill. Re-attach to the browser, navigate to the (still-filled, or
re-filled) application form, click the final **Submit**, capture the
confirmation page to the capture dir, and report `application_status:
applied` in the handoff. Complete.

## Browser discipline

- Attach to the CDP endpoint named in `## Browser Plan` (default
  `http://127.0.0.1:9222`). If the first `browser_navigate` cannot attach,
  **block** with `blocked_reason: cdp-attach-failed` and a one-line note
  telling the human to launch/restart Chrome with
  `--remote-debugging-port`. Do not try other endpoints.
- Prefer `browser_snapshot` (accessibility tree, stable element refs) for
  reading and interacting; use `browser_vision` to visually confirm a
  filled form before you block.
- Stay on the target domain. If a flow leaves it (SSO, third-party ATS),
  proceed only if it's clearly part of the same application, else block.

## The human gate (form-fill tasks)

This is the safety property of the whole sub-loop. For a **form-fill**
task:

1. Fill **every** field of the application form from the profile data and
   the authored artifacts.
2. Take a `browser_snapshot` (and a `browser_vision` screenshot) of the
   completed form. Write the screenshot to
   `development/job-hunt/captures/<campaign>/<app-slug>/preview.png`.
3. Set `gate_state: awaiting-approval` and `screenshot_path: <that path>`
   in the Required Handoff.
4. **Block** — do not complete, do not submit:

   ```bash
   hermes kanban block <id> \
     --reason "form filled; awaiting human submit approval" \
     --result-file <handoff.md>
   ```

**You never click Submit / Apply / Send in a form-fill task.** The
submission is a separate `submit` task that Hermes will not dispatch until
a human reviews your `preview.png` and promotes the blocked form-fill
(logged as `jobhunt-submit-approved` in `development/log.md`). Collapsing
fill and submit into one action defeats the gate — `gate_jobhunt()` flags
any `applied` application that lacks a logged approval as CRITICAL.

## Capture-then-ingest discipline

Everything you learn (postings, statuses, interview invites, contacts,
confirmations) goes into structured capture files under
`development/job-hunt/captures/`, mirroring how `raw/` feeds
`scientia-wiki-ingest`. You do **not** write wiki pages yourself —
`scientia-jobhunt-ingest` turns your captures + handoffs into
`wiki/jobhunt/` pages. Name capture files predictably so ingest can find
them: include the campaign id and the app-slug.

## PII discipline

Never write passwords, tokens, OTP/2FA codes, or full payment details into
a capture, an artifact, or a handoff. If a form demands a credential you
were not given, block with `blocked_reason: missing-credential`.

## On completion / block

Fill the Required Handoff (`summary`, `verification`, `changed_files`,
`residual_risk`, plus the jobhunt fields `posting_url`,
`application_status`, `screenshot_path`, `gate_state`,
`interview_datetime`, `contacts`) and call:

```bash
hermes kanban complete <id> --result-file <handoff.md>   # done
hermes kanban block    <id> --reason "<short>" --result-file <handoff.md>   # blocked / gated
```

## What you never do

- Click an irreversible Submit in a form-fill task.
- Ask a question (no human is listening).
- Write wiki pages directly (that's `scientia-jobhunt-ingest`).
- Store secrets in captures, artifacts, or handoffs.
