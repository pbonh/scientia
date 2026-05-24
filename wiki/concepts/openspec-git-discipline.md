---
title: "OpenSpec Git Discipline"
type: concept
tags: [concept, openspec, git, workflow, process]
created: 2026-05-23
updated: 2026-05-23
sources: ["raw/intent-driven-template/skills.md"]
confidence: high
---

## Definition

**OpenSpec git discipline** is a set of rules governing when OpenSpec lifecycle
phases may run relative to git state. Its core rule is simple: **every OpenSpec
state change must cross `main` before the next lifecycle phase depends on it.** It
is shipped as a skill in the [[entities/intent-driven-template]] and exists to keep
an [[entities/openspec|OpenSpec]] change's artifacts and git history coherent so
that "apply" and "archive" never act on a change that only exists on a branch or
worktree.

## How It Works

The discipline maps each phase of the
[[concepts/intent-driven-schema|proposal→specs→design→adr→tasks]] lifecycle to a
git gate:

- **Propose / continue** — artifacts may be *drafted* on a branch, but must be
  committed and merged to `main` before apply starts.
- **Apply** — may run on `main`, a branch, or a worktree **only if that exact
  proposal change is already available on `main`.**
- **Archive** — may run **only from `main`, after implementation is merged back**.
- Never create commits, branches, or merges unless the user explicitly asks.

Concrete checks back the rule. **Before apply:** run `git status --short`; verify
`openspec/changes/<change>/` has no uncommitted proposal files; verify the proposal
change exists on `main`. **Before archive:** run `git branch --show-current` and
`git status --short`; stop if not on `main`; stop if implementation work has not
been merged back. When a gate fails the agent pauses, explains the boundary, and
asks the user to make the git state explicit rather than proceeding.

## Key Parameters

| Moment | Gate |
|--------|------|
| Before propose | Prefer `main`; warn and ask if not |
| During continue | Ask to commit the completed artifact before the next one |
| After propose | Ask to commit proposal artifacts; offer a PR branch |
| Before apply | Confirm the proposal is committed on `main` |
| Before archive | Require `main` + implementation merged back |
| After archive | Ask to commit archive/spec-sync changes |

## When To Use

- Running any OpenSpec propose / continue / apply / verify / archive flow,
  especially across branches or git worktrees.
- Pairing with [[concepts/intent-driven-schema|intent-driven]] (or any
  [[concepts/custom-workflow-schema|custom schema]]) execution where artifact
  timing affects git history.

## Risks & Pitfalls

- **Worktree visibility ≠ reached `main`** — a proposal visible in a worktree has
  not necessarily crossed `main`; treating it as such is the canonical red flag.
- **Applying a branch-only proposal** — apply must start only after the proposal
  state is on `main`.
- **Archiving from a feature branch or before merge** — verification makes a change
  *eligible* to merge; it does not replace the merge.
- **Silent git mutations** — auto-committing, branching, or merging without
  explicit user approval violates the discipline.

## Related Concepts

- [[concepts/intent-driven-schema]] — the lifecycle these gates protect
- [[concepts/opsx-workflow]] — the OpenSpec workflow engine being gated
- [[concepts/delta-spec]] — the spec deltas that must reach `main` before apply
- [[concepts/durable-artifacts-vs-scaffolding]] — archive is when scaffolding is retired

## Sources

- [openspec-git-discipline skill](https://github.com/intent-driven-dev/intent-driven-template/tree/main/.agents/skills/openspec-git-discipline) (`raw/intent-driven-template/skills.md`)
