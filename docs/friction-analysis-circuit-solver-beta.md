# Friction Analysis: circuit-solver-beta × scientia

**Source:** Five Claude session logs (2082 JSONL lines) covering the full lifecycle —
wiki schema migration, hermes schema adoption, kanban init/emit, swarm dispatch,
and 76-card pipeline execution to `done=42/76`.

**Date:** 2026-05-28 → 2026-05-30

**Objective:** Extract concrete friction points from an active project and
propose refinements to scientia that prevent merge conflicts and drift.

---

## Executive Summary

The circuit-solver-beta project exercised scientia's full pipeline — from wiki
ingestion through hermes emit and autonomous swarm execution. The pipeline
*worked*: 42 of 76 cards completed, real Rust code merged to `beta`. But the
execution layer generated **six categories of friction** that repeatedly
required human intervention, caused false escalations, and in one case merged
structurally incompatible codebases. Every friction point traces back to a gap
in scientia's conflict-prevention or drift-detection machinery.

The recommendations below are ordered by impact: the first three address the
most damaging failures (lineage divergence, wave non-enforcement, and self-
block stalling), while the later ones address quality-of-life and robustness.

---

## Friction Point 1: Incompatible Git Lineages (CRITICAL — merge conflict root cause)

### What happened

Task branches were cut from **two different git bases**:

| Tasks | Base commit | Structure |
|-------|-------------|-----------|
| #1 | `beta` HEAD at emit time | Single-crate `project/src/…` |
| #11, #12, #13, #20, #21… | `cad510f` (pre-existing `v1-spec` branch) | Multi-crate `crates/` workspace |

The `cad510f` lineage already contained a full multi-crate workspace
(`crates/netlist-graph/`, `crates/digital-kernel/`, etc.) with 515-line
`graph.rs` — a *fuller* implementation than #1's 146-line single-crate version.

When #11's integration merged, `beta` became multi-crate. #1's single-crate
work was then **entirely redundant** — its `project/src/netlist/` directory
would have conflicted structurally with the already-merged `crates/netlist-graph/`.

The operator had to manually: adopt the v1-spec workspace as trunk, archive #1's
chain (4 cards), and amend `design.md`'s Component Map post-hoc.

### Root cause in scientia

