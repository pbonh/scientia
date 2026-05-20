# 03 — Multi-tenant parallel: `billing` + `identity`

**Audience.** An engineering manager coordinating two squads whose
bounded contexts overlap. The goal is to ship two changes in parallel
without stepping on each other.

**Setting.** Same repo as [02 — End-to-end single change](02-end-to-end-single-change.md),
one quarter later. Two changes are starting on the same day:

- **Squad A — billing.** `billing/2026-08-13-tax-rates`: regional
  sales tax on subscription line items.
- **Squad B — identity.** `identity/2026-08-13-step-up-auth`:
  step-up authentication for high-risk actions, including (as it
  happens) refunds.

These two changes will both touch the *settlement* concept — billing
defines it as "money has moved at the processor"; identity defines
*settlement* as a session-attestation state. This is the classic
**false-cognate** scenario the wiki already flags in
`wiki/context-maps/billing-to-identity.md`.

Concurrency rule (from scientia): **one in-flight change per
bounded-context tenant, full parallelism across tenants.** Two
tenants ⇒ this is fine.

## Phase 1 — Two grills, in parallel

Both leads activate the orchestrator independently.

### 1.1 — Lia (billing) starts

```
> "Use the scientia skill. I want to start billing/2026-08-13-tax-rates:
   apply regional sales-tax rates to subscription line items at invoice
   issuance. Out of scope: tax filing, exemptions, B2B reverse-charge."
```

The orchestrator runs `state_detect.py`. Output (relevant slice):

```json
{
  "tenants": {
    "billing":  { "active_change": null,                "stage": "absent" },
    "identity": { "active_change": null,                "stage": "absent" }
  }
}
```

Both tenants idle. Single-in-flight-per-tenant gate passes.
Recommended next: `scientia-wiki-grill` against billing.

The billing grill walks the in-scope subset of the wiki. It surfaces
three gaps and one cross-context risk:

- Glossary missing *tax rate*, *tax region*, *taxable amount*. Lia
  fills these in via grill.
- `[[concepts/invoice]]` has no `## Risks & Pitfalls` entry about
  rounding. The grill recommends one; Lia accepts.
- The `## False Cognates with Adjacent Contexts` of
  `wiki/contexts/billing.md` already lists *settlement* as a
  false-cognate with identity. The grill **surfaces** this to Lia
  even though the new change does not name *settlement* — the
  reasoning is that "tax computed at issuance time" is adjacent to
  "settlement timing". Lia confirms tax is computed at *issuance*,
  not settlement; no contamination risk.

Grill ends: 3 pages touched, 0 open questions parked. Ready for
`scientia-wiki-bind`.

### 1.2 — Devon (identity) starts (concurrently)

In a separate working tree (same git repo, different worktree —
scientia operates on absolute paths), Devon runs:

```
> "Use the scientia skill. I want to start identity/2026-08-13-step-up-auth:
   require a step-up auth challenge before high-risk actions, including
   refunds initiated by support agents and any account-recovery flow.
   Out of scope: passkey-only paths and machine-to-machine tokens."
```

Orchestrator state-detect from Devon's worktree (relevant slice):

```json
{
  "tenants": {
    "billing":  { "active_change": null, "stage": "absent" },
    "identity": { "active_change": null, "stage": "absent" }
  }
}
```

Same input, same output. The state is on disk; both worktrees see
it identically. Recommended next: `scientia-wiki-grill` against
identity.

The identity grill surfaces:

- The identity ubiquitous-language glossary lacks *step-up*,
  *attestation*, *risk action*. Devon fills these in.
- `[[concepts/session]]` has confidence `medium`; the grill asks one
  question to raise to `high`.
- The grill *also* surfaces the *settlement* false-cognate, and
  asks whether the change introduces or alters this term. Devon
  answers: no — the change uses *attestation state*, not
  *settlement*. The grill notes this and links the context-map
  entry to remind the spec author.

