# Friction Analysis: circuit-solver-**delta** × scientia

**Source:** Four Claude session logs in the `circuit-solver-delta` project plus the
live Hermes board (`circuit-solver-delta`), the emit-ledger, the four
project-prefixed profiles, and direct git/SQLite inspection of the
`circuit_solver.delta` worktree.

**Date:** 2026-05-31 → 2026-06-01

**Objective:** This is the **third** run of the same change-id
(`2026-05-28-multidomain-solver-architecture`) on the same repo — after
`circuit-solver-beta` (which produced [friction-analysis-circuit-solver-beta.md](friction-analysis-circuit-solver-beta.md))
and `circuit-solver-gamma`. Most of beta's 11 recommended fixes were committed
(`8c8da1b`, `d608e87`, `e03efbd`, …). So the question here is **which fixes
held, which recurred, and what new failure modes the delta run exposed** — and
what scientia should change next.

---

## Executive Summary

Delta's scientia pipeline (ingest → wiki → proposal → grill → specs → design →
ADR → tasks → hermes-init → hermes-emit) ran cleanly to a fully-emitted 80-card
board with correct dependency gating, ratified contracts, and bound profile
models. The **planning** layer is in good shape.

The **execution** layer dead-ended. As of this analysis the board sat at 3 done
/ 3 blocked / 70 todo, and — critically — **trunk was being silently
corrupted**: between two snapshots an hour apart, `delta` advanced from a clean
`36d5389` (empty `project/`) to `fd13136`, having merged three integrate cards
that pulled a **sibling board's** work (a root-level multi-crate `crates/`
workspace) into delta's trunk. Delta's trunk is now a contradictory mix of
`project/` + root `crates/` + foreign `openspec/`/`Cargo.toml`/`pyproject.toml`.

Every delta failure traces to one of two new root causes that sit *underneath*
beta's findings:

1. **The declarations are detached from the repository.** The branch names, the
   Component Map globs, and the "merge the task-N branch" instruction all name
   things that either don't exist on trunk or are shared across boards. Beta's
   lesson was "prevention runs at declaration time, not execution time." Delta's
   is sharper: *the declarations themselves are fictional.*
2. **The fixes live in code that doesn't run.** Several beta fixes are present in
   `src/` but not in the installed wheel; and the merge/escalation discipline
   lives entirely in the conflict-resolver profile, which is **never reached**
   because the integrator blocks instead of reassigning.

Two fixes were landed in this pass (see "Changes landed"); the rest are
recommendations ordered by impact.

---

## Friction Point 1: Shared change-id ⇒ shared branch namespace ⇒ trunk corruption (CRITICAL — root cause of the contamination)

### What happened

`circuit_solver.delta` is a **linked git worktree of the single `circuit_solver`
repo** (`git rev-parse --git-common-dir` → `…/circuit_solver/.git`). So are
`.beta` and `.gamma`. All three lanes therefore share **one object store and one
branch-ref namespace**. And all three boards emit the **same change-id**, so
`plan.py` minted identical branch names for all of them:

```python
# plan.py (before)
branch = f"{change_id}/task-{task.number}"   # e.g. 2026-05-28-…/task-11
```

Result: `…/task-11` is a single ref that beta, gamma, and delta all write. Its
tip is a **2026-05-29 gamma-era** commit (`cad510fae…`, a `crates/digital-kernel`
workspace). Delta's task-11 implementer did its real work on a Hermes worktree
branch (`wt/t_*`), but delta's *integrator* — instructed to "merge the approved
worker branch for task #11" — resolved the **conventional** `…/task-11` ref and
merged **gamma's** work. That is how a root-level `crates/` tree entered delta's
`project/`-only trunk. The reflog confirms the cascade: `36d5389 → merge
task-20-impl → merge 946a1fa → merge task-21`.

### Root cause in scientia

Two coupled defects:
1. **Branch names were not board-namespaced** — `plan.py` keyed them on
   `change_id` alone, so concurrent lanes on a shared repo collide.
2. **The integrator reconstructed the branch by convention** instead of merging
   the exact branch/commit the implementer handed off — so even a unique branch
   wouldn't help if the integrator rebuilds the shared name.

### Fix (LANDED)

