# Friction F-7 (recurrence): Pipeline Review Deadlock

**Friction ID:** F-7 (self-block stalling — reviewer never dispatches)
**Source:** circuit-solver-epsilon board execution, 2026-06-01
**Severity:** Critical — deadlocks the entire impl→review→integrate pipeline
**Status:** Open (requires changes to scientia *and* hermes-agent)

---

## What happened

Four implementer workers on the epsilon board deadlocked the scientia pipeline
by blocking themselves "waiting for review" instead of completing their cards.
Their downstream reviewer cards — which auto-dispatch only on implementer
completion — remain stranded in `todo`. The implementers wait for reviewers
that can never arrive; the reviewers wait for implementers that never complete.

| Implementer (blocked) | Reviewer (stuck in `todo`) | Task |
|---|---|---|
| `t_073f337d` | `t_d0763290` | #1 Immutable CircuitGraph |
| `t_061aae38` | `t_ec231ddd` | #12 Delta-cycle settling |
| `t_9f85f416` | `t_4f0269ca` | #13 Checkpoint/restore |
| `t_f32188ff` (1st run) | `t_219474f4` | #20 Event model |

Task #20 escaped only because a human unblocked the implementer, causing the
dispatcher to respawn it. On the retry it completed properly and the reviewer
auto-dispatched — confirming the pipeline works correctly when the implementer
completes.

F-7 was previously identified in the beta friction analysis and addressed by
adding "Do NOT self-block for review" to the implementer profile and card
body. That fix was necessary but insufficient: three workers on epsilon still
blocked for review, each explicitly citing the *generic* kanban-worker skill
as their authority for doing so.

## Why it recurred

Three instruction sources are active simultaneously in every scientia
implementer's system prompt, and two of them contradict the third:

### Source 1: `KANBAN_GUIDANCE` (hermes-agent `prompt_builder.py`)

Injected into every kanban worker's system prompt. Lifecycle step 5 contains
an unconditional exception:

> *"Exception: if your output is a code change that needs human review before
> counting as merged/done (**most coding tasks**), drop the structured metadata
> into a `kanban_comment` first, then end with
> `kanban_block(reason="review-required: <one-line summary>")` so a reviewer
> can approve+unblock or request changes. Reviewing-then-completing is more
> honest than auto-completing work that still needs eyes on it."*

No pipeline-awareness qualifier. The parenthetical "(most coding tasks)"
covers every implementer.

### Source 2: `kanban-worker` skill (hermes-agent `skills/devops/kanban-worker/SKILL.md`)

Auto-loaded via `--skills kanban-worker` for every dispatched worker. Even more
explicit:

> *"For most code-changing tasks, the work isn't truly done until a human
> reviewer has eyes on it. **Block instead of complete**, with `reason`
> prefixed `review-required:` so the dashboard surfaces the row as needing
> review."*

Provides a copy-paste code example calling `kanban_block`. Then narrows
`kanban_complete` to exceptional cases:

> *"Use `kanban_complete` only when the task is genuinely terminal — e.g. a
> one-line typo fix, a docs change with no functional consequences, or a
> research task where the artifact IS the writeup itself."*

### Source 3: Scientia implementer profile (soul-implementer.md.tmpl) + card body

The profile says:

> *"You never self-block for review — the pipeline has a dedicated reviewer
> stage next in the chain."*

And the Completion Criteria in every emitted card body (plan.py) says:

> *"Do NOT self-block for review — the next card in this pipeline is a
> dedicated reviewer."*

### Why Source 3 loses the attention contest

1. **Specificity gap.** Sources 1 and 2 give a multi-paragraph pattern with a
   concrete code example. Source 3 gives a one-line prohibition with no
   example of the *correct* action (`kanban_complete`).
2. **Prompt ordering.** `KANBAN_GUIDANCE` and the `kanban-worker` skill appear
   in the stable tier *before* the profile SOUL.md. The model has already
   committed to the "block for review" pattern before it encounters the
   override.
3. **No conditional in the generic sources.** They frame `review-required` as
   universal — "most coding tasks." The profile override reads as a soft
   preference rather than a hard contradiction because the model has no way
   to know the generic rule was only meant for boards without a downstream
   reviewer.

### Worker traces confirm the causal chain

Every blocked implementer explicitly cited the generic guidance:

- **t_061aae38**: *"Now post the review-required comment and block for review,
  **as per the kanban-worker skill guidance for code-changing tasks**"*
- **t_073f337d**: *"Now let me add the review-required comment and block for
  review, **per the kanban-worker skill guidance for code-changing tasks**"*
- **t_9f85f416**: *"All done. Let me drop the review-required handoff as a
  comment and block for review"*
- **t_f32188ff** (1st run): *"All done. Now post the review-required handoff
  comment and block for review"*

## Proposed fix

The fix requires coordinated changes to **two packages** (hermes-agent and
scientia) because the contradictory instructions originate from both.

### A. hermes-agent: `KANBAN_GUIDANCE` (prompt_builder.py)