Both grills are complete. The wiki state is now richer for both
tenants. The grills did not deadlock or conflict because each only
edited pages inside or adjacent to its own context, and the
*settlement* false-cognate was already documented — neither change
attempted to redefine it.

### 1.3 — Coordinating commits

Both leads need to commit wiki edits before binding. They do this
serially (the wiki is one shared directory):

```bash
# In Lia's worktree
$ git pull --rebase
$ git add wiki/
$ git commit -q -m "wiki: grill billing/tax-rates"
$ git push

# In Devon's worktree, before binding:
$ git pull --rebase
# (Lia's edits land cleanly — they touched only billing-side pages)
$ git add wiki/
$ git commit -q -m "wiki: grill identity/step-up-auth"
$ git push
```

If a wiki edit *did* conflict (e.g., both grills tried to edit
`wiki/context-maps/billing-to-identity.md`), git would surface the
conflict and the two leads resolve it before binding. The scientia
gates do not eliminate human-coordination on shared wiki pages —
they only enforce one in-flight *change* per tenant.

## Phase 1.4 — Lint and bind, in parallel

Both leads now lint and bind. Lint is read-only and parallel-safe.
Binds are per-tenant and parallel-safe (different manifest
directories, different snapshot pins).

```
[Lia]  > "Lint."
[Devon] > "Lint."
```

Both clean.

```
[Lia]  > "Bind billing/2026-08-13-tax-rates."
[Devon] > "Bind identity/2026-08-13-step-up-auth."
```

`development/manifests/billing/2026-08-13-tax-rates/core.md` and
`development/manifests/identity/2026-08-13-step-up-auth/core.md`
are written. Their `wiki_snapshot:` pins differ (Devon's bind ran
later, against a slightly newer HEAD), which is fine — both
snapshots are within the wiki's git history and the gate is *"the
pin resolves"*, not *"the pins are equal."*

`development/log.md` after both binds:

```markdown
- 2026-08-13T11:02:14Z — scientia-wiki-bind — manifest-bound — billing/2026-08-13-tax-rates — wiki_snapshot=44a1b7c
- 2026-08-13T11:09:51Z — scientia-wiki-bind — manifest-bound — identity/2026-08-13-step-up-auth — wiki_snapshot=2c8e0f3
```

The orchestrator now reports two active tenants when asked:

```
> "Status."

scientia (orchestrator):
  Multiple in-flight tenants:
    1) billing  — change billing/2026-08-13-tax-rates  — stage: bound
    2) identity — change identity/2026-08-13-step-up-auth — stage: bound

  recommended next per tenant:
    billing:  scientia-intent-proposal
    identity: scientia-intent-proposal

  Which tenant do you want to advance?
```

The orchestrator's policy is *"never advance two tenants in the
same turn — sequential delegation only."* The two squads operate
in their own worktrees and converse with their own orchestrator
sessions; from any single session's perspective, one tenant
advances per turn.

## Phase 2 — Two intent pipelines, in parallel

Each squad walks the OpenSpec stage sequence independently:

```
                   billing                          identity
                   ────────                         ────────
proposal           Lia                              Devon
spec               Lia                              Devon
design             Lia                              Devon
adr                Lia (1 ADR — tax id scheme)      Devon (2 ADRs — challenge UX, attestation TTL)
tasks              Lia                              Devon
verify             Lia                              Devon
```

The two pipelines do not contend except at the wiki-living-doc
mirrors (`wiki/specs/<capability>.md`). The spec stage writes
those:

- `wiki/specs/tax-rates.md` (billing)
- `wiki/specs/step-up-auth.md` (identity)

Different files; no contention. The mirrors land via separate
commits on the shared trunk, with both leads pulling --rebase
before each commit.

### 2.1 — Where they brush against each other: the false-cognate

