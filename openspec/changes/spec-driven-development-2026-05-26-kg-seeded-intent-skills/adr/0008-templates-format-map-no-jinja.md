---
title: "ADR-0008: Render templates with str.format_map, no external engine"
adr_id: ADR-0008
status: accepted
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
supersedes: []
superseded_by: null
asr:
  - "Minimal dependency surface: stdlib only for templating (ASR-9)."
shared_types: []
tags: [spec-driven-development, templates, dependencies]
created: 2026-05-27
---

# ADR-0008: Render templates with str.format_map, no external engine

## Y-Statement

**In the context of** seven markdown templates in `references/` that
`kg_pipeline.templates` renders into produced artifacts,
**facing** the choice of templating mechanism under a minimal-dependency
constraint,
**we decided for** `str.format_map` substitution of `{name}` placeholders
against a flat dict,
**and against** Jinja2, a custom mini-engine, or building artifacts from
in-code f-strings,
**to achieve** a minimal dependency surface (ASR-9) and portability with
templates that constrain structure only,
**accepting** that templates can carry no loops or conditionals, that literal
braces must be escaped, and that any structural logic moves into the calling
skill/module.

## Architecturally Significant Requirement

ASR-9: dependencies are limited to stdlib + `pyyaml` (optionally `networkx`).
A templating engine like Jinja2 would add a dependency and a feature surface
(autoescaping, sandboxing, control flow) the brief explicitly does not want —
templates are meant to constrain structure, not compute.

## Options Considered

### Option A — Jinja2
*Pros:* powerful; loops, conditionals, inheritance.
*Cons:* a dependency; invites logic-in-templates; over-built for filling
section scaffolds. Violates ASR-9.

### Option B — Custom mini template engine
*Pros:* no third-party dep; tailored.
*Cons:* code to write, test, and secure; reinvents `str.format_map` badly.

### Option C — In-code f-strings, no template files
*Pros:* no template files.
*Cons:* structure buried in Python; non-authors can't edit the artifact shape;
defeats the point of `references/` templates.

### Option D — `str.format_map` over a flat dict (chosen)
*Pros:* stdlib; editable template files; deterministic; trivially testable.
**Chosen.**
*Cons:* no control flow; braces must be escaped.

## Consequences

- Templates are pure structure with `{placeholder}` slots; all branching lives
  in the skill or module that builds the vars dict.
- Literal `{`/`}` in template prose must be doubled (`{{`/`}}`).
- `render(template_name, **vars)` and `render_to_file(...)` are the only entry
  points; templates load from `references/` only.

## Supersession

Supersedes nothing.
