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

1. **Detect pipeline state.** Run `scripts/state_detect.py` *from the
   project root*. **The project root is the directory the user's session
   was launched in — your current working directory, i.e. the output of
   `pwd`.** It is *never* derivable from the skill bundle's path, from a
   parent home directory, or from any other context. Distrobox homes and
   monorepo roots may contain stray `wiki/` directories of their own;
   those are not your scientia project.

   The preferred invocation keeps cwd in the project and references the
   script by absolute path — the script then auto-uses cwd as the repo:

   ```bash
   python3 /path/to/skills/scientia/scripts/state_detect.py --pretty
   ```

   Only pass `--repo` if you genuinely need to invoke from elsewhere, and
   in that case pass the session's cwd verbatim — do not synthesize a
   path from the skill's location:

   ```bash
   python3 /path/to/skills/scientia/scripts/state_detect.py --repo "$(pwd)" --pretty
   ```

   The script will:
   - exit 2 if invoked from inside the skill bundle (the bundle is not
     a project),
   - warn on stderr if `--repo` points to a directory with no `.git/`,
     `development/`, or `openspec/` — a strong sign you've named a
     parent/home directory by mistake.

   The script checks (or read these four canonical locations yourself
   in this order):
   - `wiki/index.md` → does the wiki exist?
   - `development/manifests/*/` → which tenants have manifests, and at
     what stage?
   - `openspec/changes/*/` → which changes are in flight?
   - `hermes kanban list` → which tasks are running per tenant?

   **If any tenant reports `blocked > 0`**, run the blocked-task sweep
   *before* offering next actions:

   ```bash
   python3 /path/to/skills/scientia/scripts/sweep_blocked.py --repo "$(pwd)"
   ```

   The sweep surfaces (a) blocked tasks whose work has actually
   resolved and are safe to `unblock`, (b) refused tasks with the
   specific gate failure, and (c) parent-child deadlock cycles —
   blocked parent ↔ todo child where the child is parented to the
   blocked parent, which can never dispatch. The sweep is read-only
   by default; pass `--apply` to execute the printed commands after
   confirmation.

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

## Boundaries (never do)

Two recurring orchestrator-overreach patterns produce false-progress
loops that stall the board: editing worker branches directly, and
unblocking integrators before the underlying conflict has actually
been resolved. Both ship untested code under the integrator's
approval signature and lead to unblock → block → unblock cycles.
The following are hard prohibitions, not guidelines:

- **Never edit a worker branch.** Rebase conflicts, clippy
  regressions, dangling `let` bindings, stale comments on
  `impl/*` branches — none of these are orchestrator hand-fixes.
  Even a one-line "trivial" patch bypasses the
  implementer → reviewer → integrator chain and ships untested
  code under the integrator's approval signature. Conflict
  resolution is the implementer's job; surface the conflict so an
  implementer respawn can do it.

- **Never call `hermes kanban unblock <id>` directly.** Always
  gate the call through `scripts/unblock_gate.py <id>`:

  ```bash
  python3 .../skills/scientia/scripts/unblock_gate.py <task-id>
  ```

  The script returns exit 0 plus the safe unblock command iff
  every gate passes (task is blocked, branch HEAD advanced past
  the blocking handoff, every `--parent` is `done`, no fresh
  REQUEST CHANGES from the reviewer). On a refuse, fix the
  underlying problem before re-running. Override
  (`--allow-stale-head`) is reserved for the case where you have
  *just* merged the unblocking work and the local mirror has not
  yet caught up.

- **Never create the implementer respawn task as a child of the
  blocked integrator.** Per `scientia-integrator.md` "On rebase
  conflicts", the respawn must be parented to the *reviewer*
  (already `done`), never to the blocked integrator — otherwise
  the parent-child deadlock pattern strands the board.

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
