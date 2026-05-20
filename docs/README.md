# scientia workflow examples

Realistic, end-to-end walkthroughs of the scientia pipeline. Each
document is written for a specific audience and follows a single
narrative — what the user types, what the orchestrator detects, which
phase skills run, what artifacts land on disk, and where the gates
catch mistakes.

| Doc | Phases used | Audience |
|---|---|---|
| [01 — Wiki-only: building a research knowledge graph](01-wiki-only-research.md) | wiki | Research lead / staff engineer mapping a new domain |
| [02 — End-to-end single change: `billing/2026-05-19-add-refunds`](02-end-to-end-single-change.md) | wiki → intent → kanban → ingest | Tech lead shipping a real change |
| [03 — Multi-tenant parallel: `billing` + `identity`](03-multi-tenant-parallel.md) | wiki + intent + kanban + ingest, two tenants | Eng manager coordinating two squads |

The examples are deliberately *narrative*. They show:

- The exact text the user types to the agent client.
- The orchestrator's detected-state output and recommended next skill.
- The on-disk artifacts produced by each phase skill (file paths and
  excerpts).
- Realistic gate failures (e.g., `wiki-lint CRITICAL`, idempotency
  drift, single-in-flight-change-per-tenant) and how to recover.
- The exact CLI commands invoked against `hermes` and `openspec`.

If you are looking for the reference for a single skill, read its
`SKILL.md` under `skills/`. The reference is canonical; these examples
are illustrations.

## How to read these

Each example follows the same structure:

1. **Setting** — repo state, team, what the user is trying to
   accomplish.
2. **Walkthrough** — the conversation, broken into phase sections.
   Code blocks show either user input (` > "..." `), CLI commands
   (`$ ...`), or file contents (` ```yaml `, ` ```markdown `).
3. **Artifacts produced** — a listing of every file the walkthrough
   touched.
4. **Recovery / variations** — what changes if a gate fails or the
   user makes a different choice.

## Reproducing locally

Every example assumes scientia is installed per
[INSTALL.md](INSTALL.md) and that the user has run

```bash
git clone https://github.com/pbonh/scientia.git ~/.agents/skills/scientia
```

The walkthroughs use **absolute** date stamps (e.g.,
`2026-05-19-add-refunds`) and **fictional** tenants. They do not
require any external API — `scientia-grill` is the only interactive
loop and runs entirely inside the agent client.
