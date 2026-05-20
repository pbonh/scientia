---
name: scientia-wiki-grill
description: Interrogate the wiki for knowledge gaps that would weaken a forthcoming OpenSpec change. Walks the in-scope bounded context, identifies thin or missing concept and entity pages, and grills the user (via scientia-grill) to fill them in before scientia-wiki-bind runs. Use immediately before binding a new change's manifest. Do not use for general brainstorming — this skill narrows knowledge to a specific change scope.
license: MIT
metadata:
  bundle: scientia
  phase: wiki
  order: "4"
---

# scientia-wiki-grill

The quality gate between "the wiki exists" and "the manifest is bound."
Runs against a *named change scope* — a tenant (bounded-context) and a
short user-supplied description of the planned change.

## Procedure

1. **Take the change scope as input.** The user supplies:
   - the tenant (= bounded-context slug),
   - a 1–3 sentence description of what the planned change is about.

2. **Enumerate the in-scope subset of the wiki:**
   - the context page at `wiki/contexts/<tenant>.md`,
   - every concept and entity page listed under that context's
     `## In-Scope Concepts` / `## In-Scope Entities` sections,
   - any related context-map pages,
   - any ADRs in `wiki/decisions/` whose `tags:` or `## Architecturally
     Significant Requirement` section touches the scope,
   - relevant summaries (those whose `## Relevant Concepts` overlap).

3. **Find gaps** by walking the in-scope set:
   - Concept pages with `confidence: low` or `medium` whose subject
     matter the change will touch.
   - Concept pages whose `## Risks & Pitfalls` section is empty or
     thin.
   - Entity pages with no `## Common Strategies`.
   - The context's `## Ubiquitous Language` glossary missing terms the
     change's description uses.
   - ADRs that the change might contradict (supersession candidates).
   - Adjacent contexts whose false-cognates may bite this change.

4. **Grill the user.** Invoke `scientia-grill`. For each identified
   gap, present one question per turn with a recommended fix
   (extend a concept, add a glossary term, add a pitfall bullet,
   etc.). Apply the four grill rules (one question per turn;
   recommend an answer; codebase over question; park don't loop).

5. **Apply confirmed fixes.** As the user confirms each fix:
   - Edit the relevant concept/entity/context/ADR page directly
     (this skill *is* allowed to edit existing wiki pages — that's
     the point).
   - Bump `updated:`. Append a log entry per edit.

6. **Park what cannot be resolved.** Open questions parked during the
   grill go to a new section in the relevant context page (or a new
   open-question page in the wiki). They do not block the bind.

7. **Emit a readiness report.** When the grill ends, summarize:
   - Pages touched.
   - Gaps filled.
   - Open questions parked.
   - Whether the wiki is ready for `scientia-wiki-bind` against this
     tenant + change scope.

8. **Append to `wiki/log.md`** one line per page edited, and one final
   `grill-complete` entry to `development/log.md`.

## Quality bar

The wiki is ready for `scientia-wiki-bind` when:

- The in-scope context page has no `confidence: low` concept pages.
- Every term the change description uses appears in the context's
  glossary (or is intentionally introduced *by* the change and so
  belongs in the new spec).
- Every in-scope concept page has at least one entry in
  `## Risks & Pitfalls`.
- Open questions are written down somewhere referenced from the
  context page; they are not blocking.

## What this skill never does

- Writes to `development/manifests/` (that's `scientia-wiki-bind`).
- Writes to `openspec/changes/` (that's the intent-phase skills).
- Adds new bounded contexts (that's `scientia-wiki-strategy`).
- Deletes content. Only extends, refines, and annotates.
