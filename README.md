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
| **Job-hunt (optional sub-loop)** | `scientia-jobhunt-brief`, `scientia-jobhunt-emit`, `scientia-jobhunt-worker`, `scientia-jobhunt-ingest`, `scientia-jobhunt-index` |

27 skills total. Plus 5 Hermes profiles
(`scientia-implementer`, `scientia-reviewer`, `scientia-integrator`,
`scientia-aggregator`, and the optional `scientia-jobhunt-agent`)
installed into `~/.hermes/profiles/` by `scientia-kanban-init`. The five
`scientia-jobhunt-*` skills and the `scientia-jobhunt-agent` profile are
**optional** — they activate only when `development/config.yaml` declares a
`jobhunt:` block (see [Job-hunt browser automation](#job-hunt-browser-automation-optional)).

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
available immediately. See [docs/INSTALL.md](docs/INSTALL.md) for the
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

### Per-profile Hermes models

`hermes.profiles` in `development/config.yaml` controls the model each
Hermes profile uses, with full fidelity to Hermes' own
[configuring-models](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models)
schema — main `model`, every `auxiliary` task, and `model_aliases` are
all configurable per profile (`implementer`, `reviewer`, `integrator`,
`aggregator`). `scientia-kanban-init` applies declared values via
`hermes -p <name> config set`; `scientia-kanban-emit` refuses on drift.
The block is optional — absent means hands-off, so existing repos see
no change. Schema reference:
[`skills/scientia-kanban-init/references/profile-models.md`](skills/scientia-kanban-init/references/profile-models.md).

```yaml
hermes:
  profiles:
    implementer:
      model:
        provider: anthropic
        default: claude-opus-4.7
    reviewer:
      model:
        default: claude-sonnet-4.6
    aggregator:
      model:
        default: claude-haiku-4.5
    # integrator omitted -> inherits Hermes host defaults
```

**Custom providers and profile isolation.** Hermes profiles are
independent home directories — a profile's `config.yaml` does **not**
inherit `custom_providers:` from the host `~/.hermes/config.yaml`. A
worker spawned against a profile that says `model.provider: custom:fireworks`
but has no `custom_providers:` block of its own crashes with
`Unknown provider 'custom:fireworks'`. `scientia-kanban-init` handles
this automatically: when a role's declared block references any
`custom:<name>` provider, the matching host entry is propagated into
the profile's own `config.yaml` before the model leaves are applied.
You manage the host `custom_providers:` definitions and per-profile
`.env` files (for API keys); scientia takes care of the propagation.
Built-in providers (`anthropic`, `openrouter`, `xai`, etc.) need no
propagation and can be declared per-profile as-is.

## Job-hunt browser automation (optional)

An optional sub-loop hangs off the wiki phase and drives a browser via
[Hermes' browser feature](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser)
to run a job search — find postings, author a résumé and cover letter from
your wiki profile, pre-fill application forms, and submit **only after you
approve**. It mirrors scientia's main closed loop but is shorter and skips
OpenSpec entirely:

```
wiki/jobhunt/ ─► brief ─► emit (Hermes browser tasks) ─► capture ─► ingest ─► wiki/jobhunt/
   (your profile + criteria)   (search · author · fill)   (human-gated submit)   (pipeline pages)
                                                                                       │
                                              development/job-hunt/pipeline.sqlite ◄────┘  (funnel analytics)
```

The job-hunt entities (companies, postings, applications, interviews,
contacts) are **wiki pages** under `wiki/jobhunt/`; application status
(`draft → applied → screening → interviewing → offer → accepted/rejected/
withdrawn`) lives in page frontmatter. A derived
`development/job-hunt/pipeline.sqlite` powers OB1-style analytics
(conversion rate, stage funnel, upcoming interviews).

**The human gate.** A form-fill worker fills the form completely,
screenshots it, and **blocks** — it never clicks Submit. The submit is a
separate kanban row parented to the form-fill, so the dispatcher cannot run
it until you review the preview and promote it (logged as
`jobhunt-submit-approved`). `verify_all.py`'s `gate_jobhunt` flags any
`applied` application lacking that approval as CRITICAL.

**Enable it.** Uncomment the `jobhunt:` block in
`development/config.yaml`, then re-run `scientia-kanban-init` to create the
`scientia-jobhunt-agent` profile and turn on its browser toolset. The
default runtime is **CDP-attach to your already-logged-in Chrome** (launch
it with `--remote-debugging-port=9222`) — best for authenticated portals
and requires no cloud keys; Camofox/Browserbase are config-selectable.

> **PII.** `wiki/jobhunt/` holds personal data (your contact details,
> recruiter names). It is committed normally so the brief's wiki-snapshot
> pin works — keep the repo on a **private remote**. Generated artifacts
> (résumés, cover letters, form screenshots) live under
> `development/job-hunt/` and are `.gitignore`'d; pages record only their
> path + a content sha.

Full walkthrough: [docs/04-jobhunt-browser-automation.md](docs/04-jobhunt-browser-automation.md).

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
