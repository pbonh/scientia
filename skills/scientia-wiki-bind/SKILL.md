---
name: scientia-wiki-bind
description: Produce the core domain manifest for a new OpenSpec change. Reads the wiki, extracts the in-scope slice for a tenant and change description, and writes development/manifests/<tenant>/<date>-<slug>/core.md pinned at the wiki's current git rev. The manifest is the single artifact that carries wiki knowledge into every downstream OpenSpec stage. Use exactly once per change, after scientia-wiki-lint reports no CRITICAL findings.
license: MIT
metadata:
  bundle: scientia
  phase: wiki
  order: "6"
---

# scientia-wiki-bind

Bind the wiki state to a specific change by producing a `core.md`
manifest under `development/manifests/<tenant>/<change-id>/`. This is the
seam between the wiki phase and the intent phase.

## Inputs

The user (or the orchestrator on the user's behalf) supplies:

1. `tenant` — the bounded-context slug (must match a
   `wiki/contexts/<tenant>.md` page).
2. `change-id` — `<YYYY-MM-DD>-<short-slug>` describing the change.
3. `description` — 1–3 sentences naming what the change is about.
4. *(Optional)* a list of capability slugs the change will introduce.

## Preflight gates

Refuse to bind if any of:

- `tenant` has no corresponding `wiki/contexts/<tenant>.md` page.
- `scientia-wiki-lint` last reported CRITICAL findings.
- A non-archived manifest already exists at
  `development/manifests/<tenant>/<any-change-id>/core.md` (one
  in-flight change per tenant — Q14).
- The wiki has uncommitted changes (the snapshot pin would be
  ambiguous). The user can override by committing first or by passing
  `--allow-dirty`, which records the dirty state in the manifest's
  frontmatter.

## Procedure

1. **Compute the wiki snapshot pin.** Run `git rev-parse HEAD` against
   the wiki's git rev (the repo containing `wiki/`). This becomes the
   `wiki_snapshot:` frontmatter value.

2. **Assemble the seven core slices** by reading the wiki:

   - **Slice 1 — Domain framing.** Read `wiki/contexts/<tenant>.md`.
     Pull its boundary, subdomain classification, and links to
     context-maps.
   - **Slice 2 — In-scope concepts.** Walk the context's
     `## In-Scope Concepts` list. For each, read the concept page and
     extract its one-line *definition* (first sentence of
     `## Definition`).
   - **Slice 3 — In-scope entities.** Same, against
     `## In-Scope Entities`.
   - **Slice 4 — Ubiquitous language.** Verbatim copy of the
     context's `## Ubiquitous Language` glossary, plus any
     false-cognate flags from `## False Cognates with Adjacent
     Contexts`.
   - **Slice 7 — Related prior work.** Find summaries
     (`wiki/summaries/*.md`) whose `## Relevant Concepts` overlap with
     slice 2; include one-line headline per relevant summary.

   (Slices 5, 6, 8 — in-force ADRs, ASRs, pitfalls — are computed at
   `scientia-intent-design` time, not here. Slice 9 — tradeoffs — is
   computed at `scientia-intent-tasks` time. Slice 10 — addenda — is
   created lazily as the live-query escape hatch is used.)

3. **Write `development/manifests/<tenant>/<change-id>/core.md`**:

   ```yaml
   ---
   title: "Core manifest — <tenant>/<change-id>"
   type: manifest-core
   tenant: <tenant>
   change_id: <change-id>
   description: "<user-supplied 1-3 sentence description>"
   capabilities: [<capability-slug>, ...]   # optional, may be empty
   scientia_schema: 1
   wiki_snapshot: <git-rev>
   bundle_version: <bundle-version>
   created: <YYYY-MM-DD>
   ---

   ## 1 — Domain Framing
   ## 2 — In-Scope Concepts
   ## 3 — In-Scope Entities
   ## 4 — Ubiquitous Language
   ## 7 — Related Prior Work
   ```

4. **Create the empty change directory** at
   `openspec/changes/<tenant>-<change-id>/` so the next phase skill
   has a target.

5. **Update `development/log.md`:**

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-wiki-bind — manifest-bound — <tenant>/<change-id> — wiki_snapshot=<rev-short>' >> development/log.md
   ```

6. **Hand off.** Report to the orchestrator: stage transitioned to
   `bound`; recommended next skill is `scientia-intent-proposal`.

## Re-binding

If the user wants to refresh the manifest core mid-change (e.g., a new
concept page was added that the change should now incorporate), the
correct operation is to write a new `core.md` *next to* the old one,
named `core-<n>.md`, with an updated `wiki_snapshot:`. The original
`core.md` is never edited — it is the bind-time pin and must remain
immutable for audit reasons. Downstream stages read the most recent
`core-<n>.md`.

## What this skill never does

- Edits the wiki.
- Computes design or tasks extensions (those are stage-entry
  computations done by the relevant intent-phase skills).
- Writes to `openspec/changes/<id>/proposal.md` or any other OpenSpec
  artifact body — it only creates the change directory.
- Resolves wiki-link rot. Run `scientia-wiki-lint` first.