Identity's `design.md` mentions that step-up will be triggered by
support-agent-initiated refunds. The design must reconcile with the
billing context's *Refund* concept. The design stage's
**in-force ADR walk** picks up:

- `ADR-0004 — refund id scheme` (billing, accepted; archived from
  the prior change).
- The identity squad's design honors it: step-up does not change
  refund ids, only gates refund issuance behind a fresh
  attestation.

Identity's `design.md` records this explicitly under
`## In-Force ADR Treatment`:

```markdown
## In-Force ADR Treatment
- **ADR-0004 — refund id scheme** (billing, accepted) — *Honored.*
  Step-up runs before the refund command is dispatched; refund id
  generation is untouched.
- **ADR-0001 — subscription state machine** (billing, accepted) —
  *Not Applicable.* No subscription state transition involved.
- ...
```

If identity's design had instead changed the refund id scheme, the
right answer would be to supersede ADR-0004 with a new
identity-side ADR (using `## Supersedes: ADR-0004`) — the
`scientia-intent-design` skill refuses to silently override.

### 2.2 — Verify, in parallel

Each squad runs verify against their own change. Different
artifacts, different reports:

- `openspec/changes/billing-2026-08-13-tax-rates/verify-20260813T144501Z.md`
- `openspec/changes/identity-2026-08-13-step-up-auth/verify-20260813T150214Z.md`

Both come back `worst_severity: suggestion`. Ready to emit.

## Phase 3 — Two emits, two boards (one db)

### 3.1 — Kanban tenant scoping

Both squads emit on the same `kanban.db`. The Hermes CLI scopes by
`--tenant`:

```bash
$ hermes kanban list --tenant billing --json
$ hermes kanban list --tenant identity --json
```

`scientia-kanban-emit` always passes `--tenant <bounded-context>`
on every `hermes kanban create`. There is no cross-tenant ambiguity.

### 3.2 — Lia emits

`billing/2026-08-13-tax-rates` has one capability (`tax-rates`)
and 3 scenarios. ADR-0006 (tax-id scheme) is `accepted` →
**P2 pipeline**.

```bash
$ hermes kanban create \
    --id t_taxratesA_impl \
    --tenant billing \
    --assignee scientia-implementer \
    --workspace git:/home/lia/work/billing-platform \
    --skill scientia-kanban-worker \
    --skill scientia-grill \
    --title "Tax rates — issuance-time computation (impl)" \
    --body-file /tmp/scientia-emit-XXXX.md
# ... 9 more (3 scenarios × 3 stages + 1 aggregator)
```

Total tasks: 10.

### 3.3 — Devon emits (note the pattern shift)

`identity/2026-08-13-step-up-auth` has one capability (`step-up-auth`)
and 5 scenarios. **ADR-0007 (challenge UX) is `proposed`** — the
team agreed to ship the change with a 30-day-review status on the
UX choice, with the reviewer/aggregator pattern requiring an
explicit human-in-loop sign-off.

ADR status `proposed` → **P5 human-in-loop** pattern. Every
aggregator task is created with `--require-approval`:

```bash
$ hermes kanban create \
    --idempotency-key step-up:ADR-0007:HASH:aggregator \
    --tenant identity \
    --assignee scientia-aggregator \
    --workspace dir:/home/devon/work/identity-platform \
    --parent t_stepupA_integrate \
    --parent t_stepupB_integrate \
    --parent t_stepupC_integrate \
    --parent t_stepupD_integrate \
    --parent t_stepupE_integrate \
    --skill scientia-kanban-worker \
    --triage \
    --body "$(cat /tmp/scientia-emit-XXXX.md)" \
    "Step-up auth — aggregator (human-in-loop)"
```

The `--triage` flag parks the task for human approval before it can
mark the spec as
shipped. This is the P5 difference from the billing emit.

Total tasks: 16 (5 × 3 + 1 aggregator).

### 3.4 — Combined status

