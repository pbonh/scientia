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
     - declare any dependency tasks via `(depends on #N)`,
     - mark every shared type it consumes via
       `@uses-shared:<fully-qualified-type-path>` (repeatable) — see
       "Shared-type markers" below,
     - optionally hint at files it expects to modify via
       `@touches:<relpath>[,<relpath>…]` — see "File-touch markers"
       below.

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
   - [ ] **1.** <Imperative task> — @spec: <capability>#<scenario-slug> @touches:src/foo.rs
   - [ ] **2.** <Next task> — @spec: <capability>#<scenario-slug> (depends on #1)
   - [ ] **3.** <Cross-cutting task> — @adr: ADR-NNNN @uses-shared:<crate>/src/<module>.rs::<TypeName>

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

## Shared-type markers (`@uses-shared:<path>`)

A shared type is a struct, enum, trait, or interface that **multiple
in-flight tasks consume**. Without explicit marking, sibling tasks
can each invent their own incompatible version of the same type,
and the conflict only surfaces at integrate time — by which point
the later branch needs to be rewritten to match whatever shape
landed first.

Rule: any task that *reads or writes a value of a shared type* must
carry `@uses-shared:<fully-qualified-path>` on its bullet line.
Multiple markers are permitted (one per consumed type). The path
matches the form used in the ratifying ADR's `shared_types:` list,
e.g. `<crate>/src/<module>.rs::<TypeName>`.

The contract this creates:

- The ADR with `<path>` in its `shared_types:` is the **source of
  truth** for that type's shape.
- `scientia-kanban-emit` refuses to emit any task carrying
  `@uses-shared:<path>` unless an `accepted` ADR with that path
  exists. This forces the type contract to be ratified *before*
  consumer work starts.
- The task whose work *defines* a shared type (the producer)
  carries `@adr: ADR-NNNN` referencing the ratifying ADR. It does
  not need `@uses-shared:` for the type it owns.

If a task legitimately consumes a type whose shape is still in
flux, do not emit it yet — promote the ADR to `accepted` first, or
the kanban-emit preflight will refuse.

## File-touch markers (`@touches:<relpath>[,<relpath>…]`)

Optional informational marker naming the files the implementer is
expected to modify. `scientia-kanban-emit` uses these to group
tasks that touch overlapping files and serialize them into emit
waves — disjoint-file tasks still run in parallel. Without this
marker, multiple branches editing the same file rebase against
each other's accumulating commits, and each integrator after the
first hits a semantic conflict.

Rule: list the files you reasonably expect to modify. Omit if the
file set is unknowable up front (refactors, scaffolding). The
marker is advisory — implementers may touch additional files
without violating the contract; the marker only affects emit
ordering, not what the worker is allowed to do.

Wave size defaults to 2 and is configurable via
`development/config.yaml`'s
`kanban.emit.max_parallel_per_file_group`.

5. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-intent-tasks — tasks-listed — <tenant>/<change-id> — task_count=<n>' >> development/log.md
   ```

6. **Hand off.** Stage transitions to `tasks`. Next recommended
   skill: `scientia-intent-verify`.

## Pre-emit fmt-baseline injection

A pre-existing format-check failure on trunk shows up as a noise
finding on every integrator preflight, masking real regressions and
slowing triage. Prevent the pattern by clearing trunk's fmt
baseline before any behavioral work on this change starts:

1. **Detect.** Before writing `tasks.md`, run the host language's
   format-check on a clean trunk checkout:

   ```bash
   # Rust workspace (Cargo.toml at root)
   cargo fmt --all -- --check

   # Go module (go.mod at root)
   gofmt -l .

   # Python project (pyproject.toml with ruff)
   ruff format --check .
   ```

2. **Inject if drifted.** If the format-check fails on `main` itself
   (independent of any change-in-flight code), inject a synthetic
   item #0 at the head of `tasks.md`:

   ```markdown
   ## Workspace & Shared Infrastructure
   - [ ] **0.** Fmt-fix baseline — non-behavioral @touches:<every-file-fmt-flagged>
   ```

   The item is non-behavioral (no spec backlink) and `@touches:`
   every file the format-check flagged. Every later task that
   carries `(depends on #N)` should naturally serialise behind it
   via the dependency chain; tasks with no explicit deps get a
   synthetic `(depends on #0)` added so they rebase onto the
   cleaned baseline.

3. **The task body** for item #0 instructs the worker to run
   `<format-command>` and commit the result, with **no other
   changes**. The integrator merges the resulting one-commit branch
   to trunk before any behavioral work starts.

If the format-check passes on trunk, skip the injection — item
numbering continues from the user-authored tasks unchanged.

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
