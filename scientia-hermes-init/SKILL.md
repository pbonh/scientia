---
name: scientia-hermes-init
description: Provisions and validates the Hermes side before the first emit so scientia-hermes-emit cannot silently no-op. Creates project-specific profiles (prefixed with the board slug) carrying SOUL.md system prompts that embed the project's architecture, ADRs, contracts, and spec scenarios — keeping kanban agents on-task. Ensures the board exists, every prefixed profile exists, and the gateway is reachable. Derives the profile roster from the change's C4 diagram and ADR ownership when config does not enumerate it. Activate before the first emit for a change, or whenever scientia.hermes.preflight reports a missing board, profile, or gateway.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+; a local Hermes install with the Kanban feature
metadata:
  stage: hermes-init
  version: "0.3"
---

# scientia-hermes-init

Provision the Hermes side of the execution layer so that
`scientia-hermes-emit` cannot silently no-op. This is the **provision** phase:
you ensure a real board, real **project-specific** profiles (each carrying a
SOUL.md grounded in the project's architecture and specs), and a running
gateway exist, then return a structured preflight verdict. You hold the
*judgment* (deriving the profile roster, writing each profile's SOUL.md, and
authoring descriptions); the package (`scientia.hermes.preflight`,
`scientia.hermes.board`) holds the deterministic checks and name resolution.

## Why project-specific profiles?

A generic "implementer" profile has no project context — it cannot know which
ADRs are law, which components own which paths, or which contracts are
ratified. Project-specific profiles solve this by embedding the project's
architecture, ADRs, contracts, and spec scenarios directly into each profile's
SOUL.md system prompt. The profile name is prefixed with the board slug (e.g.
`circuit-solver-beta-implementer` instead of `implementer`), so different
boards can have different execution profiles on the same Hermes install.

## Activate when

- Before the first `scientia-hermes-emit` for a change, **or**
- `scientia.hermes.preflight.check(...)` reports a missing profile, board, or an
  unreachable gateway.

## Inputs

- The change dir (`scientia.paths.change_dir(cid)`) for C4 + ADR + spec context.
- The `hermes:` block of `references/config.yaml`
  (`scientia.paths.config_path()`), especially `profiles:`, `pipeline:`,
  `board:`, `profile_prefix:`, `backend:`, `rest_base:`, and `preflight:`.

## Procedure

1. **Read the `hermes:` config block.** Note `pipeline` (decides whether
   `conflict-resolver` is required), `board`, `profile_prefix`, `backend`,
   `rest_base`, and the `profiles:` map.

2. **Resolve the board name and profile prefix.**
   - Board: `scientia.hermes.board.resolve_board(<the `board:` config value>)`.
     An explicit `board:` slug wins verbatim; otherwise it defaults to the
     current project name (the slugified `scientia.paths.project_name()`).
   - Prefix: `scientia.hermes.board.resolve_profile_prefix(<the
     `profile_prefix:` config value>, board=<resolved_board>)`. An explicit
     non-empty string wins; an empty string disables prefixing; absent (None)
     defaults to the board slug.
   - Both init and emit call the same resolvers, so the two phases can never
     disagree on profile names.

3. **Derive the profile roster (judgment).** If `profiles:` is enumerated, use
   its keys as the role names. Otherwise derive the minimal roster: always
   `implementer`, `reviewer`, `integrator`; add `conflict-resolver` whenever
   `pipeline: impl-review-integrate`. Each role name is then prefixed via
   `scientia.hermes.board.prefixed_profile(prefix, role)` to produce the
   actual Hermes profile name (e.g. `circuit-solver-beta-implementer`).

4. **Read project context from the change directory.** This is the core of
   project-specific profiles — extract the artifacts that ground each agent:
   - `design.md` → C4 diagrams (mermaid blocks), Component Map (component→path
     globs), Shared Contracts (name, owner, ratified-by).
   - `adrs/` → accepted ADRs with their Y-statements and status.
   - `specs/` → spec scenarios (Feature/Scenario/Given/When/Then) that tasks
     trace to.
   Parse these with `scientia.hermes.parse.parse_design` for C4/contracts and
   read the ADR/spec files directly.

5. **Compose a project-specific SOUL.md for each profile.** Use the
   `soul-implementer`, `soul-reviewer`, and `soul-integrator` templates (via
   `scientia.templates.render`). The templates accept these variables:

   | Variable | Source |
   |----------|--------|
   | `project_name` | `scientia.paths.project_name()` |
   | `prefix_display` | The resolved prefix, capitalized (e.g. "Circuit Solver Beta "), or empty |
   | `architecture` | C4 mermaid blocks from `design.md` |
   | `component_map` | Component Map section from `design.md` |
   | `shared_contracts` | Shared Contracts section from `design.md` |
   | `accepted_adrs` | List of accepted ADRs with Y-statements from `adrs/` |
   | `spec_scenarios` | Key spec scenarios from `specs/` |

   For the `conflict-resolver`, copy `scientia-conflict-resolver/SKILL.md` as
   its SOUL.md (as before), but also append a `## Project Context` section
   with the architecture, contracts, and ADRs so the resolver has the same
   project grounding.

   Write each SOUL.md to a temp file under the change dir's `hermes/` subdirectory
   (`scientia.paths.hermes_dir(cid) / "souls" / "<prefixed-role>.md"`).

6. **Ensure the board exists.** Create the resolved board if it is absent.

7. **Ensure every prefixed profile exists**, including the prefixed
   conflict-resolver for the three-stage pipeline. Deploy each profile the
   **same way** with
   `scripts/provision_profile.sh <prefixed-name> <full-model-id> [body.md] [description]`
   — the canonical, idempotent recipe: plain `hermes profile create` (bundled
   skills, incl. the auto-loaded `kanban-worker`), a Fireworks custom-provider
   `config.yaml` with the role's `model.default`, an optional repo-tracked SOUL
   body, a description, a `~/.local/bin` wrapper, and btrfs NOCOW.

   When `hermes.profiles.<role>.model` is set in config, pass the model
   identifier to `provision_profile.sh` so the profile's `config.yaml` is
   written automatically. If no model is specified, warn: "profile
   `<prefixed-name>` has no model binding; agents will use the global default.
   Set `hermes.profiles.<role>.model` in config or run `hermes model`
   interactively."

   The implementer's description MUST include: "Complete your work card when
   tests pass; do not self-block for review — the pipeline has a dedicated
   reviewer stage." This prevents the green self-block stall pattern.

   **Pass the SOUL.md** as the `body.md` argument to `provision_profile.sh`
   for each profile. This deploys the project-specific system prompt so the
   agent starts each work card already grounded in the project's architecture,
   ADRs, and contracts.

   **Never** symlink `scientia-*` skills into a profile — the dispatcher
   auto-loads `kanban-worker`, and per-profile scientia skill symlinks only
   dangle when the shared skills source moves.

8. **Run preflight.** Call `scientia.hermes.preflight.check(plan_or_probe,
   require_gateway=..., rest_base=..., known_profiles=...)`. Refuse on a
   non-loopback `rest_base` (the kanban routes are unauthenticated) and on a
   `dir:` workspace that is not absolute. Pass `known_profiles` as the set of
   prefixed profile names.

9. **Report.** Return the structured `PreflightResult` (ok / errors / warnings).
   On any error, **halt with the exact remediation** (see the table) — do not
   proceed to emit.

## Profile naming convention

Profile prefixing is **automatic** by default — no configuration needed. The
prefix is the board slug (itself defaulting to the project name), so a project
called "Circuit Solver Beta" automatically gets profiles named
`circuit-solver-beta-implementer`, `circuit-solver-beta-reviewer`, etc.

| Config `profile_prefix` | Board slug | Role | Prefixed profile name |
|---|---|---|---|
| (absent — the default) | `circuit-solver-beta` | implementer | `circuit-solver-beta-implementer` |
| (absent — the default) | `circuit-solver-beta` | reviewer | `circuit-solver-beta-reviewer` |
| `""` (empty string) | any | implementer | `implementer` |
| `csb` | any | implementer | `csb-implementer` |

To **disable** prefixing (backward compatibility with pre-0.3 setups), add
`profile_prefix: ""` to the project's local `references/config.yaml`.
To use a **custom prefix**, set `profile_prefix: "<short-slug>"`.

## Remediation (surface verbatim on failure)

| Condition | Remediation |
|---|---|
| Hermes unreachable (no REST + no CLI) | start the dashboard / install Hermes |
| Gateway not running | `hermes gateway start` (else cards sit in `ready`) |
| Profile missing (incl. prefixed conflict-resolver) | create it here before emit |
| Non-loopback `rest_base` | keep it on `127.0.0.1` or pass `allow_remote` |
| `dir:` workspace not absolute | use an absolute path |

## Decision rules

- Use `scientia.paths`, `scientia.hermes.board`, and
  `scientia.hermes.preflight` — never hard-code a path or re-implement an
  env check.
- `conflict-resolver` is **required**, not optional, under
  `pipeline: impl-review-integrate`; its absence is a refuse, not a warning.
- Keep profile descriptions short and role-scoped; no secrets in any profile
  body (plaintext SQLite, rendered in the dashboard).
- Provision every profile through `scripts/provision_profile.sh` so the roster
  stays uniform (same skill set, config shape, wrapper). The kanban worker's
  `kanban_*` lifecycle tools come from the dispatcher-injected bundled
  `kanban-worker`, resolved from `<profile>/skills/devops/kanban-worker` — never
  from a `scientia-kanban-worker` symlink.
- The SOUL.md is the primary vehicle for project-specificity. Compose it from
  the templates + live project artifacts, not from static prose.

## Acceptance behavior

- Every assignee the plan will reference exists under its prefixed name (incl.
  prefixed `conflict-resolver` when the pipeline needs it).
- Each profile carries a SOUL.md grounded in the project's C4, ADRs,
  contracts, and spec scenarios.
- The gateway is reachable (when `preflight.require_gateway`).
- A structured preflight report is returned; on failure the skill halts with
  the exact remediation rather than letting emit no-op.