`src/scientia/hermes/plan.py`:
- The worker branch is now prefixed with the board slug when one is set:
  ```python
  board_prefix = f"{routing.board}/" if routing.board else ""
  branch = f"{board_prefix}{change_id}/task-{task.number}"
  ```
  e.g. `circuit-solver-delta/2026-05-28-…/task-11`. Each lane owns a disjoint
  ref space; `board=None` is unchanged (back-compat — verified against the
  golden fixture).
- `_instructions`/`compose_body` now thread the branch into the card bodies:
  - **impl/single:** "Commit your work to branch `<board/change-id/task-N>` … do
    NOT push to a bare `<change-id>/task-N` ref, which sibling boards sharing
    this repo also write to," and a Completion Criterion requiring the handoff to
    report the exact `branch` + final `commit` SHA.
  - **integrate:** "Merge the EXACT branch and commit SHA the implementer
    reported in its handoff (authoritative) — do NOT reconstruct a branch name by
    convention. … sibling boards in this repo also write `<change-id>/task-N`
    refs, so a reconstructed name can merge another board's work into this trunk."

### Emit-time guard (LANDED)

`scientia.hermes.preflight.repo_reality_check` (pure detection in
`validators.cross_lane_task_branches`) now probes the repo's branch refs and
detects when the same change-id already has task branches in a **sibling lane**
of the shared repo. It **errors** when no board is set (bare
`<change-id>/task-N` refs in a multi-lane repo are indistinguishable) and
**warns** when the board is set (namespaced refs are safe, but the integrator
must still merge the handed-off SHA). The emit SKILL runs it at step 7 and
refuses on the error. Probes are injectable, so the deterministic suite exercises
it with no git present.

---

## Friction Point 2: Integrator blocks instead of reassigning ⇒ conflict-resolver never runs (CRITICAL — pipeline dead-end)

### What happened

The conflict-resolver profile holds *all* the real merge discipline
(git-show-over-worktree reads, base-SHA/touches audit, escalation rubric — the
beta #2/#5/#8 fixes live there). On the live board it has **zero cards, ever.**

Task #11's integrate did the *right* merge-first work: it attempted
`git merge cad510fae…`, hit six genuine conflicts (all in shared docs/wiki/log
files), and aborted cleanly to restore trunk. Then its log shows only:

```
┊ 💬 kanban_comment …
┊ ⏸ kanban_block …
"Blocked the task with reason and reassigned to circuit-solver-delta-conflict-resolver"
```

There is **no reassign call.** The card's assignee stays `…-integrator`; it is
merely *blocked* with a reason that *claims* reassignment. The resolver never
sees it, and because it "looks handled," nothing surfaces it to a human.

### Root cause in scientia

The integrator SOUL said to "reassign conflicts to the conflict-resolver" but
never named the **mechanism** (which `kanban_*` verb changes `assignee`), so the
agent substituted `kanban_block` + a comment. Intent without mechanism, with no
post-condition check.

### Fix (LANDED, partial)

The integrate card body now spells out the mechanism and a post-condition:
"you MUST actually reassign it: change the card's assignee to `<resolver>` (a
board reassign event), not merely comment that you reassigned. After
reassigning, re-read the card and verify its assignee is `<resolver>`; otherwise
the resolver never sees it."

### Runtime detector (LANDED)

`scientia.hermes.status.detect_misrouted_reassignments(cards, resolver)` (pure)
flags any `blocked` card whose reason *claims* a reassignment to the resolver
but whose `assignee` was never changed to it — the exact dead-end above. The
`scientia-hermes-status` skill (step 8) builds a `LiveCard` per board card and
surfaces these as genuine escalations ("looks handled but is not"), naming the
integrator that still owns it. This is the runtime backstop for any conflict
that slips past the plan-side reassign demand.

### Still recommended (not landed)

- Mirror the mechanism+post-condition wording into the integrator profile's
  `SOUL.md` (generated by `scientia-hermes-init`), not only the card body, so it
  survives even if the card body is truncated.

---

## Friction Point 3: Component Map describes a skeleton that doesn't exist on trunk (CRITICAL — invalidates all prevention math)

### What happened

`design.md`'s Component Map declares ownership globs under `project/src/…`:

```
- netlist: project/src/netlist/**, project/tests/netlist/**
- numeric: project/src/numeric/**, …
```

