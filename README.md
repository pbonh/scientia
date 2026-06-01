# scientia — KG-Seeded Intent-Driven Agent Skills

A client-agnostic set of [Agent Skills](https://agentskills.io/specification)
plus a small supporting Python package (`scientia`) that runs a research-and-
development pipeline from raw sources to implementation tasks:

```
sources → wiki (knowledge graph) → proposal → grill → specs → design → adrs → tasks
```

Its novel contribution is the **seam** between two patterns. The wiki — treated
as a typed-node knowledge graph — *seeds* the proposal and grill stages, and a
per-claim **confidence** score acts as a deterministic gate: where the KG is
high-confidence the pipeline can automate a decision; where it is low-confidence
the pipeline surfaces the gap as a challenge instead of guessing.

The skills follow the agentskills.io spec, so they run on any conforming runtime.
There is no graph database, no vector store, no external service, and no SaaS
dependency.

## Two layers

| Layer | Where | Carries |
|-------|-------|---------|
| **Skills** (LLM judgment) | `~/.agents/skills/scientia*/SKILL.md` | reading sources/proposals, rating confidence, writing prose |
| **`scientia`** (determinism) | the pip-installed `scientia` package | parsing, the confidence math, templating, validation, the advance gate |

The dividing line is the spine of the design: anything whose output must be
byte-stable and testable lives in the package; anything needing an LLM's reading
lives in a skill. Skills hold no derived state — they call the package and
read/write files.

## The skills

One orchestrator plus eight stage skills:

| Skill | Stage |
|-------|-------|
| `scientia` | orchestration (walks the pipeline, gates every stage) |
| `scientia-ingest-source` | ingest a raw source into the wiki |
| `scientia-audit-wiki` | periodic, non-destructive wiki health check |
| `scientia-seed-proposal` | seed a proposal from the KG |
| `scientia-grill-proposal` | interrogate the proposal against the KG |
| `scientia-write-specs` | gherkin-style specs |
| `scientia-write-design` | design.md with C4 diagrams |
| `scientia-record-adr` | one ADR per durable decision |
| `scientia-generate-tasks` | the final tasks.md checklist |

### Optional execution layer (`scientia-hermes-*`)

If a `hermes:` block is present in `config.yaml`, the pipeline does not have to
stop at `tasks.md`: four further skills turn the finished change into a live,
dependency-ordered [Hermes](https://github.com/NousResearch/hermes-agent) Kanban
board of `impl → review → integrate` pipelines and report progress back. They are
fully optional — absent the block, nothing here runs.

| Skill | Phase |
|-------|-------|
| `scientia-hermes-init` | provision/validate the board, project-specific profiles, and gateway |
| `scientia-hermes-emit` | emit cards + dependency links (REST-first, idempotent) |
| `scientia-hermes-status` | read the board back and surface real escalations |
| `scientia-conflict-resolver` | the Hermes *profile* that resolves integrate conflicts without a human |

Conflict robustness is the headline property: work is decomposed along C4
component boundaries so collisions are *prevented* (file-collision waves +
shared-contract ratification, in `scientia.hermes.conflict`), and the residue is
*resolved* automatically by the `conflict-resolver` profile.

**Project-specific profiles.** Each Hermes profile is automatically prefixed with
the board slug (e.g. `circuit-solver-beta-implementer` instead of the generic
`implementer`) and carries a SOUL.md system prompt that embeds the project's
C4 architecture, accepted ADRs, shared contracts, and spec scenarios. No
configuration is needed — the prefix is derived from the project name. Different
boards on the same Hermes install can thus have different execution profiles —
each grounded in its own project's architecture and constraints. Add
`hermes.profile_prefix: ""` to the project's `references/config.yaml` to
disable prefixing for backward compatibility with pre-0.3 setups.

## Layout

```
scientia/                     # this repo — a collection of installable skills
├── scientia/                 # orchestrator skill (SKILL.md)
├── scientia-ingest-source/   # … the eight stage skills, one dir each
├── scientia-audit-wiki/
├── scientia-seed-proposal/
├── scientia-grill-proposal/
├── scientia-write-specs/
├── scientia-write-design/
├── scientia-record-adr/
├── scientia-generate-tasks/
├── scientia-hermes-init/     # optional execution layer (only with a hermes: block)
├── scientia-hermes-emit/
├── scientia-hermes-status/
├── scientia-conflict-resolver/  # the Hermes conflict-resolver profile
├── src/scientia/             # the importable Python package
│   ├── wiki/__init__.py      # Page, Link, load/list/parse_links/neighbors/write_page
│   ├── hermes/               # the execution layer (parse/idempotency/conflict/plan/
│   │                         #   render/ledger/validators pure; preflight/apply impure)
│   ├── confidence.py         # multiplier, recompute(_all), rollup_page/edge
│   ├── templates.py          # render / render_to_file (str.format_map, no Jinja)
│   ├── validators.py         # validate_* → error lists
│   ├── advance.py            # the package-owned stage-advance gate
│   ├── paths.py              # single source of file-layout truth
│   └── references/           # config.yaml + *.md.tmpl (shipped as package data)
├── tests/{modules,skills,fixtures}/ + run_all.py
└── examples/sources/karpathy-2026.md   # the worked example
```

Each top-level `scientia*` directory is a self-contained Agent Skill; the
non-skill directories (`src/`, `tests/`, `examples/`) have no `SKILL.md` and are
ignored by skill runtimes.

## Install

Skills are discovered from `~/.agents/skills`, and the `scientia` package must be
importable by whatever runs the skills.

```bash
# 1. Clone the skills directly into the skills root so they are discovered.
git clone <this-repo> ~/.agents/skills

# 2. Install the supporting Python package EDITABLE (pip or uv).
#    Use -e so a `git pull` updates the importable package in lockstep with the
#    SKILL.md files it ships beside — a non-editable install freezes a copy and
#    drifts stale (see "Keeping the package in sync" below).
pip install -e ~/.agents/skills         # or:  uv pip install -e ~/.agents/skills
#   networkx is an optional traversal extra:  pip install -e '~/.agents/skills[graph]'

# 3. Point the pipeline at your project (where sources/, wiki/, proposals/ live).
export SCIENTIA_ROOT=/path/to/your/project
```

If you keep other skills in `~/.agents/skills`, clone this repo elsewhere and
symlink the `scientia*` directories into the skills root instead:

```bash
git clone <this-repo> ~/src/scientia
ln -s ~/src/scientia/scientia* ~/.agents/skills/
pip install -e ~/src/scientia
```

### Claude Code

Claude Code discovers skills under `~/.claude/skills/`. Each skill directory must
sit at the top level of that folder; a single symlink to the repo root is not
enough because Claude expects each skill's `SKILL.md` to be one directory level
below the skills root.

```bash
# 1. Clone this repo anywhere you like.
git clone <this-repo> ~/.agents/skills/scientia

# 2. Symlink each individual skill directory into ~/.claude/skills/
for dir in ~/.agents/skills/scientia/scientia*/; do
  ln -s "$(realpath "$dir")" ~/.claude/skills/
done

# 3. Install the supporting Python package EDITABLE and set the project root.
pip install -e ~/.agents/skills/scientia
export SCIENTIA_ROOT=/path/to/your/project
```

Afterwards, `~/.claude/skills/` should contain the individual skill directories
(e.g., `~/.claude/skills/scientia/`, `~/.claude/skills/scientia-ingest-source/`,
etc.), not a top-level `scientia` directory that wraps them.

### Keeping the package in sync (avoid stale wheels)

The skills and the Python package ship in **one repo** and must move together:
each `SKILL.md` calls functions in the installed `scientia` package, so when the
two diverge the skills invoke an API the install does not have. A **non-editable**
install (`pip install <path>`) copies a snapshot into site-packages; a later
`git pull` updates the live `SKILL.md` files but **not** the frozen copy, and the
pipeline fails mid-run with `AttributeError`/`ImportError` on names like
`resolve_profile_prefix`, `verify_touches`, `touches_overlap_warnings`, or with a
`hermes kanban task create` (the old CLI verb) — symptoms of code newer in the
repo than in the install.

Prevent it:

```bash
# Always install editable so the import path IS the repo (no frozen copy):
pip install -e ~/.agents/skills/scientia

# If you (or a teammate) used a non-editable install, force a clean reinstall
# after every pull so the package matches the checked-out SKILL.md files:
pip install --force-reinstall --no-deps ~/.agents/skills/scientia

# Verify the install resolves to the repo, not a stale site-packages copy:
python -c "import scientia, pathlib; print(scientia.__file__)"
#   editable -> .../.agents/skills/scientia/src/scientia/__init__.py  (good)
#   stale    -> .../site-packages/scientia/__init__.py                (reinstall)

# A leftover build/ tree can shadow src/ on sys.path — remove it if present:
rm -rf ~/.agents/skills/scientia/build
```

An editable install removes this failure mode at the source; the
`python -c` check above is the quickest way to confirm a runtime is not on a
stale copy before starting a pipeline run.

## Test

```bash
python -m pytest tests/modules -q
python tests/run_all.py     # SKILL.md validation + skill evals + golden-file suite
```

`networkx` is optional — the pure-Python neighborhood traversal is canonical and
the suite passes with it absent. When present, its traversal is verified to
return identical results.

## Running the pipeline on any Agent-Skills runtime

1. Ensure the `scientia*` skills are discoverable under `~/.agents/skills` and the
   `scientia` package is installed (see Install).
2. Set `SCIENTIA_ROOT` to your project directory (or run from it). The pipeline
   reads `sources/`, builds `wiki/`, and writes `proposals/<change-id>/` there.
   Paths are centralized in `scientia.paths`.
3. Ask the runtime to *run the pipeline* — the `scientia` skill activates and
   walks the stages, activating each child skill and gating every stage through
   the package-owned validation marker.

### Configuration (`references/config.yaml`)

The committed defaults ship as package data (ADR-0003, ADR-0010): the
source-count curve `[1.00, 0.04, 1.10]` (+10% cap), `contradiction_floor 0.40`,
`rollup min`, and thresholds `proposal_seed_min 0.70` / `prior_art_floor 0.60` /
`grill_dismiss_min 0.85` / `adr_recommend_accept_min 0.90` /
`low_confidence_floor 0.45`; `audit.staleness_days 14`; and the per-stage
`autonomous` / `pause_and_ask` mode table. A project may override any key by
placing its own `references/config.yaml` at `SCIENTIA_ROOT`.

## Confidence model

A claim's `base` (an LLM rating set once at ingest, never edited) is layered with
two pure-Python signals:

```
multiplier(n) = min(1.10, 1.00 + 0.04 * (n - 1))      # n = distinct sources
multiplied    = base * multiplier(n)
effective     = min(contradiction_floor, multiplied) if contradicted else multiplied
```

`effective` is persisted but canonically derived: `recompute` is its only writer,
is idempotent, and stamps an `inputs_hash`. Rollups verify that hash against live
inputs and **raise** rather than return a stale value. The asymmetry is
intentional — many sources lift a claim by at most 10%, but one contradiction
caps it hard.

## Walkthrough (smoke test)

`examples/sources/karpathy-2026.md` ships as the worked example. Copy it into
`$SCIENTIA_ROOT/sources/` and run `scientia-ingest-source`:

```
wiki/
├── source-karpathy-2026.md
├── entity-llm-wiki.md
├── claim-rag-rediscovers-knowledge-on-every-query.md   (base 0.85, n=1, effective 0.85)
├── claim-llm-maintains-wiki-stateful.md                (base 0.82, n=1, effective 0.82)
└── question-when-does-the-wiki-drift.md
```

After `scientia-seed-proposal` for topic `entity-llm-wiki`, both claims (≥ 0.70)
appear in `## Context (from KG)` with their `effective` shown inline, the open
question appears under `## Candidate Problems`, and `## Constraints (from KG)` is
present but empty with `_KG provided no high-confidence content for this
subsection._`.

A second source citing the same two claims raises both `effective` values via the
source-count multiplier (`n=2 → ×1.04`) — the smallest end-to-end demonstration
of compounding knowledge through confidence.

## Provenance

This bundle is the implementation of `kg-seeded-intent-driven-skills-design.md`,
carried through the intent workflow to specs (8 capabilities), a design with C4
diagrams, 11 accepted ADRs, and a 30-task plan under
`openspec/changes/spec-driven-development-2026-05-26-kg-seeded-intent-skills/`.