The orchestrator (in either squad's session) sees both:

```
> "Status --all"

scientia-kanban-status --all:

## billing/2026-08-13-tax-rates — Pattern: P2 pipeline (10 tasks)
  impl:      done(3)
  review:    done(2), running(1)
  integrate: pending(3)
  aggregator: waiting

## identity/2026-08-13-step-up-auth — Pattern: P5 human-in-loop (16 tasks)
  impl:      done(2), running(2), blocked(1)
  review:    pending(5)
  integrate: pending(5)
  aggregator: waiting (--require-approval)

Blocked tasks:
  - identity / t_stepupC_impl — "ambiguous risk-action enumeration; is
    `change-of-mfa-device` itself a risk action?" → Devon needs to
    resolve.

Idempotency drift: none.
```

Devon resolves the blocked task by extending the spec's
`## Acceptance Criteria` to enumerate explicitly, re-running verify
(still `suggestion`), and re-emitting. Re-emit produces new child
keys for the one scenario whose body changed; the other 14 tasks
are untouched.

## Phase 4 — Two ingests, atomic per change

### 4.1 — Lia: billing ingests first

Eventually all 10 billing tasks complete. Lia runs:

```
> "Ingest evidence."
> "Synthesize."
```

`wiki/syntheses/billing-2026-08-13-tax-rates.md` is created with
status `proposed`. Lia reviews the four proposed edits, applies
them to the named wiki pages (no double-counting; the synthesis
only proposes, the human applies), sets status to `applied`, and:

```
> "Archive."
```

Preflight ✓ ✓ ✓ ✓. Dry-run shown. Confirm:

```
> "archive billing/2026-08-13-tax-rates"
```

Execution: 10 `hermes kanban archive` calls, one `openspec archive`,
wiki/manifest/task index finalizations.

`development/log.md`:

```markdown
- 2026-08-19T16:21:08Z — scientia-ingest-archive — archived — billing/2026-08-13-tax-rates — atomic=ok
```

Billing tenant is idle again.

### 4.2 — Devon: identity ingests after human approval

Identity's aggregator is gated by `--require-approval`. The
reviewer flagged one residual risk (TTL on attestation cache),
which Devon promotes to a **deferred follow-up** in the synthesis.
The aggregator approver (the identity-owning eng) approves; the
aggregator marks `done`.

```
> "Ingest evidence."
> "Synthesize."
```

`wiki/syntheses/identity-2026-08-13-step-up-auth.md` proposes:

- Extend `[[concepts/session]]`'s `## Risks & Pitfalls` (TTL
  question).
- Add new concept `[[concepts/risk-action]]`.
- Extend `[[contexts/identity]]`'s ubiquitous-language glossary.
- Note a **deferred follow-up**: ADR-0007 status remains `proposed`;
  a future change should promote to `accepted` after 30 days of
  field data.

Devon applies the proposed edits manually, sets synthesis status to
`applied`, and archives.

### 4.3 — Both tenants idle

```
> "Status --all"

scientia-kanban-status --all:
  billing  — idle (last archive: billing/2026-08-13-tax-rates)
  identity — idle (last archive: identity/2026-08-13-step-up-auth)

  recommended next: name a new change on either tenant
```

## CI gate (single command, both tenants)

While both changes were in flight, the repo's CI ran
`skills/scientia/scripts/verify_all.py` on every push:

```yaml
# .github/workflows/scientia.yml
jobs:
  scientia-verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ~/.agents/skills/scientia/skills/scientia/scripts/verify_all.py
```

`verify_all.py` walks **all** in-flight manifests, runs
`scientia-wiki-lint` + per-change `openspec verify` + idempotency-key
drift check + git preflights, aggregates findings by severity, and
exits non-zero per the configured threshold. The cross-tenant nature
is transparent: one script, two changes inspected, one aggregated
report.

Sample output mid-pipeline (both changes emitted, billing in
review, identity blocked):

