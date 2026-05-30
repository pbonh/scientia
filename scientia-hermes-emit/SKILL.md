---
name: scientia-hermes-emit
description: Turns a finished change into Hermes Kanban pipelines plus dependency links. Parses tasks.md and design.md, computes file-collision waves and shared-contract ratification, builds an impl-review-integrate (or single) plan, and applies it REST-first, ledger-idempotent. You own the task-to-profile routing and card-body judgment; the scientia.hermes package owns every key, edge, wave, ratification, and topological order. Activate when tasks.md exists and scientia-hermes-init reported clean.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+; a local Hermes install with the Kanban feature
metadata:
  stage: hermes-emit
  version: "0.2"
---

# scientia-hermes-emit

Drive a finished change onto a live Hermes board. This is the **drive** phase.
You compose the `Routing` (task → profile) and any preflight resolution; the
package owns everything byte-stable — keys, edges, waves, contract ratification,
topological order, and the single side-effecting write.

> **You do not compute keys, edges, waves, ratification, or order.** Those are
> the package's job (`scientia.hermes.*`). Your judgment is the routing and the
> framing — never the derived numbers.

## Activate when

`proposals/<change-id>/tasks.md` exists and `scientia-hermes-init` returned a
clean preflight. Absent a `hermes:` config block, do not activate at all.

## Inputs

- `tasks.md` (required), `design.md` (C4 + Component Map + Shared Contracts).
- `specs/`, `adrs/` for body context.
- The `hermes:` config block.

## Procedure (delegate the determinism)

1. **Parse.** `tasks = scientia.hermes.parse.parse_tasks(tasks_md)`;
   `c4, comp_map, contracts = scientia.hermes.parse.parse_design(design_md)`.
2. **Resolve the routing (judgment).** Build a
   `scientia.hermes.plan.Routing` grounded in the C4 components and ADR
   ownership: pick `default_implementer/reviewer/integrator`, the `resolver`
   (the `conflict-resolver` profile), per-task overrides, `board`
   (`scientia.hermes.board.resolve_board(<`board:` config>)`, which defaults to
   the current project name when `board:` is unset — matching the board
   `scientia-hermes-init` provisioned), and `tenant` (from `tenant_strategy`).
   Compose nothing the package composes.
3. **Set options.** Build `scientia.hermes.plan.PlanOptions` from the `hermes:`
   block (`pipeline`, `emit_epic`, `workspace`, `max_parallel_per_file_group`,
   `conflict_prevention`). Pass `adr_contracts` = the set of contract names
   ratified by an **accepted** ADR (read the ADR statuses; this is the only place
   acceptance is resolved, keeping `conflict.ratify_contracts` pure).
4. **Read the trunk base SHA.** Run `git rev-parse HEAD` in the project root
   to capture the current trunk commit. Pass it as `base_sha` to
   `build_plan` so each impl/single card carries a pinned branch point —
   preventing lineage divergence when trunk advances between emit and dispatch.
5. **Build the plan.** `plan = scientia.hermes.plan.build_plan(cid, tasks, c4,
   comp_map, contracts, routing, options, base_sha=base_sha)`. This raises
   `ContractError` (an unpinned `uses-contract`) or `CycleError` (a
   dependency/wave cycle) — surface either verbatim and halt.
6. **Validate.** `scientia.hermes.validators.validate_plan(plan,
   known_profiles=...)` and `validate_routing(...)`; surface
   `ownership_smells(tasks, comp_map)` as warnings (a `touches` outside its
   component is a smell, not a hard stop). Also surface
   `touches_overlap_warnings(tasks)` — tasks sharing a touched path with no
   shared contract are at risk of independent type invention. Run
   `scientia.hermes.preflight.check(plan, ...)` and refuse on any error.
7. **Apply.** `scientia.hermes.apply.apply(plan, dry_run=False,
   backend=..., on_supersede=...)`. It is the single writer: REST-first,
   ledger-idempotent (skips keys already created), captures ids, archives
   superseded cards, and writes `hermes/emit-ledger.json`. Show a dry-run diff
   first when the operator wants one (`dry_run=True`).
8. **Report the diff.** Use `scientia.hermes.ledger.diff(old, plan)` to report
   added / changed (re-keyed → archived) / removed cards.

## Card bodies & handoff

The package composes each card body deterministically from the `hermes-card` /
`hermes-handoff` templates: the inlined traces (`traces-spec`, `traces-adr`,
component, touches, contracts), per-stage instructions, and the **Required
Handoff** block the worker returns via `kanban_complete(summary, metadata)`
(`changed_files`, `verification`, `dependencies`, `branch_head`,
`residual_risk`). `branch_head` is load-bearing for `integrate` and the resolver.

## Conflict robustness (what the plan encodes)

- **Prevention.** `compute_waves` caps concurrent editors of a shared `touches`
  path at `max_parallel_per_file_group`; `synthetic_edges` serialize the overflow
  onto the prior wave's integrate. `ratify_contracts` links a `uses-contract`
  consumer behind its producer (or an accepted ADR), refusing otherwise.
- **Resolution.** The `integrate` card instructs the integrator to **reassign a
  conflict to `conflict-resolver`** (never block to a human); escalation is the
  exception, reserved for genuine spec contradictions.

## Decision rules

- A task with no `traces-spec` is a warning, not a stop — surface it.
- Never hand-author keys, links, waves, or order; if you are tempted to, you are
  doing the package's job.
- Refuse (do not partially emit) on any preflight or validation error.

## Acceptance behavior

- Each task expands into linked `impl→review→integrate` cards (or one `single`
  card); `(depends on #M)` parents task N's impl on task M's integrate.
- Re-emitting an unchanged change creates zero new cards; an edited task re-keys,
  is reported under `changed`, and (default) archives its superseded card.
- A `uses-contract` with no producer/ADR refuses with `ContractError`; a cycle
  refuses with `CycleError`.
