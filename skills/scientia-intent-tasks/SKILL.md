---
name: scientia-intent-tasks
description: Produce the tasks.md checkbox list for a scientia OpenSpec change. Computes the tasks-stage manifest extension (INVEST/story-splitting/SMART tradeoffs) and decomposes each spec capability into ordered, dependency-aware implementation tasks. Use after ADRs exist and before scientia-intent-verify. tasks.md is BOTH the planning artifact OpenSpec apply walks AND the source from which scientia-kanban-emit materialises one impl/review/integrate pipeline per item — `(depends on #N)` becomes a kanban --parent edge, and `@spec:` markers wire per-scenario impls to depend on the matching integrate stages.
license: MIT
metadata:
  bundle: scientia
  phase: intent
  openspec_stage: tasks
---

# scientia-intent-tasks

Produce `openspec/changes/<tenant>-<change-id>/tasks.md`: the checkbox
implementation plan that OpenSpec's `apply` phase consumes AND the
source that `scientia-kanban-emit` reads to materialise per-item
kanban pipelines. Every numbered `- [ ] **N.**` bullet becomes a
three-stage `impl → review → integrate` Hermes row, with `(depends on
#N)` translated into `--parent` edges and `@spec: <cap>#<scn>` markers
used to wire per-scenario impl rows back onto their prerequisite
items. The full body of `tasks.md` is also inlined into the kanban
parent task body as `## Implementation Checklist` for reference.

## Inputs

- `proposal.md`, `specs/*/spec.md`, `design.md`, `adr/NNNN-*.md` for
  the change.
- `development/manifests/<tenant>/<change-id>/{core,design}.md`.

## Procedure

1. **Compute the tasks-stage manifest extension** at
   `development/manifests/<tenant>/<change-id>/tasks.md`:

   - **Slice 9 — Tradeoffs & suggestions.** From the wiki: INVEST
     properties, story-splitting heuristics (workflow, business-rule,
     data-variation, interface, etc.), SMART criteria where they
     apply. List the rules that constrain the decomposition.

   Frontmatter:

   ```yaml
   ---
   title: "Tasks manifest — <tenant>/<change-id>"
   type: manifest-tasks
   tenant: <tenant>
   change_id: <change-id>
   scientia_schema: 1
   wiki_snapshot: <git-rev-at-tasks-entry>
   created: <YYYY-MM-DD>
   ---
   ```

2. **Decompose** each capability's spec scenarios into implementation
   steps:

   - One task per *atomic* implementation step. A task is atomic if
     it completes in a single coding session and has one observable
     output.
   - Group tasks by capability for readability, but order them by
     dependency, not by source-file boundary.
   - Each task must:
     - be specific enough that a worker can complete it without
       asking back,
     - reference the spec scenario or ADR it implements (`@spec:
       <capability>#<scenario-slug>` or `@adr: ADR-NNNN`),
     - declare any dependency tasks via `(depends on #N)`.

3. **Write `tasks.md`**:

   ```markdown
   ---
   title: "Tasks: <change title>"
   tenant: <tenant>
   change_id: <change-id>
   manifest_tasks: development/manifests/<tenant>/<change-id>/tasks.md
   created: <YYYY-MM-DD>
   ---

   # Implementation Plan

   ## Capability: <capability-slug>
   - [ ] **1.** <Imperative task> — @spec: <capability>#<scenario-slug>
   - [ ] **2.** <Next task> — @spec: <capability>#<scenario-slug> (depends on #1)
   - [ ] **3.** <Cross-cutting task> — @adr: ADR-NNNN

   ## Capability: <next-capability-slug>
   - [ ] **4.** ...

   ## Cross-Cutting
   - [ ] **N.** Documentation update — non-behavioral
   - [ ] **N+1.** CI workflow tweak — non-behavioral
   ```

   The apply phase ticks each `- [ ]` as `- [x]` once the
   corresponding code change is made. Non-behavioral cross-cutting
   tasks (docs, CI, scaffolding) also produce kanban rows; the
   `(depends on #N)` chain typically keeps them late in the
   pipeline rather than at the front.

4. **Apply the INVEST properties as a self-check.** Every task should
   be Independent, Negotiable, Valuable, Estimable, Small, Testable.
   Tasks that violate INVEST get split before this skill exits.

5. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-intent-tasks — tasks-listed — <tenant>/<change-id> — task_count=<n>' >> development/log.md
   ```

6. **Hand off.** Stage transitions to `tasks`. Next recommended
   skill: `scientia-intent-verify`.

## Gates

- Refuse if `proposal.md`, any `specs/<capability>/spec.md`, or
  `design.md` is missing.
- Refuse if any task references a spec or ADR that does not exist.

## What this skill never does

- Emits kanban tasks. That is `scientia-kanban-emit`. The emission
  units are *both* the Gherkin scenarios (per-spec impl/review/
  integrate pipelines) *and* each `- [ ] **N.**` bullet in
  `tasks.md` (per-item impl/review/integrate pipelines with
  `(depends on #N)` chains wired as `--parent` edges).
- Edits spec or design or ADR content. If the decomposition surfaces
  a contradiction, pause and let the user push back upstream — do not
  silently rewrite earlier artifacts.
- Ticks tasks as complete. That is the apply phase's job.
