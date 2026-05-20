---
name: scientia-ingest-evidence
description: Per-task evidence ingest. Reads the Required Handoff block from a completed kanban task, extracts the structured fields (changed_files, verification, branch_head, residual_risk, wiki_spec, wiki_adr_ids, dependencies), and appends a structured bullet to the originating spec page's ## Implementation Evidence section in both wiki/specs/ and openspec/changes/.../specs/. Idempotent — keyed by the task's idempotency-key, so re-running on already-ingested tasks is a no-op.
license: MIT
metadata:
  bundle: scientia
  phase: ingest
  order: "1"
---

# scientia-ingest-evidence

Run per completed task. Cheap, continuous, additive. The integrator
profile triggers this skill as its last act before archiving; the
orchestrator's polling loop may also trigger it.

## Procedure

1. **Identify ingestable tasks.** Tasks where:
   - `status == "done"`,
   - the latest comment contains a complete `## Required Handoff`
     block,
   - the spec's `## Implementation Evidence` section does not already
     contain a bullet keyed by this task's idempotency-key.

2. **For each task, extract the handoff fields** via
   `scripts/handoff_extract.py`. The script reads the task body +
   comments + completion result and produces a JSON object with
   verbatim values for: `summary`, `verification`, `changed_files`,
   `dependencies`, `blocked_reason`, `retry_notes`, `residual_risk`,
   `branch_head`, `wiki_spec`, `wiki_adr_ids`.

3. **Identify the originating spec.** From the task's
   `wiki_spec` field (e.g., `refunds#refund-cash`), resolve to:
   - `wiki/specs/<spec-slug>.md` (living-documentation mirror).
   - `openspec/changes/<tenant>-<change-id>/specs/<spec-slug>/spec.md`
     (the authoritative spec).

4. **Append an evidence bullet** to each. Schema:

   ```markdown
   ## Implementation Evidence

   <!-- scientia-ingest-evidence-keyed -->
   - **Scenario `<scenario-slug>`** — task `<task-id>` (key
     `<idempotency-key-short>`) merged at `<branch_head>` by
     `<integrator-profile>`. Verification: `<verification>`. Residual
     risk: `<residual_risk>`. Changed files: `<n>`.
   ```

   If the section does not yet exist, create it. If a bullet keyed
   by this task's idempotency-key already exists, **no-op** — this
   is the idempotence guarantee.

5. **Append to `wiki/log.md`** one line per spec page touched:

   ```markdown
   - YYYY-MM-DDTHH:MM:SSZ — scientia-ingest-evidence — appended — wiki/specs/<spec>.md — task=<id>
   ```

6. **Append to `development/log.md`** one line per task ingested:

   ```markdown
   - YYYY-MM-DDTHH:MM:SSZ — scientia-ingest-evidence — evidence-appended — <tenant>/<change-id> — task=<id>
   ```

## Gates

- Refuse to ingest a task whose handoff block is malformed or missing
  required fields. Surface as a finding and direct the user (or the
  reviewer who approved) to ask the implementer for a corrected
  handoff.
- Refuse to ingest if the originating spec page no longer exists
  (e.g., the spec was renamed; this is the renamed-slug case from the
  idempotency-key concept page — handle via re-emit, not via ingest).

## Helper

- `scripts/handoff_extract.py` — parse a task's completion comment
  into the structured handoff JSON.

## What this skill never does

- Touches `wiki/concepts/` or `wiki/entities/`. Concept synthesis is
  `scientia-ingest-synthesize`, which writes only proposed edits.
- Archives tasks or changes. That is `scientia-ingest-archive`.
- Marks tasks as `done` or modifies their status. Only workers and
  the integrator do that.
