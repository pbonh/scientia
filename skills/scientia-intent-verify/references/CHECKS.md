# scientia-intent-verify check inventory

Authoritative list of every check the verify skill runs, grouped by
dimension. The skill body delegates to this reference rather than
inlining all of it.

## Completeness

| Check | Severity | Description |
|---|---|---|
| `proposal-exists` | CRITICAL | `proposal.md` must exist for the change. |
| `proposal-why-non-empty` | WARNING | `## Why` has at least one paragraph (not just a placeholder). |
| `proposal-what-changes-non-empty` | CRITICAL | `## What Changes` has at least one bullet. |
| `proposal-capabilities-non-empty` | CRITICAL | `## Capabilities Introduced or Modified` lists ≥ 1 capability. |
| `spec-per-capability` | CRITICAL | Every capability in `proposal.md` has a matching `specs/<capability>/spec.md`. |
| `spec-has-scenario` | CRITICAL | Each `spec.md` has at least one `### Scenario:` block. |
| `spec-has-glossary` | WARNING | Each `spec.md` has a non-empty `## Glossary` section. |
| `design-exists` | CRITICAL | `design.md` must exist. |
| `design-overview-non-empty` | WARNING | `## Overview` has at least one paragraph. |
| `design-has-diagram` | WARNING | `design.md` has at least one Mermaid block. |
| `design-adr-treatment-complete` | WARNING | Every ADR in the design manifest's slice 5 has a row in `## In-Force ADR Treatment`. |
| `tasks-exists` | CRITICAL | `tasks.md` must exist. |
| `tasks-non-empty` | CRITICAL | `tasks.md` has at least one `- [ ]` task. |
| `tasks-per-capability` | WARNING | Each capability mentioned in proposal has ≥ 1 task. |
| `manifest-core-exists` | CRITICAL | `development/manifests/<tenant>/<change-id>/core.md` exists. |
| `manifest-design-exists` | WARNING | `manifests/.../design.md` exists (computed at design entry). |
| `manifest-tasks-exists` | WARNING | `manifests/.../tasks.md` exists (computed at tasks entry). |
| `breaking-change-acknowledged` | WARNING | Every `**BREAKING:**` bullet in proposal is referenced by at least one spec scenario or ADR. |

## Correctness

| Check | Severity | Description |
|---|---|---|
| `wikilink-resolves` | CRITICAL | Every `[[wiki-link]]` in any change artifact resolves. |
| `spec-ref-resolves` | CRITICAL | Every `@spec: <capability>#<scenario>` reference resolves to a real scenario slug. |
| `adr-ref-resolves` | CRITICAL | Every `@adr: ADR-NNNN` reference resolves to a real ADR file. |
| `adr-y-statement-five-clauses` | WARNING | Every ADR's Y-statement contains all of: "In the context of", "facing", "we decided for", "and against", "to achieve", "accepting". |
| `gherkin-single-when` | WARNING | Every `### Scenario:` block has exactly one `When` step. |
| `gherkin-observable-then` | SUGGESTION | Every `Then` step references observable state, not implementation detail (heuristic: no implementation noun in the `Then`). |
| `gherkin-named-personas` | WARNING | Every `Given` step references a persona named in the spec's `## Personas` block. |
| `glossary-terms-defined` | WARNING | Every term used in a `### Scenario:` block that appears in the manifest core's slice 4 glossary is used consistently with its definition (heuristic: at least one mention in `## Glossary`). |
| `adr-supersedes-resolves` | CRITICAL | Every ADR's `supersedes:` list points to existing ADRs. |
| `adr-superseded-by-resolves` | CRITICAL | Every ADR's `superseded_by:` (if set) points to an existing ADR. |
| `adr-immutable-body` | CRITICAL | Accepted ADRs have not been edited since acceptance (best-effort: compare to git history). |
| `manifest-snapshot-pin-resolves` | CRITICAL | Every manifest layer's `wiki_snapshot:` git rev resolves. |

## Coherence

| Check | Severity | Description |
|---|---|---|
| `design-honors-in-force-adr` | CRITICAL | If `## In-Force ADR Treatment` marks an ADR `Overridden`, a corresponding new ADR with `supersedes: [ADR-NNNN]` exists in this change. |
| `design-vs-spec-no-contradiction` | WARNING | No spec scenario contradicts a stated design constraint. |
| `tasks-cover-spec-scenarios` | WARNING | Every spec scenario is referenced by at least one task in `tasks.md`. |
| `tasks-order-respects-dependencies` | WARNING | Tasks listed `(depends on #N)` come after task N. |
| `proposal-what-changes-covered` | WARNING | Every bullet in `## What Changes` has at least one spec scenario or ADR backing it. |
| `tasks-md-vs-kanban-emit-consistent` | SUGGESTION | If a previous emit ran, `tasks.md` and the parent task's `## Implementation Checklist` are consistent. |
| `in-flight-singleton` | CRITICAL | This is the only non-archived change for its tenant. |

## How findings are formatted in the verify report

```markdown
- **<SEVERITY>** — `<location>` — <message>
```

Where `<location>` is the file path + optional line number (e.g.,
`specs/refunds/spec.md:42`) and `<message>` is a short, actionable
description of what's wrong.