Replace the unconditional "review-required" exception in lifecycle step 5 with
a pipeline-aware conditional. The pipeline case must be the **first** branch so
the model encounters it before the generic fallback:

```python
# BEFORE (current — unconditional):
"Exception: if your output is a code change that needs human review "
"before counting as merged/done (most coding tasks), drop the "
"structured metadata (changed_files / tests_run / diff_path) into a "
"`kanban_comment` first, then end with "
"`kanban_block(reason=\"review-required: <one-line summary>\")` so a "
"reviewer can approve+unblock or request changes. Reviewing-then-"
"completing is more honest than auto-completing work that still needs "
"eyes on it.\n"

# AFTER (pipeline-aware conditional):
"If your task body or Completion Criteria explicitly says "
"\"Do NOT self-block for review\" (you are in a pipeline with a "
"dedicated downstream reviewer), call "
"`kanban_complete(summary=..., metadata=...)`. The reviewer card "
"auto-dispatches on your completion — blocking here deadlocks the "
"pipeline. Flag design concerns in `residual_risk`, not a block "
"reason.\n"
"Otherwise, if your output is a code change that needs human review "
"before counting as merged/done (most coding tasks on boards without "
"a downstream reviewer), drop the structured metadata into a "
"`kanban_comment` first, then end with "
"`kanban_block(reason=\"review-required: <one-line summary>\")` so a "
"human reviewer can approve+unblock or request changes.\n"
"If the task is genuinely terminal (one-line typo, docs-only change, "
"research writeup), `kanban_complete(summary=..., metadata=...)` "
"directly.\n"
```

### B. hermes-agent: `kanban-worker` skill (SKILL.md)

Add a **Pipeline-aware completion** subsection immediately **before** the
existing **Coding task that needs human review (review-required)** subsection.
Placement before — not after — is critical because LLMs weight earlier
instructions more heavily when two sections cover the same decision point.

```markdown
**Coding task in a pipeline with a dedicated reviewer (pipeline-complete):**

When your task card body or Completion Criteria explicitly says
"Do NOT self-block for review" (scientia impl→review→integrate pipeline),
you MUST `kanban_complete` — never `kanban_block` for review. The
pipeline dispatches the reviewer automatically when you complete;
blocking instead deadlocks the pipeline because the reviewer card
never leaves `todo`.

```python
kanban_complete(
    summary="shipped delta-cycle settling — 35/35 tests pass, clippy clean",
    metadata={
        "changed_files": ["project/src/digital/settle.rs"],
        "verification": "cargo test && cargo clippy",
        "branch_head": "c305fff",
        "residual_risk": "batch-update semantics choice needs reviewer eyes",
    },
)
```

Note the `residual_risk` field: this is how you flag design decisions that
need reviewer attention **without blocking**. The reviewer reads your
handoff metadata, including `residual_risk`, when their card dispatches.

**Coding task that needs human review (review-required):**

*Only for boards that lack a downstream reviewer card.* For most
code-changing tasks on such boards, the work isn't truly done until a
human reviewer has eyes on it. Block instead of complete [... rest of
existing section unchanged ...]
```

### C. scientia: Implementer SOUL template (soul-implementer.md.tmpl)

Strengthen the "do NOT block" instruction from a one-line note to a framed
override that explicitly names and contradicts the generic sources. The model
must recognize this as a direct substitution, not a soft suggestion:

```markdown
## CRITICAL: Complete, do NOT block for review

The generic `kanban-worker` skill and `KANBAN_GUIDANCE` lifecycle both
recommend `kanban_block(reason="review-required: ...")` for "most coding
tasks." That guidance applies to boards **without a downstream reviewer
stage**. This pipeline has a dedicated reviewer card that auto-dispatches
when you `kanban_complete`. Blocking instead of completing **deadlocks
the pipeline**: your reviewer card stays in `todo` waiting for you to
complete, while you are blocked waiting for a reviewer that never
arrives.

**Always `kanban_complete(summary=..., metadata=...)` when your work
passes the Completion Criteria.** Flag design concerns in
`residual_risk`, not in a block reason.
```

This replaces the current two-line note:

```markdown
Do NOT self-block for review — the next card in this pipeline is a dedicated
reviewer. If you have a design concern, note it in the handoff `residual_risk`
field and complete anyway.
```

### D. scientia: Reviewer SOUL template (soul-reviewer.md.tmpl)

Same treatment — strengthen the existing "complete, never block" instruction
to name and contradict the generic sources:

```markdown
## CRITICAL: Return your verdict by completing, never by blocking

The generic `kanban-worker` skill recommends blocking for review; that
does not apply to you. There is no automatic re-dispatch from a
reviewer-blocked card — a block stalls the pipeline permanently (friction
F-7). Instead, always return your verdict via `kanban_complete`:

- Approve → `kanban_complete(summary="<what you verified>")`.
- Reject → `kanban_complete(summary="REJECTED: <reason>",
  metadata={"verdict": "rejected"})`.
```

This replaces the current paragraph:

```markdown
Do NOT call `kanban_block()`. There is no automatic re-dispatch from a
reviewer-blocked card, so a block stalls the pipeline permanently; a
completion carrying a `REJECTED:` summary lets the integrator and
conflict-resolver stages handle the downstream failure (friction F-7).
```

### E. scientia: Card body emission (plan.py)

The Completion Criteria already includes the "Do NOT self-block" line. Add a
second reinforcing line that uses the CRITICAL framing and mentions the
deadlock consequence explicitly:

```python
# In the impl-stage branch of _card_instructions():
base += (
    "\n\n## Completion Criteria\n"
    "Complete (do NOT block for review) when ALL of:\n"
    "- Every spec scenario traced above has a passing test\n"
    "- `cargo test` passes (or the verification command in the handoff)\n"
    "- `cargo clippy` passes with no warnings\n"
    "- All edits are within the declared touches paths\n"
    f"{commit_line}"
    "\n"
    "CRITICAL: You MUST `kanban_complete`, not `kanban_block`. This "
    "pipeline has a dedicated reviewer card that auto-dispatches on "
    "your completion. Blocking for review deadlocks the pipeline — "
    "the reviewer waits for you to complete while you wait for a "
    "reviewer that never arrives. Flag design concerns in "
    "`residual_risk`, not in a block reason.\n"
)
```

## Files to change

| Package | File | Change |
|---|---|---|
| hermes-agent | `agent/prompt_builder.py` (KANBAN_GUIDANCE) | Pipeline-first conditional in lifecycle step 5 |
| hermes-agent | `skills/devops/kanban-worker/SKILL.md` | Add pipeline-complete subsection before review-required |
| scientia | `src/scientia/references/soul-implementer.md.tmpl` | Replace 2-line note with CRITICAL override paragraph |
| scientia | `src/scientia/references/soul-reviewer.md.tmpl` | Replace "complete, never block" paragraph with CRITICAL override |
| scientia | `src/scientia/hermes/plan.py` | Add CRITICAL deadlock-warning line to Completion Criteria |

No schema changes. No dispatcher logic changes. No new config keys.

## Design rationale

### Why "pipeline-first" ordering instead of just strengthening the profile

The beta friction analysis tried the "just strengthen the profile" approach.
It didn't hold because the generic sources are structurally more prominent in
the prompt. Strengthening the profile alone creates an arms race: the model
has to resolve a contradiction between two sources of similar authority, and
the more detailed, example-carrying source wins regardless of how bold the
override's font is.

The pipeline-first conditional in the generic sources is a different strategy:
it **removes the contradiction** rather than trying to overpower it. The model
no longer has to choose between two contradictory instructions — the generic
rule itself says "if you're in a pipeline, complete; otherwise, block." The
profile override then serves as confirmation rather than contradiction.

### Why a text signal ("Do NOT self-block for review") rather than a task metadata field

A `pipeline_mode: impl-review-integrate` column on the task row would be
cleaner than inferring from the card body text. But:

1. It requires a schema migration in `kanban_db.py`, an emitter change in
   `plan.py`, and a dispatcher change to expose the field in
   `kanban_show()` output.
2. The text signal already exists (every emitted card says "Do NOT self-block
   for review") and is visible in `kanban_show()` output. Adding a metadata
   field would be redundant with the text that's already there.
3. The text signal is deployable immediately with no coordination cost.

A metadata field is worth considering for a v2, but the text-signal approach
fixes the deadlock now.

### Why not auto-detect and override `kanban_block` on implementer cards

The dispatcher could detect that a reviewer card is downstream and
automatically convert the implementer's `kanban_block` to a `kanban_complete`.
But a block might be for a *genuine* reason (missing credentials, prerequisite
absent, scope contradiction), and silently converting it to a completion would
be semantically wrong and dangerous. The correct fix is to prevent the
erroneous block, not to patch it after the fact.

## Validation plan

1. **Unit** — after amending `KANBAN_GUIDANCE`, search the assembled system
   prompt for "review-required" and confirm it is now gated behind "boards
   without a downstream reviewer."
2. **Integration** — unblock the three stuck epsilon implementers
   (`t_073f337d`, `t_061aae38`, `t_9f85f416`) and verify that on retry they
   `kanban_complete` and their reviewer cards auto-dispatch.
3. **Regression** — on a non-pipeline board (a plain `kanban-worker` board
   without downstream reviewer cards), verify that the `review-required`
   pattern still works — a code-changing task blocks for human review as
   before.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Remove `review-required` from the generic skill entirely | Breaks non-pipeline boards that rely on the pattern for human gatekeeping |
| Dispatcher auto-converts implementer `kanban_block` to `kanban_complete` | Silent semantic corruption of genuine blocks (missing credentials, etc.) |
| Make reviewer dispatch independent of implementer completion | Breaks the impl→review ordering guarantee; reviewer would read incomplete implementation |
| Add a `pipeline_mode` metadata field to task rows | Clean but requires schema migration; the text signal already exists and is deployable immediately |
