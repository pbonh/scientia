# KG-Seeded Intent-Driven Skills

A portable [Agent Skills](https://agentskills.io) bundle that runs a research-and-
development pipeline from raw sources to implementation tasks:

```
sources → wiki (knowledge graph) → proposal → grill → specs → design → adrs → tasks
```

Its novel contribution is the **seam** between two patterns. The wiki — treated
as a typed-node knowledge graph — *seeds* the proposal and grill stages, and a
per-claim **confidence** score acts as a deterministic gate: where the KG is
high-confidence the pipeline can automate a decision; where it is low-confidence
the pipeline surfaces the gap as a challenge instead of guessing.

The bundle is runtime-agnostic. **opencode + OpenSpec** are the tested-against
implementation, **not** a requirement — there is no graph database, no vector
store, no external service, and no SaaS dependency.

## Two layers

| Layer | Where | Carries |
|-------|-------|---------|
| **Skills** (LLM judgment) | `.agents/skills/*/SKILL.md` | reading sources/proposals, rating confidence, writing prose |
| **`kg_pipeline`** (determinism) | `kg_pipeline/*.py` | parsing, the confidence math, templating, validation, the advance gate |

The dividing line is the spine of the design: anything whose output must be
byte-stable and testable lives in the package; anything needing an LLM's reading
lives in a skill. Skills hold no derived state — they call the package and
read/write files.

## Layout

```
kg_pipeline/                  # this bundle (the working directory)
├── kg_pipeline/              # the importable Python package
│   ├── wiki/__init__.py      # Page, Link, load/list/parse_links/neighbors/write_page
│   ├── confidence.py         # multiplier, recompute(_all), rollup_page/edge
│   ├── templates.py          # render / render_to_file (str.format_map, no Jinja)
│   ├── validators.py         # validate_* → error lists
│   ├── advance.py            # the package-owned stage-advance gate
│   └── paths.py              # single source of file-layout truth
├── .agents/skills/<9 skills>/SKILL.md
├── references/               # config.yaml + 7 *.md.tmpl
├── tests/{modules,skills,fixtures}/ + run_all.py
└── sources/  wiki/  proposals/   # runtime stores (operator-owned)
```

## Install & test

```bash
pip install -e .            # deps: pyyaml (networkx is an optional extra: .[graph])
python -m pytest tests/modules -q
python tests/run_all.py     # validators + skill evals + golden-file suite
```

`networkx` is optional — the pure-Python neighborhood traversal is canonical and
the suite passes with it absent. When present, its traversal is verified to
return identical results.

## Running the pipeline on any Agent-Skills runtime

1. Point your runtime at `.agents/skills/` so it discovers the nine skills.
2. Set `KG_PIPELINE_ROOT` to your project directory (or run from it). The
   pipeline reads `sources/`, builds `wiki/`, and writes `proposals/<change-id>/`
   there. Paths are centralized in `kg_pipeline.paths`.
3. Ask the runtime to *run the pipeline* — `pipeline-controller` activates and
   walks the stages, activating each child skill and gating every stage through
   the package-owned validation marker.

### Configuration (`references/config.yaml`)

The committed defaults (ADR-0003, ADR-0010): the source-count curve
`[1.00, 0.04, 1.10]` (+10% cap), `contradiction_floor 0.40`, `rollup min`, and
thresholds `proposal_seed_min 0.70` / `prior_art_floor 0.60` /
`grill_dismiss_min 0.85` / `adr_recommend_accept_min 0.90` /
`low_confidence_floor 0.45`; `audit.staleness_days 14`; and the per-stage
`autonomous` / `pause_and_ask` mode table. A project may ship its own
`references/config.yaml` to override.

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

`sources/karpathy-2026.md` ships as the worked example. After `ingest-source`:

```
wiki/
├── source-karpathy-2026.md
├── entity-llm-wiki.md
├── claim-rag-rediscovers-knowledge-on-every-query.md   (base 0.85, n=1, effective 0.85)
├── claim-llm-maintains-wiki-stateful.md                (base 0.82, n=1, effective 0.82)
└── question-when-does-the-wiki-drift.md
```

After `seed-proposal` for topic `entity-llm-wiki`, both claims (≥ 0.70) appear in
`## Context (from KG)` with their `effective` shown inline, the open question
appears under `## Candidate Problems`, and `## Constraints (from KG)` is present
but empty with `_KG provided no high-confidence content for this subsection._`.

A second source citing the same two claims raises both `effective` values via the
source-count multiplier (`n=2 → ×1.04`) — the smallest end-to-end demonstration
of compounding knowledge through confidence.

## Provenance

This bundle is the implementation of `kg-seeded-intent-driven-skills-design.md`,
carried through the intent workflow to specs (8 capabilities), a design with C4
diagrams, 11 accepted ADRs, and a 30-task plan under
`openspec/changes/spec-driven-development-2026-05-26-kg-seeded-intent-skills/`.