**The emit does not pin a git base SHA.** The `EmitPlan` records `source_sha`
(a content hash of the task's markers) but not the trunk HEAD at emit time.
Hermes workers branch from whatever HEAD is current at *dispatch* time, not at
*emit* time. If trunk advances between emit and dispatch (which it always does
once the first integrate merges), later workers branch from a different base
than earlier ones.

### Recommendation: `base_sha` pinning

1. **Record `base_sha` at emit time.** `scientia-hermes-emit` reads `git
   rev-parse HEAD` (or accepts it as a parameter) and embeds it in every card
   body as a `Required: branch from <sha>` instruction. The `CardSpec` dataclass
   gains an optional `base_sha: str` field.

2. **The implementer respects it.** The card body already says "in an isolated
   workspace"; add: "Branch from commit `<base_sha>`. If that commit is no
   longer on trunk, rebase onto current trunk but verify your `touches` still
   apply."

3. **The integrator verifies it.** Before merging, the integrator checks that
   the worker branched from a commit that is an ancestor of current trunk. If
   not, it reassigns to the conflict-resolver with a "stale base" note.

4. **Design-change detection.** If `base_sha` differs between two sibling
   tasks' integrate targets, the integrator surfaces this as a structural
   conflict signal — even before merge markers appear.

**Code changes:** `plan.py` `CardSpec` gains `base_sha`; `render.py`
`task_payload` includes it; `compose_body` inlines it in the instructions;
`preflight.py` gains an optional `git_head_probe` callable.

---

## Friction Point 2: Wave Caps Not Enforced at Dispatch (HIGH — merge conflict enabler)

### What happened

`conflict.compute_waves` correctly computed waves (capping concurrent editors
of a shared path at `max_parallel_per_file_group=2`). `synthetic_edges`
correctly generated dependency edges between wave groups. The plan built clean.

But the **daemon/dispatcher ignores wave information.** It simply dispatches
all `ready` cards. The synthetic edges *should* gate this — a wave-2 task's
impl depends on wave-1's integrate — but the edges are only as good as the
`touches` declarations, and several tasks' actual edits exceeded their declared
touch-sets (see Friction Point 5).

Result: multiple tasks simultaneously edited `Cargo.toml`, `Cargo.lock`,
`crates/digital-kernel/src/lib.rs`, and `crates/digital-kernel/src/kernel.rs`
— precisely the collisions the wave math was designed to prevent.

### Root cause in scientia

The wave computation is pure and correct, but it has **no runtime enforcement.**
The wave index is computed, consumed to generate edges, and then discarded.
The dispatcher has no visibility into it, and there is no post-hoc audit
checking whether actual edits respected the declared touches.

### Recommendation: Touches verification at integrate time

1. **Integrator `touches` audit.** Before merging, the integrator runs
   `git diff --name-only <base_sha>..<branch_head>` and compares the result
   against the card's declared `touches`. Any file outside the touch-set is
   flagged as an **undeclared edit** and the card is reassigned to the
   conflict-resolver with the discrepancy listed.

2. **Wave membership in card body.** Include `wave: N` in the card body so the
   dispatcher can (optionally) respect it as a scheduling hint, and the
   conflict-resolver can see it when diagnosing a collision.

3. **`ownership_smells` promoted to hard error for undeclared touches.** Today
   `ownership_smells` is a warning (a `touches` outside owned globs). At emit
   time this is appropriate (the skill author may not know exact paths). But
   `validate_plan` should also run a *post-impl* check: after an implementer
   completes, verify actual edits match declared touches. This is a new
   function in `validators.py`: `verify_touches(task, actual_files) -> list[str]`.

**Code changes:** `validators.py` gains `verify_touches`; `render.py`
`compose_body` inlines `wave: N`; `conflict.py` `compute_waves` returns a
`dict[int, int]` that `plan.py` threads into `CardSpec.wave`; the
conflict-resolver SKILL.md gains a "verify touches" step before merge.

---

## Friction Point 3: Implementer Self-Block Stalling (HIGH — pipeline throughput)

### What happened

Every implementer agent (running under Fireworks) completed with green tests,
clippy clean, and a commit — then **self-blocked with `review-required`**
instead of completing. This happened for #1, #13, #25, #8, #9, #10, and likely
others. The pipeline has a *dedicated review stage* next in the chain, so the
self-block is redundant — it duplicates the reviewer's job and stalls the
pipeline until a human (or the operator agent) manually unblocks.

The operator had to develop a workaround: `unblock` the card, which requeues it
for the daemon to re-dispatch. The implementer then completed it on the second
run instead of re-blocking. But each self-block costs 60s+ of daemon tick
latency plus the operator's attention.

### Root cause

The implementer's `SOUL.md` is generic — it doesn't instruct the agent to
*complete* when tests pass. The `review-required` self-block comes from the
agent's own caution, which is reasonable in isolation but counterproductive
given the pipeline design (impl → review → integrate).

### Recommendation: Card-body completion criteria

1. **Explicit completion criteria in the impl card body.** The `compose_body`
   function already generates instructions. Add a **Completion Criteria** block:

   ```
   ## Completion Criteria
   Complete (do NOT block) when ALL of:
   - Every spec scenario traced above has a passing test
   - `cargo test` passes (or equivalent verification command)
   - `cargo clippy` passes with no warnings
   - All edits are within the declared touches paths
   
   Do NOT self-block for review — the next card in this pipeline is a
   dedicated reviewer. If you have a design concern, note it in the
   handoff `residual_risk` field and complete anyway.
   ```

2. **`SOUL.md` template.** The `scientia-hermes-init` skill already authors
   per-profile descriptions. Add a sentence: "Complete your work card when
   tests pass; do not self-block for review."

3. **`unblock` automation.** In `scientia-hermes-status`, detect green self-
   blocks (status=blocked, reason contains "review-required", and the
   verification metadata shows all tests passing) and recommend unblock
   automatically rather than surfacing them as escalations.

**Code changes:** `plan.py` `_instructions` adds the Completion Criteria block;
`scientia-hermes-init/SKILL.md` adds the SOUL.md guidance;
`scientia-hermes-status/SKILL.md` adds green-self-block detection.

---

## Friction Point 4: Transport Version Skew (HIGH — emit failure)

### What happened

Scientia 1.0.0's `_cli_transport()` issues `hermes kanban task create` /
`hermes kanban task update <id>`. Hermes v0.15.1's kanban CLI has **no `task`
subcommand** — verbs are `create`, `edit`, `assign`, `promote`, etc. directly
under `kanban`. The native CLI backend fails on the first card.

The operator fell back to an external `emit_via_cli_shim.py` script that
correctly called `hermes kanban create` with positional title, group-level
`--board`, etc. But this shim was hand-rolled and lives in the project repo,
not in the scientia package.

### Root cause

The `_cli_transport()` function in `apply.py` was written against an
assumed future Hermes CLI grammar that includes `task` subcommands. The
`render.to_cli` function correctly documents the v0.15.1 grammar (no `task`
subcommand, positional title, group-level `--board`), but `_cli_transport`
doesn't use it — it has its own inline command construction that diverges.

### Recommendation: Unify CLI transport with `render.to_cli`

1. **`_cli_transport` should call `render.to_cli`**, not re-implement the
   command construction. The `render.to_cli` function already produces the
   correct v0.15.1 argv lists. The transport should execute them rather than
   building its own commands.

2. **Version probe.** At preflight time, run `hermes kanban --help` and parse
   the available subcommands. If `task` is present, use the newer grammar; if
   not, use the v0.15.1 grammar. Store the detected version in the
   `PreflightResult` for the apply phase to consume.

3. **Integration test with real CLI.** The current test suite uses a recording
   stub. Add a single integration test that runs against a real `hermes kanban`
   CLI (skipped if `hermes` is not on PATH) to catch grammar drift.

**Code changes:** `apply.py` `_cli_transport` refactored to use `render.to_cli`
output; `preflight.py` gains `cli_version_probe`; test suite gains
`test_cli_transport_integration`.

---

## Friction Point 5: Touches Declarations vs. Reality (MEDIUM — merge conflict enabler)

### What happened

Task #11's card declared `Touches: project/src/digital/event_queue.rs`, but the
agent actually shipped a new `crates/digital-kernel/` workspace crate and edited
the root `Cargo.toml` — neither in its declared touch-set. Task #20 similarly
duplicated `LogicValue` across crates, creating a contract gap that the
conflict-resolver had to reconcile.

The `ownership_smells` check at emit time correctly produces warnings, but
these are *pre-emit* — they validate the *declared* touches against the
Component Map, not the *actual* edits against the declarations. There is no
post-implementation verification.

### Root cause

Two gaps:
1. The skill author writes `touches` based on *predicted* file paths, which are
   approximate before code exists.
2. No runtime check compares actual git diffs against declared touches.

### Recommendation: Touches reconciliation loop

1. **Implementer handoff includes actual files.** The `kanban_complete`
   metadata already includes `changed_files`. The implementer's Completion
   Criteria (Friction Point 3) should require reporting `changed_files` that
   match the declared `touches` (with a warning for undeclared files).

2. **Integrator verifies.** Before merge, compare `changed_files` against
   `touches`. Flag any undeclared file as a potential collision risk. If an
   undeclared file collides with another task's declared touches, reassign to
   the conflict-resolver.

3. **Design amendment trigger.** If an implementer consistently creates files
   outside its component's owned globs, the design's Component Map is stale.
   The status skill should surface this as a drift signal recommending a design
   amendment.

**Code changes:** `validators.py` gains `verify_touches`; conflict-resolver
SKILL.md gains a touches-audit step; `plan.py` `_instructions` requires
`changed_files` in the handoff.

---

## Friction Point 6: Gateway/Dashboard Port Mismatch (MEDIUM — preflight failure)

### What happened

Config had `rest_base: http://127.0.0.1:8787`, but the Hermes dashboard defaults
to port `9119`. Preflight failed with "gateway not reachable." The operator had
to manually start the dashboard bound to `8787` and discover that nothing in
`.hermes` was configured to serve that port.

When the gateway was started (for continuous dispatch), it was board-unscoped —
it dispatched the *other* `circuit-solver` board and spawned an unrelated worker,
incurring unintended spend. The operator had to stop the gateway and start a
board-scoped daemon instead.

### Root cause

1. The `rest_base` port is a config choice with no enforcement mechanism — the
   dashboard must be manually bound to match.
2. The gateway's embedded dispatcher has no board filter; it dispatches
   everything it can see.
3. `daemon` is deprecated in v0.15.1 (dispatch runs inside the gateway), but
   the deprecation was not surfaced until the daemon exited immediately.

### Recommendation: Preflight diagnostics

1. **Dashboard port detection.** Preflight should probe the dashboard's
   actual port (default `9119`) and compare it to `rest_base`. If they differ,
   the error message should say "dashboard is on :9119 but config expects :8787
   — start with `hermes dashboard --port 8787` or update `rest_base`."

2. **Board-scoped dispatch recommendation.** When `backend=cli`, preflight
   warns that a dispatcher must be running. Add: "For board-scoped dispatch,
   use `hermes kanban --board <slug> daemon --interval 60` rather than the
   gateway's embedded dispatcher."

3. **Daemon deprecation surface.** Preflight should probe the daemon verb's
   availability and warn if it is deprecated for the installed Hermes version.

**Code changes:** `preflight.py` gains `_dashboard_port_probe` and board-scoped
dispatch recommendation in the CLI-backend warning path.

---

## Friction Point 7: Integrator False Positive Conflicts (MEDIUM — wasted resolver cycles)

### What happened

Task #25's integrator reported a merge conflict (2 files — `kernel.rs`,
`lib.rs`). The conflict-resolver attempted the merge and found **zero
conflicts** — the integrator's report was a false positive. The merge completed
cleanly.