```
scientia verify-all — 2026-08-15T09:12:04Z

Tenants in flight: 2
  billing   change=2026-08-13-tax-rates       stage=emitted
  identity  change=2026-08-13-step-up-auth    stage=emitted

Wiki lint:         clean
OpenSpec verify:
  billing/2026-08-13-tax-rates       — suggestion (3)
  identity/2026-08-13-step-up-auth   — suggestion (5)
Idempotency drift: none
Git preflights:    spec-on-trunk ✓ ✓

Worst severity: suggestion (below block threshold)
Exit: 0
```

Two days later, when Devon re-emits after the blocked-task fix, the
CI run on the same script catches the moment the old child keys are
closed and new ones written. No false alarms; idempotency drift is
expected during a re-emit and is logged, not flagged as critical.

## Artifacts produced (cross-tenant view)

```
wiki/
  concepts/tax-rate.md, tax-region.md, taxable-amount.md       (billing-side, new)
  concepts/step-up-attestation.md, risk-action.md              (identity-side, new)
  contexts/billing.md, contexts/identity.md                    (both edited; glossaries grew)
  context-maps/billing-to-identity.md                          (annotated for the false-cognate)
  specs/tax-rates.md                                           (billing mirror)
  specs/step-up-auth.md                                        (identity mirror)
  syntheses/billing-2026-08-13-tax-rates.md                    (status: archived)
  syntheses/identity-2026-08-13-step-up-auth.md                (status: archived)

development/
  manifests/billing/archive/2026-08-13-tax-rates/
  manifests/identity/archive/2026-08-13-step-up-auth/
  tasks/billing/archive/2026-08-13-tax-rates/      (10 task index files)
  tasks/identity/archive/2026-08-13-step-up-auth/  (16 task index files)
  log.md                                            (appended throughout)

openspec/
  archive/billing-2026-08-13-tax-rates/
  archive/identity-2026-08-13-step-up-auth/
```

## Recovery scenarios

**Both squads try to write the same wiki page.** Git's merge
conflict surfaces it. Resolve before lint; the conflict is human
work, not scientia work.

**A third squad tries to start a *second* `billing` change while
the first is in flight.** `scientia-intent-proposal`'s
single-in-flight-per-tenant gate refuses:

```
scientia-intent-proposal:
  REFUSED — billing already has an in-flight change
  (billing/2026-08-13-tax-rates, stage=design).
  Wait for archive, or supersede the existing change.
```

The third squad either waits or works on a different tenant.

**The false-cognate bites later.** Suppose identity *had* tried to
redefine *settlement*. Two places catch it:

1. `scientia-intent-spec` would inline the identity-side glossary;
   the term would resolve from the identity manifest's slice 4. So
   far so good — *inside* identity, settlement means session
   attestation.
2. `scientia-intent-verify`'s Correctness check would flag a wiki-
   link or `@spec:` reference that *crossed* into billing using
   *settlement* — because the billing spec's inlined glossary
   defines settlement differently. The two would diverge at the
   point of cross-reference, which is exactly where the bug would
   bite at runtime.

If neither bite, the bite happens at integration time and the
relevant `scientia-ingest-evidence` handoff records the residual
risk; `scientia-ingest-synthesize` then proposes adding it to the
context map's `## False Cognates` table. The wiki gets smarter for
the next change.

**One squad wants to archive but the other's worker branch hasn't
merged.** Each archive is per-change, not per-tenant; billing's
`git:worker-branch-merged` gate checks billing's task branches
only. Identity's open branches do not affect billing's archive.

**Bundle upgrade mid-flight.** `scientia_schema_version` lives in
`development/config.yaml`. In-flight changes keep their pinned
schema (via each `core.md`'s `scientia_schema:` field) until they
archive. New changes adopt the new schema. The orchestrator's
`scientia_schema_version_repo > scientia_schema_version_bundle`
case surfaces a "downgrade or upgrade the bundle" message; it does
not corrupt in-flight state.
