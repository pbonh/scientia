---
title: "Spec: KG Wiki Model"
tenant: spec-driven-development
change_id: 2026-05-26-kg-seeded-intent-skills
capability: kg-wiki-model
created: 2026-05-26
updated: 2026-05-26
---

# Capability: KG Wiki Model

The typed-node knowledge-graph representation of the wiki and the
on-demand traversal library (`kg_pipeline.wiki`) that parses it. The wiki
is the *only* persistent representation of the KG — there is no derived
graph database; queries parse markdown files on demand. Every page is
markdown with YAML frontmatter and a `type`. Edges are wiki-links whose
kind is encoded in the link's alias slot.

## Glossary (inlined from manifest)

- **Concept page / Entity page** *(false-cognate flag)* — in scientia's
  own wiki these are page types; the wikis this capability *produces* use
  a different typed-node scheme (see New Terms). Same words, different
  model. Do not conflate.

## New Terms (introduced by this capability)

- **Node type** — one of `entity`, `claim`, `source`, `question`. Only
  `claim` carries confidence.
- **Edge kind** — `mentions` (default), `supports`, `contradicts`,
  `refines`, encoded in a wiki-link's alias slot
  (`[[claim-x | supports]]`).
- **Page** — a dataclass `{frontmatter: dict, body: str}`.
- **Link** — a pair `(target_id: str, kind: str)`.

## Personas

- **Pipeline Author** — the LLM agent executing a pipeline skill that
  reads the KG through the library.
- **KG Library** — `kg_pipeline.wiki`, the deterministic, pure-Python
  traversal module. Authority: parsing and writing pages; never mutates
  semantics.

## Acceptance Criteria

- Every produced page sets `type` in frontmatter; a page without `type`
  is invalid.
- `parse_links` recovers the edge kind from the alias slot and defaults
  unknown aliases to `mentions`.
- `neighbors` returns exactly the pages reachable within the requested
  hop count.
- `write_page` is idempotent: writing a page already on disk produces no
  content change.

## Scenarios

### Scenario: Load a well-formed page into a Page dataclass
```gherkin
Given a wiki file with valid YAML frontmatter and a markdown body
When the Pipeline Author calls load_page on that file
Then the returned Page carries the parsed frontmatter dict and the body string
```

### Scenario: Reject a page that omits its node type
```gherkin
Given a wiki file whose frontmatter has no "type" field
When the Pipeline Author loads and validates that page
Then the page is reported invalid with a message naming the missing "type" field
```

### Scenario: Recover edge kind from the link alias slot
```gherkin
Given a page body containing the link "[[claim-x-causes-y | supports]]"
When the Pipeline Author calls parse_links on that body
Then a Link with target "claim-x-causes-y" and kind "supports" is returned
```

### Scenario: Treat an unknown alias as a mentions edge
```gherkin
Given a page body containing the link "[[entity-llm-wiki | seealso]]"
When the Pipeline Author calls parse_links on that body
Then a Link with target "entity-llm-wiki" and kind "mentions" is returned
```

### Scenario: Traverse the neighborhood to a bounded hop count
```gherkin
Given a claim page that links to a second claim which links to a third claim
When the Pipeline Author calls neighbors on the first page with hops set to 1
Then only the directly-linked second claim is returned
```

### Scenario: Writing an unchanged page leaves it byte-identical
```gherkin
Given a Page loaded from an existing wiki file
When the KG Library calls write_page with that unchanged Page
Then the file on disk is byte-identical to before the write
```

## Kanban Tasks
<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->