### Root cause

The integrator likely pre-emptively flagged potential conflicts based on file
overlap rather than actually attempting `git merge`. The card instructions say
"if it conflicts, reassign to the conflict-resolver," but the integrator
interpreted file-level overlap as a conflict without running the merge.

### Recommendation: Merge-before-reassign discipline

1. **Integrator must attempt the merge before reassigning.** Update the
   integrate card instructions:

   ```
   Attempt `git merge <branch>`. Only if git reports conflicts
   (exit code 1, conflict markers in files) do you reassign to the
   conflict-resolver. File overlap alone is NOT a conflict.
   ```

2. **Conflict-resolver verifies the integrator's claim.** The resolver's
   procedure already starts with "reproduce the conflict" (step 2). Add: "If
   the merge succeeds cleanly, the integrator's conflict was a false positive.
   Complete the integrate card normally with `resolution_kind:
   false-positive-conflict`."

**Code changes:** `plan.py` `_instructions` for the integrate stage adds the
merge-first discipline; conflict-resolver SKILL.md adds false-positive handling.

---

## Friction Point 8: Worktree Recycling / False Escalations (MEDIUM — operator trust)

### What happened

The operator read a worktree directory (`t_5f1bedbd`) that had been *recycled*
for a different task, and reported a soundness/UB bug in `results.rs` that
doesn't exist in task #22's actual branch. The "alarming" `results.rs` with
`setflags(...).ok()` placeholder/UB came from a recycled worktree — not from
the task under review.