But trunk `delta:project/` contained only `.gitignore`, `.gitkeep`,
`README.md` — there was no `src/` skeleton at all. Implementers, finding a blank
workspace, improvised a **different layout** (a top-level `crates/` workspace).
The #11 implementer's log shows it `ls project/src/ [exit 2]`, searched the
*wrong repo* (`circuit_solver.beta`), then built `crates/` from scratch.

Consequence: every `touches`, every wave, every contract is computed over paths
that **don't match where code actually lands**. The only files that ever collide
at merge are the shared docs/wiki/log files (Friction Point 4) — the code went
to undeclared locations the prevention machinery never modeled.

### Root cause in scientia

The Component Map is authored from the design narrative and never validated
against the repository it will execute in. `scientia-write-design` /
`scientia-generate-tasks` accept globs that don't resolve on `base_sha`.

### Fix (LANDED)

`scientia.hermes.preflight.repo_reality_check` (pure detection in
`validators.component_map_reality`) now reads the trunk tree at `base_sha` and
**warns** for every Component-Map owned-root that has no presence on trunk —
e.g. "component `netlist` owns `project/src/netlist` but no path under it exists
on trunk @ base_sha — workers will find a blank workspace and may improvise a
different layout." Warnings (not hard errors) because a greenfield change
legitimately scaffolds the whole tree; the emit SKILL step 7 surfaces them and
instructs scaffolding-or-fixing the map before proceeding.

### Still recommended (not landed)

- **Scaffold the workspace skeleton** as an epic/preamble card so implementers
  inherit the declared layout instead of improvising — turning the warning above
  into an automatic fix rather than an operator decision.

---

## Friction Point 4: Shared narrative files collide on every integrate (HIGH — systemic)

### What happened

Every worker writes `wiki/*` and `development/log.md`. Those paths are **not in
the Component Map**, so the wave planner never serializes them. The #11 conflict
was *exactly* this: all six conflicting files were `development/log.md`,
`wiki/log.md`, `wiki/index.md`, and four `wiki/concepts/*.md`. This will recur on
**every** task's integrate.

### Recommendation

Pick one: (a) forbid workers from editing the KG/dev-log and move those updates
to a single post-merge step; (b) declare them a shared serialized resource with a
ratification/wave like contracts; or (c) ship a `.gitattributes` union
merge-driver for append-only `log.md`/wiki files in the scaffold.

---

## Friction Point 5: Implementer green self-blocks (HIGH — recurred despite beta #3)

### What happened

Two of three running impl cards self-blocked with tests fully green (#1: 50/50,
#20: 34/34), e.g. `"review-required: … 50/50 tests pass … needs review before
merging."` The implementer SOUL *does* carry the beta #3 line ("Complete your
work card when tests pass; do not self-block"), yet the generic `kanban-worker`
skill's "block for review" guidance won — the log even says it blocked "as per
the kanban-worker skill guidance for code-changing tasks."

### Root cause

Beta #3 made completion a *recommendation* (SOUL sentence + status-skill
suggestion). A soft instruction loses to the base skill's default.

### Recommendation

Make it *enforcement*, not advice: a Hermes Stop-hook that auto-unblocks a card
whose block reason is `review-required` and whose verification metadata is green
(the operator independently proposed exactly this), or have
`scientia-hermes-status` *issue* the unblock rather than only recommending it.

---

## Friction Point 6: Hermes CLI/REST transport skew recurred; beta #4 fix is only cosmetic (HIGH — recurred)

### What happened

On Hermes v0.15.1 both stock transports are dead: REST `:8787` returns 401 with
no kanban API on 8787 *or* 9119, and the CLI uses `hermes kanban task create`,
which doesn't exist (verbs are `create`/`edit`/`assign`/… directly under
`kanban`). The operator hand-wrote a per-change emit shim **again**
(`proposals/.../hermes/emit.py`), wiring `--parent` atomically at create to close
a dispatch race.

### Root cause in scientia

