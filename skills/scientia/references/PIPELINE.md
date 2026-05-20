# scientia pipeline reference

The full description of the four-phase pipeline. Read this when the
orchestrator's `SKILL.md` body is insufficient.

## Phase 1 — Wiki construction

Owns: `raw/`, `wiki/`.

Goal: produce a knowledge graph rich enough to anchor downstream design
decisions, with bounded-context structure (strategic DDD), ubiquitous
language (contextual glossaries), captured pitfalls, and pinned ADRs.

Skill order (only `scientia-wiki-bind` is mandatory per change; the
others run on knowledge-arrival cadence):

```
scientia-wiki-init
    ↓
scientia-wiki-ingest  (per source document)
    ↓
scientia-wiki-strategy
    ↓
scientia-wiki-grill   (per planned change)
    ↓
scientia-wiki-lint
    ↓
scientia-wiki-bind    → development/manifests/<tenant>/<change-id>/core.md
```

Output: a `core.md` manifest pinned at the wiki's current git rev. Slices
1–4 + 7 of the 10-slice manifest schema.

## Phase 2 — Intent preparation

Owns: `openspec/changes/<tenant>-<change-id>/`, augmented by manifest
extensions written under `development/manifests/<tenant>/<change-id>/`.

OpenSpec stage sequence, each handled by a dedicated scientia skill:

```
scientia-intent-proposal    (delegates to scientia-grill)
    ↓
scientia-intent-spec        (Gherkin authoring)
    ↓
scientia-intent-design      (computes manifest design extension; C4 diagrams; supersession walk)
    ↓
scientia-intent-adr         (immutable Y-statement ADRs; may delegate to scientia-grill)
    ↓
scientia-intent-tasks       (INVEST / story-splitting; computes manifest tasks extension)
    ↓
scientia-intent-verify      (Completeness / Correctness / Coherence)
```

Output: a complete OpenSpec change ready to emit, plus a manifest with
core + design + tasks extensions + any addenda.

## Phase 3 — Hermes Kanban execution

Owns: rows on the durable task board (`kanban.db`).

```
scientia-kanban-init      (once per host: install Hermes profiles)
    ↓
scientia-kanban-emit      (per change: idempotency-key triples; emit parent + N children + aggregator)
    ↓  (workers run; scientia-kanban-worker loaded into each spawned profile)
scientia-kanban-status    (read-only inspection)
    ↓
scientia-kanban-archive   (per-task cleanup once done)
```

Emit unit: **Gherkin scenarios** from `specs/<capability>/spec.md`.
`tasks.md` is inlined into the parent task's body as
`## Implementation Checklist`, not emitted as separate rows.

Pattern selection from ADR status (the wiki documents this rule):

- `accepted` → P2 pipeline (`implementer → reviewer → integrator`)
- `proposed` → P5 human-in-loop (final approval task with `--require-approval`)
- multiple feature files → P1 fan-out wrapping
- reviewer agreement matters → P3 voting/quorum
- `deprecated`/`superseded` without successor → refuse to emit

Idempotency-key triple per spec parent: `<spec-slug>:<adr-id>:<sha256(spec-body)>`.
Per-scenario child key adds `<scenario-slug>:<sha256(scenario-body)>`.

## Phase 4 — Ingest

Owns: round-trip of completed task results back into `wiki/`, plus
atomic archive across all three stores.

```
scientia-ingest-evidence      (per-task; runs continuously during apply)
    ↓
scientia-ingest-synthesize    (per-change; once all tasks done)  → wiki/syntheses/<change-id>.md
    ↓  (user approves proposed edits)
scientia-ingest-archive       (atomic: wiki update + openspec archive + hermes kanban archive)
```

`scientia-ingest-synthesize` writes **proposed edits only**. Direct
writes to `wiki/concepts/` and `wiki/entities/` are not allowed; the
user reviews the synthesis page and applies it.

## Cross-cutting concerns

**Gates.** Each phase has preflight gates. The orchestrator refuses to
advance when a gate fails. The complete gate inventory:

| Gate | Where | Effect on failure |
|---|---|---|
| `scientia-wiki-lint` CRITICAL | before `scientia-wiki-bind` | block bind |
| `wiki_snapshot` resolvable | before any stage that reads manifest | block stage |
| OpenSpec `verify` ≥ block_on_severity | before `scientia-kanban-emit` | block emit |
| `git:spec-on-trunk` | before `scientia-kanban-emit` | block emit |
| Single in-flight change per tenant | before `scientia-intent-proposal` | block proposal |
| `git:worker-branch-merged` | before `scientia-ingest-archive` (per task) | block archive |
| `scientia_schema_version` ≤ bundle | always | block all |

**Tenancy.** `<tenant>` = bounded-context-slug = OpenSpec spec-slug =
Hermes `--tenant` value. One in-flight change per tenant. Across
tenants: full parallelism.

**Configuration.** Per-repo settings live in `development/config.yaml`.
OpenSpec stage→skill bindings live in `openspec/config.yaml`. The two
files do not cross-reference; each tool owns its own.

**Versioning.** `development/config.yaml` declares
`scientia_schema_version`. Each manifest's `core.md` frontmatter pins the
schema it was bound against. Bundle upgrades migrate `config.yaml` but
leave in-flight manifests on their pinned schema until archived.

**CI.** A single platform-agnostic script
(`skills/scientia/scripts/verify_all.py`) runs every gate. Wire it into
GitHub Actions / GitLab CI / pre-commit with a one-liner.