Later, the operator used the wrong merge base (`cad510f` instead of the
current `beta` HEAD) and fabricated a `run_until(&mut self, target:
SimulationTime) -> KernelRunReport` vs `run_until(&mut self, sink: &mut dyn
Write, target: SimulationTime)` discrepancy — the "sink" variant never existed.

### Root cause

1. Worktree directories are recycled by the dispatcher when a task completes.
   Reading from a worktree path at time T may return a different task's code
   than the one that occupied it at time T-1.
2. The operator agent (Claude) relied on cached/stale file reads during
   parallel operations, leading to analysis errors.

### Recommendation: Worktree grounding discipline

1. **Always use `git show <branch>:<path>` rather than worktree reads.** The
   conflict-resolver SKILL.md should mandate this: read from the *branch*, not
   the filesystem, because the filesystem is ephemeral.

2. **Branch name is the stable identifier.** Each task's branch is
   `<change-id>/task-N` — this is deterministic and never recycled. The
   `kanban_show()` output includes the branch; all analysis should use it.

3. **Add this to the operator-facing status skill.** `scientia-hermes-status`
   should note: "Worktree directories are recycled; use git branch references
   for code analysis, not filesystem paths."

**Code changes:** conflict-resolver SKILL.md gains the git-show discipline;
`scientia-hermes-status/SKILL.md` gains the worktree-recycling warning.

