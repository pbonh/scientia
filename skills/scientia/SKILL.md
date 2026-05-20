---
name: scientia
description: Software R&D pipeline orchestrator that walks a knowledge graph / wiki, an intent-driven OpenSpec change, Hermes Kanban execution, and ingest synthesis as a single closed loop. Use when starting, continuing, or inspecting a development effort whose source-of-truth is a wiki and whose execution is a durable kanban board. Do not use for one-off code edits, dependency bumps, or non-spec work.
license: MIT
metadata:
  bundle: scientia
  bundle_version: "0.1.0"
  scientia_schema_version: "1"
  role: orchestrator
---

# scientia (pipeline orchestrator)

You are the orchestrator of the **scientia** software R&D pipeline. You
*navigate* the pipeline; you do not do phase work. Every concrete action
— writing a proposal, drafting a spec, emitting tasks, ingesting
results — is delegated to a phase skill.

## The four-phase pipeline

```
wiki ──► intent ──► kanban ──► ingest ──► wiki
```

1. **Wiki construction** — produces and curates `raw/` + `wiki/`; ends
   with `scientia-wiki-bind` writing a per-change manifest.
2. **Intent preparation** — OpenSpec `proposal → specs → design → adr →
   tasks` augmented by the manifest.
3. **Hermes Kanban execution** — emit Gherkin scenarios as durable
   tasks; workers run; humans interpose where needed.
4. **Ingest** — handoffs flow back into the wiki; OpenSpec and Hermes
   archive; the wiki is now richer for the next change.

Concurrency rule: **one in-flight change per bounded-context tenant**;
multiple tenants run in parallel. Change-ids are `<tenant>/<date>-<slug>`.

See [references/PIPELINE.md](references/PIPELINE.md) for the full pipeline
diagram and stage descriptions.

## How to activate this skill

1. **Detect pipeline state.** Run `scripts/state_detect.py` (or read the
   four canonical locations yourself in this order):
   - `wiki/index.md` → does the wiki exist?
   - `development/manifests/*/` → which tenants have manifests, and at
     what stage?
   - `openspec/changes/*/` → which changes are in flight?
   - `hermes kanban list` → which tasks are running per tenant?

2. **Present valid next actions.** Cross-reference detected state against
   [references/SKILL_MAP.md](references/SKILL_MAP.md). Show the user the
   set of valid next phase skills, with a recommended default.

3. **Delegate.** Activate the chosen phase skill. **You never write
   `proposal.md`, `spec.md`, `design.md`, `adr.md`, `tasks.md`, kanban
   tasks, or wiki concept pages yourself** — those are owned by phase
   skills. You only:
   - read state and propose actions,
   - append to `development/log.md` after every state transition,
   - refuse to advance when gates fail (and surface why).

4. **Persist state on disk, not in memory.** The pipeline's true state
   lives in `wiki/`, `development/`, `openspec/`, and `kanban.db`. Do
   not invent a separate state file. Re-running this skill from scratch
   in a new session must produce the same next-action set.

## Detected-state → next-action matrix (summary)

The full table is in [references/SKILL_MAP.md](references/SKILL_MAP.md).
Common cases:

| Detected state | Default next action |
|---|---|
| No `wiki/` directory | `scientia-wiki-init` |
| Wiki exists, no manifests | `scientia-wiki-ingest` or `scientia-wiki-strategy` |
| Wiki exists, user names a new change | `scientia-wiki-grill` → `scientia-wiki-lint` → `scientia-wiki-bind` |
| Manifest core exists, no `openspec/changes/<tenant>-<id>` | `scientia-intent-proposal` |
| Proposal exists, no specs | `scientia-intent-spec` |
| Specs exist, no design | `scientia-intent-design` |
| Design exists, ADRs incomplete | `scientia-intent-adr` |
| ADRs accepted, no tasks.md | `scientia-intent-tasks` |
| tasks.md exists, not verified | `scientia-intent-verify` |
| Verified, no kanban tasks | `scientia-kanban-emit` |
| Kanban tasks running | `scientia-kanban-status` or wait |
| All kanban tasks done | `scientia-ingest-evidence` → `scientia-ingest-synthesize` → `scientia-ingest-archive` |
| User says "verify" | `scripts/verify_all.py` (CI-style report) |
| User says "grill me" | `scientia-grill` |

## Gates

Refuse to advance and surface the conflict if:

- The wiki's git rev no longer resolves the `wiki_snapshot` pin in the
  manifest's `core.md`.
- `scientia-wiki-lint` reports CRITICAL findings.
- OpenSpec `verify` reports findings above the threshold in
  `development/config.yaml`'s `verify.block_on_severity`.
- `git:spec-on-trunk` fails before `scientia-kanban-emit`.
- Multiple in-flight changes exist on the same tenant.
- `development/config.yaml` declares a `scientia_schema_version` newer
  than this bundle supports.

If the user wants to bypass a gate, require explicit *"override gate
\<name>"* confirmation and append a `gate-override` entry to
`development/log.md`.

## Logging

After every state transition (entering or exiting a phase, recommending a
delegation, applying a gate override), append one line to
`development/log.md` of the form:

```
- YYYY-MM-DDTHH:MM:SSZ — orchestrator — <event> — <tenant>/<change-id> — <details>
```

**Always append via shell redirection, never via Edit-style
old-string/new-string anchors.** `log.md` grows between turns
(other skills append too); anchoring on its current tail fails
intermittently. The canonical idiom — used by every scientia skill
that logs — is:

```bash
printf '%s\n' '- '$(date -u +%Y-%m-%dT%H:%M:%SZ)' — orchestrator — <event> — <tenant>/<change-id> — <details>' >> development/log.md
```

Substitute the skill name for `orchestrator` (e.g.
`scientia-intent-spec`) when calling from a phase skill, and the
same shape for `wiki/log.md` writes. This log is the orchestrator's
audit trail and the canonical record of *why* the pipeline is where
it is.

## Files in this skill

- `references/PIPELINE.md` — full pipeline reference (read on demand).
- `references/SKILL_MAP.md` — detected-state → next-action table.
- `scripts/state_detect.py` — emits a JSON state report.
- `scripts/verify_all.py` — runs the full verify gate suite (also the
  CI entry point).
- `scripts/migrations/` — schema-version migration scripts (empty in
  v0.1; populated when schema versions bump).
