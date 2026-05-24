---
title: "intent-driven Schema"
type: concept
tags: [concept, openspec, schema, workflow, adr]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/intent-driven-schema.md", "raw/intent-driven-template/index.md"]
confidence: high
---

## Definition

`intent-driven` is a [[concepts/custom-workflow-schema|custom OpenSpec workflow
schema]] for changes where contributor intent, observable behaviour, technical
design, and durable architectural decisions should all be captured *before*
implementation. It defines the five-artifact lifecycle
`proposal -> specs -> design -> adr -> tasks`, mandates that behaviour specs be
written in [[concepts/gherkin|Gherkin]] style, and persists
[[concepts/architectural-decision-record|ADRs]] outside the change folder so they
survive archival. It is one of the schemas catalogued in the
[[entities/openspec-schemas|openspec-schemas]] repository and ships as a bundled
local copy inside the [[entities/intent-driven-template|intent-driven-template]].

## How It Works

The schema's `schema.yaml` declares an artifact dependency graph:

```text
proposal ──► specs ──► design ──► adr ──► tasks
```

with `apply` tracking `tasks.md`. Each stage has gate expectations:

- **proposal** — states *why* the change matters and lists the capabilities that
  need behaviour specs (the Capabilities section is the contract between proposal
  and specs). Sections: Why / What Changes (mark **BREAKING**) / Capabilities
  (New + Modified, kebab-case) / Impact.
- **specs** — one OpenSpec Markdown delta file per capability at
  `specs/<capability>/spec.md`. The Markdown headings are the *merge wrapper*
  (`### Requirement:`, the exact four-hash `#### Scenario:`); the bodies are
  written in [[concepts/gherkin|Gherkin]] `GIVEN`/`WHEN`/`THEN`. Delta operations
  are `## ADDED`, `## MODIFIED` (full updated content, never a partial diff),
  `## REMOVED` (with Reason + Migration), and `## RENAMED` (FROM:/TO:). **No
  `.feature` files are produced.**
- **design** — explains *how* and must account for currently in-force ADRs: list
  every file in `<repo>/adr/`, build the supersession graph from each ADR's
  `Supersedes:` field, and constrain the design only by accepted, non-superseded
  ADRs. A decision to revisit a live ADR is flagged under Open Questions, not by
  editing it.
- **adr** — distills the design's significant decisions into ADR files written to
  the repo's top-level `adr/` folder (never under `openspec/`). See **Key
  Parameters** for the immutability rule. Uses the [[concepts/madr|MADR-short]]
  template.
- **tasks** — a dependency-ordered checkbox list (`- [ ] X.Y …`) the apply phase
  parses to track progress.

The payoff is the [[concepts/spec-adr-dual-representation|dual representation]]:
after a change ships, `specs/` says what the system does today and `adr/` says how
and why it got that way.

## Key Parameters

| Field | Value |
|-------|-------|
| Artifacts | `proposal → specs → design → adr → tasks` |
| Spec form | OpenSpec Markdown delta wrapper + Gherkin-style requirement/scenario bodies |
| Durable outputs | `specs/<capability>/spec.md` and ADRs in top-level `adr/` |
| Scaffolding outputs | `proposal.md`, `design.md`, `tasks.md` (archived) |
| ADR lifecycle | immutable once accepted; superseded via `Supersedes:`, never edited |
| ADR filenames | `adr/NNNN-kebab-title.md`, monotonic sequence, never reused |
| Activate | `schema: intent-driven` in `openspec/config.yaml` |
| Validate | `openspec schema validate intent-driven` |
| Distribution | [[entities/openspec-schemas]] (upstream) and [[entities/intent-driven-template]] (bundled copy) |

## When To Use

- Product or platform changes with meaningful behaviour *and* long-lived design
  decisions; cross-module work; or architecture choices future changes must honor.
- When you want behaviour captured as executable [[concepts/gherkin|Gherkin]]
  examples and rationale captured as durable ADRs in one workflow.

Not a good fit for small tactical fixes, docs-only changes, dependency bumps, or
behaviour-only work — for the last of these the lighter `behaviour-driven` schema
is enough.

## Relationship to `spec-driven-with-adr`

`intent-driven` and [[concepts/spec-driven-with-adr-schema|`spec-driven-with-adr`]]
are sibling schemas from the same catalog and share the identical five-artifact
graph and the durable-ADR-outside-`openspec/` rule. The practical distinction is
emphasis: `intent-driven` makes Gherkin-style behaviour specs and the
"design reads the in-force ADR supersession graph" step first-class, and is the
schema bundled and demonstrated by the [[entities/intent-driven-template]];
`spec-driven-with-adr` is framed primarily as adding a durable ADR stage to the
default `spec-driven` flow.

## Risks & Pitfalls

- **MODIFIED with partial content loses detail at archive time** — a `## MODIFIED`
  requirement must contain the entire updated block, not a diff.
- **Heavyweight for small work** — running five gated stages on a trivial or fully
  reversible change is friction; downgrade to a lighter schema.
- **Top-level `adr/` collisions** — repositories that already keep ADRs elsewhere
  (e.g. `docs/adr/`) must reconcile locations or risk a split
  [[concepts/decision-log|decision log]].
- **No bundled Gherkin lint** — the schema intentionally omits Gherkin lint config;
  any `.feature`-style linting is the target project's responsibility.

## Related Concepts

- [[concepts/custom-workflow-schema]] — the OpenSpec mechanism this is an instance of
- [[concepts/spec-driven-with-adr-schema]] — its sibling schema in the same catalog
- [[concepts/gherkin]] — the behaviour-spec style it mandates
- [[concepts/architectural-decision-record]] — the durable artifact its `adr` stage produces
- [[concepts/madr]] — the ADR template family it defaults to
- [[concepts/durable-artifacts-vs-scaffolding]] — the lifecycle principle it encodes
- [[concepts/spec-adr-dual-representation]] — what specs vs ADRs each capture
- [[concepts/opsx-workflow]] — the workflow engine that runs the schema
- [[concepts/delta-spec]] — the spec representation it preserves for archive

## Sources

- [intent-driven schema README + schema.yaml](https://github.com/intent-driven-dev/intent-driven-template/tree/main/openspec/schemas/intent-driven) (`raw/intent-driven-template/intent-driven-schema.md`)
- [intent-driven-template README](https://github.com/intent-driven-dev/intent-driven-template) (`raw/intent-driven-template/index.md`)
- Upstream canonical schema: [openspec-schemas / intent-driven](https://github.com/intent-driven-dev/openspec-schemas/tree/main/openspec/schemas/intent-driven)