---

## Friction Point 9: Profile Model Binding Gap (LOW — init friction)

### What happened

The four profiles (implementer, reviewer, integrator, conflict-resolver) were
created without model bindings. `hermes model` is interactive-only (OAuth
picker), so the operator had to hand-write `config.yaml` files for each profile
mirroring the working `scientia-implementer` format.

### Root cause

`scripts/provision_profile.sh` creates the profile but does not bind a model.
`hermes model` requires interactive selection. The scientia-hermes-init skill
assumes profiles come with models but doesn't provide a non-interactive path.

### Recommendation: Non-interactive model binding

1. **`provision_profile.sh` accepts a `--model <provider:model_id>` flag.** If
   provided, it writes the `config.yaml` with the `model:` and
   `custom_providers:` blocks automatically.

2. **Init skill uses it.** `scientia-hermes-init` already knows the model from
   the `hermes.profiles.<name>.model` config block. It passes it to
   `provision_profile.sh` at provision time.

3. **Fallback for missing model.** If no model is specified in config, init
   warns: "profile `<name>` has no model binding; agents will use the global
   default. Set `hermes.profiles.<name>.model` in config or run `hermes model`
   interactively."

**Code changes:** `provision_profile.sh` gains `--model` flag;
`scientia-hermes-init/SKILL.md` documents the config-driven model path.

---

## Friction Point 10: Config Schema Migration Pain (LOW — setup friction)

### What happened

`development/config.yaml` carried old-scheme keys (`scientia_schema_version`,
`bundle_version_installed`, `wiki`, `emit`, `verify`, `ingest`, `tenants`) that
the new scientia schema doesn't recognize. The orchestrator surfaced these as
unrecognized keys. The operator had to manually strip them and rewrite the file
to contain only the recognized `hermes` block.

### Root cause

No migration path from old config schema to new. The orchestrator correctly
surfaces unrecognized keys but doesn't offer to translate them.

### Recommendation: `scientia config migrate`

1. **Add a `scientia config migrate` command** that reads a config with old-
   scheme keys and produces the equivalent new-schema config. Log the mapping
   for audit.

2. **Orchestrator suggests it.** When unrecognized keys are detected, the
   orchestrator should say: "Run `scientia config migrate` to translate these
   keys to the current schema."

**Code changes:** New `scientia/config.py` module with `migrate()` function;
orchestrator SKILL.md gains the migration suggestion.

---

## Friction Point 11: Shared Contract Drift — LogicValue Duplication (MEDIUM — semantic conflict)

### What happened

Tasks #11 and #20 both defined `LogicValue` independently — one in
`digital-kernel`, one in `netlist-graph`. No contract pinned the type to one
owner. The conflict-resolver had to reconcile the duplication, and the design
had to be amended post-hoc to add a shared-types contract.

