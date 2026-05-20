---
name: scientia-intent-adr
description: Write immutable Y-statement architectural decision records for the significant decisions distilled by design.md. Each ADR is sequence-numbered, includes Architecturally Significant Requirement, and follows supersession discipline (never edit accepted ADRs; write a new one that Supersedes the prior). Use after design.md exists and before tasks.md. May delegate to scientia-grill to stress-test a decision before recording it.
license: MIT
metadata:
  bundle: scientia
  phase: intent
  openspec_stage: adr
---

# scientia-intent-adr

Capture the significant decisions named in `design.md`'s
`## Decisions Distilled to ADRs` section as immutable ADRs at
`openspec/changes/<tenant>-<change-id>/adr/NNNN-<kebab-title>.md`.

## Inputs

- `design.md` for the change.
- `development/manifests/<tenant>/<change-id>/design.md` (the design
  manifest extension; especially slice 5 in-force ADRs to know the
  next ADR number).

## Procedure

1. **Determine the next ADR number.** Walk
   `openspec/changes/*/adr/NNNN-*.md` plus `openspec/archive/.../adr/`
   to find the highest existing NNNN. The next ADR's number is
   `max+1`, four-digit zero-padded.

2. **For each decision** in design's `## Decisions Distilled to ADRs`:

   a. **Optionally stress-test via `scientia-grill`.** Only required
      for decisions the user flags as uncertain or contentious; for
      crisp decisions, write the ADR directly.

   b. **Write the ADR** at
      `openspec/changes/<tenant>-<change-id>/adr/NNNN-<kebab-title>.md`:

      ```markdown
      ---
      title: "ADR-NNNN: <Imperative Decision Title>"
      adr_id: ADR-NNNN
      status: proposed              # proposed | accepted | deprecated | superseded
      tenant: <tenant>
      change_id: <change-id>
      supersedes: []                # list of ADR-IDs this ADR replaces
      superseded_by: null           # filled by a future ADR if/when superseded
      asr:                          # the architecturally significant requirement
        - "<one-line ASR>"
      tags: [<bounded-context-tag>, <other-tags>]
      created: <YYYY-MM-DD>
      ---

      # ADR-NNNN: <Title>

      ## Y-Statement

      **In the context of** <bounded context / situation>,
      **facing** <forces and concerns>,
      **we decided for** <option>
      **and against** <alternatives considered>,
      **to achieve** <benefits>,
      **accepting** <drawbacks / consequences>.

      ## Architecturally Significant Requirement

      <Spell out the ASR. Why is this a decision worth capturing?>

      ## Options Considered

      ### Option A — <name>
      <Description, pros, cons.>

      ### Option B — <name>
      <Description, pros, cons.>

      ### Option C — <name> (chosen)
      <Description, pros, cons. Mark chosen.>

      ## Consequences

      - <Positive consequence>
      - <Negative consequence / cost>
      - <Follow-up actions, if any>

      ## Supersession

      <If this ADR supersedes an earlier one, name it and explain the
      delta. If this ADR is later superseded, the *successor* ADR
      records that fact and this one's `superseded_by:` frontmatter
      is updated to point to the successor — but the *body* of this
      ADR is never edited.>
      ```

   c. **Mirror to wiki living documentation.** Create
      `wiki/decisions/<adr-id>.md` with frontmatter `type: decision`
      and a `## Source` section pointing back to the OpenSpec ADR
      path. Add a row to `wiki/index.md`'s **Decisions** table.

3. **Status discipline.**
   - New ADRs start as `proposed`. The user (or a reviewer) flips
     them to `accepted` once consensus is reached. The flip is the
     only allowed status edit on an ADR; everything else is
     supersession.
   - When superseding: the *new* ADR's `supersedes:` lists the prior
     IDs; the *prior* ADR's frontmatter `superseded_by:` is updated
     to point to the new ID (this is the *one* exception to ADR
     immutability — a single frontmatter pointer, not a body edit).

4. **Append to `development/log.md`** one line per ADR written:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-intent-adr — adr-drafted — <tenant>/<change-id> — adr=ADR-NNNN status=proposed' >> development/log.md
   ```

5. **Hand off.** Stage transitions to `adr`. Next recommended skill:
   `scientia-intent-tasks`.

## Gates

- Refuse to draft if `design.md` does not exist.
- Refuse to edit an `accepted` ADR's body. The only legal mutations
  on an accepted ADR are: status → `deprecated`, `superseded_by:`
  pointer to a successor. Body and Y-statement are frozen.

## What this skill never does

- Writes tasks. That's `scientia-intent-tasks`.
- Decides which decisions warrant an ADR. The design skill enumerates
  them in `## Decisions Distilled to ADRs`; this skill records them.
- Approves ADRs as `accepted`. That requires explicit user (or
  reviewer) action; this skill writes `proposed` and waits.
