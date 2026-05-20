---
name: scientia-intent-verify
description: Score a scientia OpenSpec change across Completeness, Correctness, and Coherence with severities CRITICAL / WARNING / SUGGESTION. Reads proposal.md, specs/*, design.md, adr/*, tasks.md, and the manifest layers, and writes a verify report at openspec/changes/<tenant>-<change-id>/verify-<timestamp>.md. Use immediately before scientia-kanban-emit. Never emits if findings meet or exceed development/config.yaml's verify.block_on_severity threshold.
license: MIT
metadata:
  bundle: scientia
  phase: intent
  openspec_stage: verify
---

# scientia-intent-verify

Cross-cutting verifier for a complete OpenSpec change. Produces a
machine-readable + human-readable report scored across three
dimensions and three severities. The report is the *gate* between the
intent phase and the kanban phase.

## Dimensions

| Dimension | What it checks |
|---|---|
| **Completeness** | Every section in every artifact is filled. Every task references a spec or ADR. Every capability has a spec. Every spec has at least one scenario. Every breaking change in proposal is reflected in specs and tasks. |
| **Correctness** | Every wiki-link resolves. Every `@spec:` reference resolves to a real scenario slug. Every ADR's Y-statement has all five clauses. Every Gherkin scenario passes the single-When rule. Every glossary term used in specs is defined in the manifest core's slice 4. |
| **Coherence** | Design honors every in-force ADR (or explicitly supersedes via an ADR). Tasks order respects spec dependencies. Spec scenarios cover every "What Changes" bullet in proposal. No contradiction between design and ADR. |

## Severity assignment

- **CRITICAL** — broken structurally: missing artifact, unresolved
  reference, violated ADR immutability, contradiction. Blocks emit.
- **WARNING** — meets the structure but violates a documented
  discipline: thin section, multiple `When`s in a scenario, glossary
  term used but not defined, design that mentions a topic with no
  ADR coverage. Blocks emit only if `block_on_severity == warning`
  or stricter in config.
- **SUGGESTION** — advisory. Never blocks. Surfaces improvement
  opportunities (e.g., a capability with one scenario that probably
  needs more, a spec without a doc-string example).

## Procedure

1. **Read every artifact** for the change:
   - `proposal.md`
   - `specs/<capability>/spec.md` (one or more)
   - `design.md`
   - `adr/NNNN-*.md` (zero or more)
   - `tasks.md`
   - `development/manifests/<tenant>/<change-id>/{core,design,tasks}.md`

2. **Run the dimension checks.** The skill's authoritative check list
   is in `references/CHECKS.md`. Each check produces zero or more
   findings with `(dimension, severity, location, message)`.

3. **Aggregate** by `(dimension, severity)`. Compute the worst
   severity across all findings.

4. **Write the report** at
   `openspec/changes/<tenant>-<change-id>/verify-<YYYY-MM-DDTHHMMSS>.md`:

   ```markdown
   ---
   title: "Verify report — <tenant>/<change-id>"
   type: verify-report
   tenant: <tenant>
   change_id: <change-id>
   created: <YYYY-MM-DDTHH:MM:SSZ>
   worst_severity: <critical|warning|suggestion|clean>
   counts:
     critical: <n>
     warning: <n>
     suggestion: <n>
   ---

   # Verify Report

   ## Completeness (<n> findings)
   - **CRITICAL** — <location> — <message>
   - **WARNING** — <location> — <message>
   - ...

   ## Correctness (<n> findings)
   ...

   ## Coherence (<n> findings)
   ...

   ## Summary
   <One paragraph: pass, conditional pass, or block, against the
   configured block_on_severity threshold.>
   ```

5. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-intent-verify — verified — <tenant>/<change-id> — critical=<n> warning=<n> suggestion=<n>' >> development/log.md
   ```

6. **Hand off.** If worst severity ≥ `block_on_severity`: refuse to
   advance and tell the orchestrator the gate failed. Otherwise:
   stage transitions to `verified`. Next recommended skill:
   `scientia-kanban-emit`.

## Relationship to `verify_all.py`

`scripts/verify_all.py` in the orchestrator skill runs *all* gates
across *all* in-flight changes (wiki-lint + this skill + emit
preflights + idempotency-drift). This skill runs only the
intent-phase scoring for *one* change. The orchestrator-level
`verify_all.py` is the CI entry point; this skill is the per-change
gate before emit.

## What this skill never does

- Edits any artifact. Read-only.
- Decides whether to override the gate. Override is a user-driven
  action through the orchestrator.
