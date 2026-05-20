# scientia

A software research-and-development pipeline implemented as a set of
[Agent Skills](https://agentskills.io). The pipeline starts with a knowledge
graph / wiki and ends with delivered software, closing the loop by ingesting
task output back into the wiki so development is an ongoing process.

```
raw/ ──► wiki/ ──► development/manifests/ ──► openspec/changes/ ──► kanban tasks ──► ingest ──► wiki/
   (knowledge construction)   (intent + spec + design + ADR + tasks)   (execution)        (synthesis)
```

scientia is **client-agnostic** — anything that implements the Agent Skills
specification can discover and activate its skills. Its only runtime
dependencies are [OpenSpec](https://github.com/intent-driven-dev/openspec) and
[Hermes Kanban](https://github.com/nous-research/hermes).

## Phases and skills

| Phase | Skills |
|---|---|
| **Orchestrator** | `scientia` |
| **Utility** | `scientia-grill` |
| **Wiki construction** | `scientia-wiki-init`, `scientia-wiki-ingest`, `scientia-wiki-strategy`, `scientia-wiki-grill`, `scientia-wiki-lint`, `scientia-wiki-bind` |
| **Intent (per OpenSpec stage)** | `scientia-intent-proposal`, `scientia-intent-spec`, `scientia-intent-design`, `scientia-intent-adr`, `scientia-intent-tasks`, `scientia-intent-verify` |
| **Hermes Kanban execution** | `scientia-kanban-init`, `scientia-kanban-emit`, `scientia-kanban-worker`, `scientia-kanban-status`, `scientia-kanban-archive` |
| **Ingest (closing the loop)** | `scientia-ingest-evidence`, `scientia-ingest-synthesize`, `scientia-ingest-archive` |

22 skills total. Plus 4 Hermes profiles
(`scientia-implementer`, `scientia-reviewer`, `scientia-integrator`,
`scientia-aggregator`) installed into `~/.hermes/profiles/` by
`scientia-kanban-init`.

## Pipeline at a glance

1. **Wiki phase.** `scientia-wiki-init` scaffolds `raw/`, `wiki/`,
   `development/`, `openspec/`. `scientia-wiki-ingest` turns sources into
   summaries + concept/entity pages. `scientia-wiki-strategy` runs the
   strategic-DDD pass that identifies bounded contexts and subdomains.
   `scientia-wiki-grill` interrogates the wiki for gaps relevant to a
   forthcoming change. `scientia-wiki-lint` validates frontmatter and
   wiki-link integrity. `scientia-wiki-bind` writes
   `development/manifests/<tenant>/<change-id>/core.md` — the wiki-snapshot
   pin that carries through every downstream stage.

2. **Intent phase.** Five per-stage skills walk the OpenSpec
   `proposal → specs → design → adr → tasks` lifecycle, with each stage
   reading the manifest core + computing its own per-stage extension
   (`design.md`, `tasks.md`). `scientia-intent-verify` checks
   Completeness / Correctness / Coherence across the change.

3. **Hermes phase.** `scientia-kanban-emit` reads the change, computes
   idempotency-key triples `(spec-slug, adr-id, sha256(spec-body))`, picks a
   collaboration pattern from ADR status, and emits one parent task + N
   per-scenario children + one aggregator per spec. `scientia-kanban-worker`
   is loaded into every spawned worker profile.

4. **Ingest phase.** `scientia-ingest-evidence` appends per-task handoffs to
   the spec's `## Implementation Evidence` as tasks complete.
   `scientia-ingest-synthesize` (after every task is `done`) writes proposed
   wiki edits to `wiki/syntheses/<change-id>.md` for user approval.
   `scientia-ingest-archive` atomically archives the wiki update, the
   OpenSpec change, and the Hermes tasks.

## Install

```bash
git clone https://github.com/pbonh/scientia.git ~/.agents/skills/scientia
```

That is the whole install step. Every Agent Skills client tested
(OpenCode, Claude Code, Cursor) discovers `SKILL.md` files under
`~/.agents/skills/` recursively, so the 22 bundled skills become
available immediately. See [INSTALL.md](INSTALL.md) for the
fine print (client-specific paths, Hermes profile install, upgrade,
uninstall).

Then, in any target repo, activate the orchestrator:

> *"Use the scientia skill."*

The orchestrator detects pipeline state from on-disk artifacts and
recommends the next action — usually `scientia-wiki-init` on a fresh
repo.

## Concurrency

One in-flight OpenSpec change per **bounded-context tenant**; multiple
tenants run in parallel. Change-ids are `<tenant>/<date>-<slug>/` across
`development/manifests/`, `development/tasks/`, and `openspec/changes/`.

## Configuration

- `development/config.yaml` — scientia per-repo settings (paths, profile
  name overrides, emit pattern overrides, verify strictness, ingest
  behavior, tenant policies). See template installed by `scientia-wiki-init`.
- `openspec/config.yaml` — OpenSpec's own config (stage→skill bindings);
  scientia writes the bindings at init time but does not own this file.

## Versioning

Each repo records `scientia_schema_version` in `development/config.yaml`;
each `manifests/.../core.md` frontmatter pins the schema it was bound
against. In-flight changes keep their schema across bundle upgrades;
new changes adopt the new schema. Upgrade scientia by
`cd ~/.agents/skills/scientia && git pull`; `verify_all.py` will flag
any migration required.

## CI

A single platform-agnostic gate is shipped at
`skills/scientia/scripts/verify_all.py`. Wire it into any CI:

```yaml
- run: ~/.agents/skills/scientia/skills/scientia/scripts/verify_all.py
```

It walks all in-flight manifests, runs wiki-lint + OpenSpec verify +
idempotency-key drift check + git preflights, aggregates by severity, and
exits non-zero on the threshold set in `development/config.yaml`.

## License

MIT. See [LICENSE](LICENSE).
