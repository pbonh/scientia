---
name: scientia-wiki-strategy
description: Run strategic Domain-Driven Design over the wiki. Identifies bounded contexts, classifies subdomains as core/supporting/generic, produces context maps, and flags false-cognates and duplicate-concepts across contexts. Required before scientia-wiki-bind because the manifest's domain-framing slice depends on bounded-context structure. Use periodically as the wiki accumulates concept pages, and always before binding the first manifest for a new tenant.
license: MIT
metadata:
  bundle: scientia
  phase: wiki
  order: "3"
---

# scientia-wiki-strategy

Apply Eric Evans's strategic DDD to the wiki, producing first-class
`wiki/contexts/` and `wiki/context-maps/` pages.

## Procedure

1. **Read the index.** Enumerate all concept and entity pages via
   `wiki/index.md`. Note tags and confidence levels.

2. **Identify candidate bounded contexts.** A bounded context is a
   region of the domain in which one consistent ubiquitous language
   applies. Heuristics:
   - Concept pages whose definitions share vocabulary cluster into one
     context.
   - Tags like `bounded-context`, `domain-concern` are strong signals
     when ingested concepts already carry them.
   - When in doubt, ask the user. Use `scientia-grill` for any
     decision that cannot be answered by reading the wiki.

3. **Classify each context** by subdomain type:
   - **core** — the differentiator; where the business invests.
   - **supporting** — necessary but not differentiating.
   - **generic** — commodity; ideally replaceable by a vendor.

4. **Write one page per bounded context** at
   `wiki/contexts/<slug>.md`:

   ```yaml
   ---
   title: "<Context Name>"
   type: context
   tags: [context, bounded-context, <core|supporting|generic>]
   created: <YYYY-MM-DD>
   updated: <YYYY-MM-DD>
   confidence: high|medium|low
   ---

   ## Boundary
   ## Subdomain Classification
   ## In-Scope Concepts
   ## In-Scope Entities
   ## Ubiquitous Language (Glossary)
   ## False Cognates with Adjacent Contexts
   ## Sources
   ```

   The **Ubiquitous Language** section is a contextual glossary: term
   → definition, scoped to this context. Inlining it into kanban task
   bodies later protects against false-cognate drift across workers.

5. **Write one or more context-map pages** at
   `wiki/context-maps/<slug>.md` to record relationships *between*
   contexts (upstream/downstream, customer/supplier, conformist,
   anti-corruption layer, etc.). Use this template:

   ```yaml
   ---
   title: "<Context Map Title>"
   type: context-map
   tags: [context-map]
   contexts: [<context-a-slug>, <context-b-slug>, ...]
   created: <YYYY-MM-DD>
   updated: <YYYY-MM-DD>
   ---

   ## Relationships
   ## False Cognates
   ## Duplicate Concepts
   ## Open Questions
   ```

6. **Flag false-cognates and duplicate-concepts.** Two different
   contexts using the same term to mean different things is a
   false-cognate. Two different terms for the same thing is a
   duplicate-concept. Each finding becomes:
   - a row in the relevant context-map page's `## False Cognates` or
     `## Duplicate Concepts` section, and
   - an entry on each affected context page's `## False Cognates with
     Adjacent Contexts` section, with a wiki-link to the offending
     concept page on the other side.

7. **Update `wiki/index.md`** — add rows to the **Contexts** and
   **Context Maps** tables.

8. **Append to `wiki/log.md`** one line per context or map page
   created.

## When to ask vs. decide

- *Reading existing pages decides:* whether two concepts share
  vocabulary, which entities a context touches, what tags imply.
- *Ask via `scientia-grill`:* what counts as the core subdomain in
  this business; whether two near-synonyms are false-cognates or just
  ill-named duplicates; where to draw the boundary when concepts
  straddle two candidate contexts.

## Quality bar

- Every concept and entity page is referenced from exactly one
  bounded context (no orphans, no double-counting). Use the
  `## In-Scope Concepts` and `## In-Scope Entities` sections to verify.
- Every context has a non-empty ubiquitous-language glossary.
- Every adjacent context pair has at least one entry in a
  context-map page or an explicit "no overlap" note.

## What this skill never does

- Edits concept or entity page bodies (it only categorizes them).
- Renames concepts to resolve duplicates — that requires a manual
  decision recorded as an ADR after the user agrees.
- Writes to `development/` or `openspec/`.
