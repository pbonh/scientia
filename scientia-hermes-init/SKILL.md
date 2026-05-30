---
name: scientia-hermes-init
description: Provisions and validates the Hermes side before the first emit so scientia-hermes-emit cannot silently no-op. Ensures the board exists, every configured profile exists (implementer, reviewer, integrator, and — for the impl-review-integrate pipeline — conflict-resolver), and the gateway is reachable. Derives a minimal profile roster from the change's C4 diagram and ADR ownership when config does not enumerate it. Activate before the first emit for a change, or whenever scientia.hermes.preflight reports a missing board, profile, or gateway.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+; a local Hermes install with the Kanban feature
metadata:
  stage: hermes-init
  version: "0.2"
---

# scientia-hermes-init

Provision the Hermes side of the execution layer so that
`scientia-hermes-emit` cannot silently no-op. This is the **provision** phase:
you ensure a real board, real profiles, and a running gateway exist, then return
a structured preflight verdict. You hold the *judgment* (deriving the profile
roster and writing each profile's description); the package
(`scientia.hermes.preflight`) holds the deterministic checks.

## Activate when

- Before the first `scientia-hermes-emit` for a change, **or**
- `scientia.hermes.preflight.check(...)` reports a missing profile, board, or an
  unreachable gateway.

## Inputs

- The change dir (`scientia.paths.change_dir(cid)`) for C4 + ADR context.
- The `hermes:` block of `references/config.yaml`
  (`scientia.paths.config_path()`), especially `profiles:`, `pipeline:`,
  `board:`, `backend:`, `rest_base:`, and `preflight:`.

## Procedure

1. **Read the `hermes:` config block.** Note `pipeline` (decides whether
   `conflict-resolver` is required), `board`, `backend`, `rest_base`, and the
   `profiles:` map.
2. **Derive the profile roster (judgment).** If `profiles:` is enumerated, use
   it. Otherwise derive the minimal roster from the C4 container/component
   diagram and ADR ownership: always `implementer`, `reviewer`, `integrator`;
   add **`conflict-resolver`** whenever `pipeline: impl-review-integrate`. Author
   a one-line description for each (the committed defaults are a good template).
3. **Ensure the board exists.** Resolve the board name with
   `scientia.hermes.board.resolve_board(<the `board:` config value>)`: an
   explicit `board:` slug wins verbatim; otherwise it defaults to the current
   project name (the slugified `scientia.paths.project_name()`) so the board
   belongs to this project rather than Hermes' shared default. `scientia-hermes-emit`
   calls the same resolver, so init and emit never disagree on the name. Create
   that board if it is absent.
4. **Ensure every profile exists**, including `conflict-resolver` for the
   three-stage pipeline. Deploy each profile the **same way** with
   `scripts/provision_profile.sh <name> <full-model-id> [body.md] [description]`
   — the canonical, idempotent recipe: plain `hermes profile create` (bundled
   skills, incl. the auto-loaded `kanban-worker`), a Fireworks custom-provider
   `config.yaml` with the role's `model.default`, an optional repo-tracked SOUL
   body, a description, a `~/.local/bin` wrapper, and btrfs NOCOW. The
   `conflict-resolver` body ships as `scientia-conflict-resolver/SKILL.md`; the
   `implementer`/`reviewer`/`integrator` personas are init-authored (no body
   file). **Never** symlink `scientia-*` skills into a profile — the dispatcher
   auto-loads `kanban-worker`, and per-profile scientia skill symlinks only
   dangle when the shared skills source moves.

   When `hermes.profiles.<name>.model` is set in config, pass the model
   identifier to `provision_profile.sh --model <provider:model_id>` so the
   profile's `config.yaml` is written automatically. If no model is specified,
   warn: "profile `<name>` has no model binding; agents will use the global
   default. Set `hermes.profiles.<name>.model` in config or run `hermes model`
   interactively."

   The implementer's description should include: "Complete your work card when
   tests pass; do not self-block for review — the pipeline has a dedicated
   reviewer stage." This prevents the green self-block stall pattern where
   implementers block with `review-required` instead of completing.
5. **Run preflight.** Call `scientia.hermes.preflight.check(plan_or_probe,
   require_gateway=..., rest_base=..., known_profiles=...)`. Refuse on a
   non-loopback `rest_base` (the kanban routes are unauthenticated) and on a
   `dir:` workspace that is not absolute.
6. **Report.** Return the structured `PreflightResult` (ok / errors / warnings).
   On any error, **halt with the exact remediation** (see the table) — do not
   proceed to emit.

## Remediation (surface verbatim on failure)

| Condition | Remediation |
|---|---|
| Hermes unreachable (no REST + no CLI) | start the dashboard / install Hermes |
| Gateway not running | `hermes gateway start` (else cards sit in `ready`) |
| Profile missing (incl. `conflict-resolver`) | create it here before emit |
| Non-loopback `rest_base` | keep it on `127.0.0.1` or pass `allow_remote` |
| `dir:` workspace not absolute | use an absolute path |

## Decision rules

- Use `scientia.paths` and `scientia.hermes.preflight` — never hard-code a path
  or re-implement an env check.
- `conflict-resolver` is **required**, not optional, under
  `pipeline: impl-review-integrate`; its absence is a refuse, not a warning.
- Keep profile descriptions short and role-scoped; no secrets in any profile
  body (plaintext SQLite, rendered in the dashboard).
- Provision every profile through `scripts/provision_profile.sh` so the roster
  stays uniform (same skill set, config shape, wrapper). The kanban worker's
  `kanban_*` lifecycle tools come from the dispatcher-injected bundled
  `kanban-worker`, resolved from `<profile>/skills/devops/kanban-worker` — never
  from a `scientia-kanban-worker` symlink.

## Acceptance behavior

- Every assignee the plan will reference exists (incl. `conflict-resolver` when
  the pipeline needs it).
- The gateway is reachable (when `preflight.require_gateway`).
- A structured preflight report is returned; on failure the skill halts with the
  exact remediation rather than letting emit no-op.