### Root cause

The `produces-contract` / `uses-contract` markers exist to prevent exactly
this, but they were not present in the original `tasks.md`. The `ratify_contracts`
function catches unratified `uses-contract` declarations, but it cannot detect
an *undeclared* contract duplication — two tasks independently inventing the
same type without either marking it as a contract.

### Recommendation: Contract inference from touches overlap

1. **Emit-time contract smell detection.** If two tasks touch the same path and
   neither declares a contract for it, `ownership_smells` should warn: "tasks
   #A and #B both touch `<path>` with no shared contract declared — consider
   adding `produces-contract`/`uses-contract` markers."

2. **Integrator type-duplication check.** When the integrator sees two worker
   branches defining the same type name (detected via `grep -r "struct
   <Name>"` or `grep -r "enum <Name>"`), flag it as a potential undeclared
   contract collision before merging.

3. **Post-merge audit.** `scientia-hermes-status` should run a lightweight
   duplicate-symbol scan on the merged trunk and surface any types defined in
   more than one component.

**Code changes:** `validators.py` `ownership_smells` gains cross-task touches
overlap detection; integrator instructions add a type-collision check;
`scientia-hermes-status/SKILL.md` adds a post-merge duplicate-symbol scan.

---

## Summary: Priority-Ordered Recommendations

| # | Friction Point | Severity | Recommendation | Code Touchpoint |
|---|---------------|----------|----------------|-----------------|
| 1 | Incompatible git lineages | CRITICAL | `base_sha` pinning in emit + card body | `plan.py`, `render.py`, `preflight.py` |
| 2 | Wave caps not enforced | HIGH | Post-impl touches verification | `validators.py`, conflict-resolver SKILL.md |
| 3 | Implementer self-block | HIGH | Completion criteria in card body + SOUL.md | `plan.py`, `scientia-hermes-init/SKILL.md` |
| 4 | Transport version skew | HIGH | Unify `_cli_transport` with `render.to_cli` | `apply.py`, `preflight.py` |
| 5 | Touches vs. reality | MEDIUM | Implementer handoff + integrator audit | `validators.py`, conflict-resolver SKILL.md |
| 6 | Gateway port mismatch | MEDIUM | Preflight port detection + board-scoped advice | `preflight.py` |
| 7 | False positive conflicts | MEDIUM | Merge-before-reassign discipline | `plan.py`, conflict-resolver SKILL.md |
| 8 | Worktree recycling | MEDIUM | Git-show discipline over filesystem reads | conflict-resolver SKILL.md, `scientia-hermes-status/SKILL.md` |
| 9 | Profile model binding | LOW | `--model` flag on provision script | `provision_profile.sh`, `scientia-hermes-init/SKILL.md` |
| 10 | Config migration | LOW | `scientia config migrate` command | New `config.py` |
| 11 | Undeclared contract duplication | MEDIUM | Cross-task touches overlap smell + post-merge audit | `validators.py`, `scientia-hermes-status/SKILL.md` |

---

## Architectural Principle Extracted

The dominant pattern across all friction points is: **scientia's prevention
machinery operates at declaration time but not at execution time.** The
conflict math (waves, contracts, touches) is computed once during emit and
then trusted for the entire execution. But execution is where the real world
diverges from declarations — agents edit undeclared files, branch from
different bases, self-block redundantly, and report false conflicts.

The single most impactful architectural change is: **add execution-time
verification loops** that compare reality back to the plan. Specifically:

1. **Integrate-time touches audit** (does the git diff match the declarations?)
2. **Base SHA continuity check** (are sibling tasks branching from a common ancestor?)
3. **Post-merge duplicate-symbol scan** (are types being independently invented?)
4. **Green self-block auto-flow** (if tests pass, the pipeline should advance)

These four checks, run at the integrate stage, would have prevented or
auto-resolved **7 of the 11 friction points** in this project.
