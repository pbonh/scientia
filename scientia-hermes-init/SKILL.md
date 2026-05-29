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
3. **Ensure the board exists.** Create it if `board:` names a slug that is
   absent; otherwise use the Hermes default board.
4. **Ensure every profile exists**, including `conflict-resolver` for the
   three-stage pipeline. The `conflict-resolver` profile body ships as
   `scientia-conflict-resolver/SKILL.md` — install/register it as the Hermes
   profile of that name.
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

## Acceptance behavior

- Every assignee the plan will reference exists (incl. `conflict-resolver` when
  the pipeline needs it).
- The gateway is reachable (when `preflight.require_gateway`).
- A structured preflight report is returned; on failure the skill halts with the
  exact remediation rather than letting emit no-op.
