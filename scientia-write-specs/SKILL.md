---
name: scientia-write-specs
description: Translates an accepted proposal and the proposer's grill responses into gherkin-style scenarios (Feature/Scenario/Given/When/Then) in markdown — lightweight convention, no parser. Refuses to run while any grill entry is unaddressed, and stamps a traces-grill comment linking each scenario to the grill entry it satisfies. Activate after grill.md is fully addressed.
license: MIT
compatibility: Requires the scientia Python package (pip install scientia); Python 3.10+
metadata:
  stage: specs
  version: "1.0"
---

# scientia-write-specs

Turn the addressed proposal + grill into one `specs/<capability>/spec.md` per
capability, in Gherkin-style markdown. This is convention, not a parsed `.feature`
format.

## Inputs

- `proposals/<change-id>/proposal.md`
- `proposals/<change-id>/grill.md` (must be fully addressed)

## Outputs

- `proposals/<change-id>/specs/<capability>/spec.md`, rendered from the
  `gherkin-spec` template via `scientia.templates`.

## Gate (refuse-if-unaddressed)

Before writing anything, confirm no grill entry is unaddressed. Run
`scientia.validators.validate_grill(paths.grill_path(cid))`; if it returns
errors, **refuse** and report the unaddressed entries. Equivalently, the grill
stage's advance marker must be present
(`scientia.advance.is_advanced(cid, "grill")`).

## Authoring discipline (spec: intent-artifact-generation; [[gherkin]])

- **Exactly one observable `When` per scenario.** Keep UI clicks, HTTP calls,
  and DB rows out of the scenario — those belong in step definitions, not here.
- `Then` states an observable outcome.
- Use `### Scenario: <title>` headings inside the rendered `## Scenarios`
  section; `scientia.validators.validate_specs` checks the one-When rule.
- Each scenario that came from a grill-derived requirement carries a
  traceability comment naming the entry id:

  ```
  ### Scenario: <title>
  <!-- traces-grill: <grill-entry-id> -->
  ```

  ```gherkin
  Given <precondition>
  When <single observable event>
  Then <observable outcome>
  ```

## Decision rules

- One capability per spec file; group related scenarios under one Feature.
- Stamp `traces-grill` on every scenario derived from a grill entry.
- Validate with `validate_specs(paths.specs_dir(cid))` before finishing.

## Low-confidence handling (mode key: `write_specs`, default `autonomous`)

Specs are revisable; runs `autonomous`. When a requirement's wording is
ambiguous, encode the most defensible interpretation and note the alternative in
the scenario description rather than halting.

## Acceptance behavior

- `write-specs` refuses to run while any grill entry is `addressed: false`.
- Each grill-derived requirement is traceable to a scenario via `traces-grill`.
