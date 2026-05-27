---
title: "Spec: Pipeline Tooling"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: pipeline-tooling
created: 2026-05-26
updated: 2026-05-26
---

# Capability: Pipeline Tooling

The supporting deterministic modules — `kg_pipeline.templates`,
`kg_pipeline.validators`, `kg_pipeline.paths` — plus the seven markdown
templates, the `config.yaml`, and the test/eval suites. Templates render
via `str.format_map` (no Jinja). Validators return human-readable error
lists the controller gates on. Paths helpers centralize the file layout
so skills never hard-code paths.

## Glossary (inlined from manifest)

- **Skill validation** *(from manifest slice 4, agent-skills context)* —
  tooling that checks a skill's structure and frontmatter conform to the
  agentskills.io spec.

## New Terms (introduced by this capability)

- **Template render** — `str.format_map` substitution of `{name}`
  placeholders against a flat dict; no external template engine.
- **Validator** — a function returning a list of human-readable errors
  (empty list = pass).
- **Golden-file test** — a module test comparing actual against an
  expected JSON dump over a fixture wiki; no mocks.
- **Rubric-judged eval** — a fixture-based skill eval whose pass/fail is
  decided by an LLM call against a `rubric.md` of required and forbidden
  mentions.

## Personas

- **Pipeline Author** — the LLM agent that renders templates and runs
  validators through the modules.
- **Operator** — the human who runs the eval suite after editing a
  `SKILL.md` body.

## Acceptance Criteria

- Template rendering substitutes flat-dict placeholders without invoking
  any external template engine.
- A validator returns an empty list when its artifact conforms and a
  populated list otherwise.
- Path helpers are the single source of file-layout truth; skills use
  them rather than literal paths.
- `validate_skill_md` reports a `SKILL.md` whose `name` does not match its
  directory.

## Scenarios

### Scenario: Render a template by flat-dict substitution
```gherkin
Given a template containing the placeholder "{change_id}" and a vars dict mapping change_id to a value
When the Pipeline Author calls render on that template
Then the rendered output contains the value in place of the placeholder
```

### Scenario: A conforming artifact validates clean
```gherkin
Given a proposal.md that satisfies every required section
When the Pipeline Author calls validate_proposal on it
Then an empty error list is returned
```

### Scenario: A non-conforming artifact reports errors
```gherkin
Given a proposal.md missing its required "Why" section
When the Pipeline Author calls validate_proposal on it
Then the returned error list names the missing "Why" section
```

### Scenario: Flag a SKILL.md whose name mismatches its directory
```gherkin
Given a SKILL.md under directory "seed-proposal" whose frontmatter name is "seed_proposal"
When the Pipeline Author calls validate_skill_md on it
Then the returned error list reports the name/directory mismatch
```

### Scenario: A golden-file module test compares against the expected dump
```gherkin
Given a fixture wiki and its expected JSON dump of pages and rollups
When the Operator runs the module's golden-file test over that fixture
Then the test passes only when the actual dump equals the expected dump
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