Beta #4 was only PARTIAL: `apply._cli_transport` was patched to `hermes kanban
create`, but its docstring **falsely claims** it delegates to `render.to_cli`
while still hand-building argv inline; there is no `cli_version_probe`; and there
is no real-CLI integration test, so grammar drift is invisible.

### Recommendation

Actually route `_cli_transport` through `render.to_cli`; add a `hermes kanban
--help` version probe at preflight that selects the grammar and fails loudly on
mismatch; fold the proven shim (`create`/`link`/`archive`, `--parent`-at-create)
into the package; add one `skipif-no-hermes` integration test.

---

## Friction Point 7: Install/version skew — the running wheel lacks the machinery its SKILLs assume (HIGH — meta)

### What happened

The agent found the installed `scientia` (1.0.0) missing
`resolve_profile_prefix`, `prefixed_profile`, `gateway_check`,
`provision_profile.sh`, and the SOUL templates — all referenced by the SKILL.md
files. It hand-derived prefixes and **cloned gamma profiles** instead of
provisioning. The `d608e87` commit body itself flags the wheel as stale: fixes
present in `src/` (`task create`→`create`, `verify_touches`,
`touches_overlap_warnings`, …) were missing from the install.

This is corrosive to *every other finding*: a fix in `src/` that isn't installed
reads as "the fix didn't work."

### Fix (LANDED)

`README.md` install instructions now use **editable installs** (`pip install -e`)
for all three install paths, with a new "Keeping the package in sync (avoid
stale wheels)" section: the failure symptoms, a `--force-reinstall` recipe for
non-editable installs, a `python -c "import scientia; print(scientia.__file__)"`
check to confirm the runtime is on the repo and not a stale site-packages copy,
and a note to remove a leftover `build/` tree that can shadow `src/`.

### Still recommended (not landed)

- **Preflight package assertion:** `scientia-hermes-init`/`-emit` should assert
  package version ≥ required and that expected symbols/scripts exist, refusing
  with a "reinstall (`pip install -e .`)" message rather than letting the agent
  improvise. (The README claim was deliberately written to *not* assert this
  feature exists yet.)

---

## Friction Point 8: Config-location footgun (MEDIUM — new variant of beta #10, still unaddressed)

The package reads only `references/config.yaml`. The operator's
`development/config.yaml` edits were silently ignored (the file "worked" only
because it was byte-identical to defaults), and templates must *also* be mirrored
into `references/` or all nine generating stages break. Beta's recommended
`scientia config migrate` was never built. **Recommendation:** warn when a
`development/config.yaml` exists but isn't the read path; add a config/template
relocate-or-migrate helper; fall back to package-bundled templates when
`references/` holds only a config.

---

## Friction Point 9: Gateway port + board-unscoped dispatch (MEDIUM — recurred, partially mitigated)

`rest_base: 8787` serves nothing; the operator started a dashboard purely so the
preflight TCP probe goes green (it accepts a 401). The board-unscoped gateway
dispatcher (`dispatch_in_gateway: true`) dispatches *all* boards every 60s,
including unrelated `circuit-solver` todos, and could claim delta cards in the
wrong cwd (the gamma post-mortem bug) — avoided only by manual `/proc/<pid>/cwd`
checks. Beta #6 added port detection + a cwd warning (good), but preflight still
accepts an endpoint that can't serve the kanban API. **Recommendation:** verify
the endpoint serves *kanban* (not just any 200/401); escalate board-scoping to a
hard precondition for CLI-backend dispatch.

---

## Friction Point 10: Emit ledger frozen at `todo` (MEDIUM)

All 80 ledger entries read `last_status: "todo"` despite 3 done / 3 blocked / 4
archived live. The ledger is a fine idempotency record but actively misleading as
progress; `scientia-hermes-status` correctly reads `kanban.db` instead.
**Recommendation:** drop `last_status` from the ledger, or have status reconcile
and rewrite it.

---

## Friction Point 11: Worktree recycling + branch-naming divergence (MEDIUM — latent)

Workers pushed inconsistent refs (`wt/t_183511fc`, `task-20-impl`) that diverge
from the card's `task-N`; sibling boards share the object store so
recycled/prunable worktrees and stray `fix/double-commit-*`, `integrate-*`,
`merge-task-*` branches are visible. The git-show discipline that mitigates this
(beta #8) lives in the conflict-resolver SOUL — which never runs (FP2). Friction
Point 1's "report and merge the exact handoff branch/SHA" change addresses the
core of this; pinning the worker's output branch as a completion criterion (now
in the impl card body) closes the rest.

---

## Beta-recurrence scorecard

| Beta finding | Delta outcome |
|---|---|
| #1 incompatible git lineages / base_sha | **Superseded by FP1** — fresh emit fixed *bases*, but shared-namespace branches still merged the wrong lane's work |
| #2 wave caps not enforced | NEW-VARIANT — shared docs/wiki files un-wave-gated (FP4) |
| #3 implementer self-block when green | **RECURRED** (FP5) — soft fix lost to base skill |
| #4 CLI transport version skew | **RECURRED** (FP6) — beta fix cosmetic only |
| #5 touches vs reality | NOT-SEEN as a per-task mismatch (FP3 is the deeper cause) |
| #6 gateway port / board-unscoped dispatch | **RECURRED**, partially mitigated (FP9) |
| #7 integrator false-positive conflicts | NEW-VARIANT (FP2) — real conflict, but false *routing* |
| #8 worktree recycling | **RECURRED** (FP11) |
| #9 profile model binding | NOT-SEEN — bound, but via clone-from-gamma workaround (FP7) |
| #10 config migration | NEW-VARIANT (FP8) — location, not schema; still unaddressed |
| #11 undeclared contract duplication | NOT-SEEN — contracts ratified clean |

---

## Changes landed in this pass

| File | Change |
|---|---|
| `src/scientia/hermes/plan.py` | Board-namespace the worker branch (`{board}/{change_id}/task-N`); impl card reports exact branch+commit; integrate card merges the handed-off branch/SHA (not a reconstructed convention) and must verifiably reassign conflicts to the resolver. |
| `src/scientia/hermes/validators.py` | Pure detectors `cross_lane_task_branches` (FP1) and `component_map_reality` (FP3); also exported `touches_overlap_warnings` in `__all__`. |
| `src/scientia/hermes/preflight.py` | `repo_reality_check` — git-grounded gate running both detectors (injectable branch/tree probes; errors on bare emit into a multi-lane repo, warns otherwise; warns on absent Component-Map roots). |
| `scientia-hermes-emit/SKILL.md` | Step 7 now runs `repo_reality_check` and refuses on error. |
| `src/scientia/hermes/status.py` | New module: `detect_misrouted_reassignments` (FP2) + `LiveCard` — the runtime conflict-resolver dead-end detector. |
| `scientia-hermes-status/SKILL.md` | Step 8 runs the detector and surfaces dead-ends as escalations; decision rule + acceptance updated. |
| `tests/…` | 23 new tests across `test_hermes_validators.py`, `test_hermes_preflight.py`, `test_hermes_status.py`. |
| `tests/fixtures/hermes-plan.expected.json` | Regenerated golden `body_sha` for the intentional instruction change (board=None branch unchanged). |
| `README.md` | Editable-install (`pip install -e`) for all paths + "Keeping the package in sync (avoid stale wheels)" section. |

Suite after all changes: **178 passed**, only the 9 environmental `yaml`
failures/errors remain (pytest interpreter lacks pyyaml).

> **Live board:** this analysis was strictly read-only. Delta's trunk is already
> contaminated (FP1) and continuing dispatch would merge more sibling-board
> branches. Recovering the live `circuit_solver.delta` trunk is a structural
> decision for the operator (re-base the lane, archive the contaminated merges,
> or re-cut the board with namespaced branches) and is **out of scope** for these
> package fixes — the code changes above prevent the *next* run from recurring.

---

## Architectural principle extracted

Beta's principle was: *prevention machinery operates at declaration time, not
execution time.* Delta extends it in two directions:

1. **Validate declarations against reality, not just internal consistency.** A
   Component Map that owns a non-existent skeleton, or a branch name shared
   across lanes, passes every internal check and still corrupts trunk. Emit must
   reconcile its plan with the actual repo (`base_sha` tree, `git-common-dir`,
   sibling boards) before it writes a single card.
2. **Routing must be mechanism-level and post-condition-verified.** "Reassign to
   the resolver" and "merge the worker branch" are *intents*; the agent needs the
   exact tool/ref and a check that the intent took effect. An instruction whose
   success is never verified is indistinguishable from one that silently failed.

All three highest-leverage guards are now landed: the emit-time
shared-change-id/repo check (FP1) and the Component-Map-vs-trunk reality check
(FP3) convert delta's two silent corruptions into loud, early emit-time
failures, and the `scientia-hermes-status` mis-routed-reassignment detector (FP2)
catches a conflict-resolver dead-end on a live board. Together they make delta's
three invisible failures visible — two before any card is written, one on the
next status check. The remaining items (Friction Points 4–11) are quality-of-
life and robustness improvements ordered in the table above.
