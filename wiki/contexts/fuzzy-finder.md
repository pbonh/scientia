---
title: "Fuzzy Finder"
type: context
tags: [context, bounded-context, generic]
created: 2026-05-24
updated: 2026-05-24
confidence: high
---

## Boundary

Television as a configurable terminal fuzzy finder: channels and cables
(its source-definition model), the remote-control navigation UI, a
string-template system, frecency-based ranking, shell integration,
search-pattern syntax, and inline/watch UI modes. Owns the
*fuzzy-finding* vocabulary.

## Subdomain Classification

**Generic.** A fuzzy finder is commodity interactive-search tooling
(television/fzf/etc.). Reference knowledge for the wiki, not a scientia
build or differentiator.

## In-Scope Concepts

- [[concepts/television-channel]]
- [[concepts/television-cable]]
- [[concepts/television-remote-control]]
- [[concepts/television-template-system]]
- [[concepts/television-frecency-sorting]]
- [[concepts/television-shell-integration]]
- [[concepts/television-search-pattern]]
- [[concepts/television-inline-mode]]
- [[concepts/television-watch-mode]]

## In-Scope Entities

- [[entities/television]]
- [[entities/string-pipeline]]
- [[entities/nucleo-matcher]]

## Ubiquitous Language (Glossary)

- **Channel** — a configured source of candidate items to fuzzy-search.
- **Cable** — a shareable bundle of channel definitions.
- **Remote control** — television's pane for switching channels mid-search.
- **Frecency** — a ranking that blends frequency and recency of
  selection.
- **Template system** — the string-pipeline syntax for transforming
  matched results into output.
- **Search pattern** — the query syntax (fuzzy/exact/negation) driving
  the matcher.
- **Inline mode** — embedding the finder within the current shell line.
- **Watch mode** — re-running a source on an interval for live results.

## False Cognates with Adjacent Contexts

- **"template"** (`television-template-system`, string-pipeline) collides
  with `pi-prompt-template` ([[contexts/coding-agent-platform]]) and
  Ansible's Jinja2 templating
  ([[contexts/infrastructure-automation]]) — three unrelated templating
  systems. See [[context-maps/terminal-tooling]].
- **"channel"** here (a search source) is a false cognate of Neovim's
  async *channels* ([[contexts/editor-extensibility]]) — unrelated.
- **"index"** implied by matching is unrelated to `wiki/index.md` in
  [[contexts/knowledge-base-and-wiki]].
- **"string-pipeline"** (the entity) is a templating crate, not a shell
  pipeline ([[contexts/shell-and-data-pipeline]]).

## Sources

- [[summaries/television-docs]]
