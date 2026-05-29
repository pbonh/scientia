---
skill: ingest-source
---

# Rubric: ingest-source

## Setup

Run `ingest-source` on `sources/karpathy-2026.md` (this directory) against an
empty `wiki/`. Save the agent's summary of what it wrote to `output.md` here.

## Expected wiki state

- `source-karpathy-2026.md` (type `source`)
- one entity page for the LLM-wiki concept (type `entity`)
- ≥2 claim pages (type `claim`) each with `confidence.base` set, no `effective`
  set by the agent (recompute fills it)
- one question page (type `question`) for the drift/lint open question

## Required mentions (output MUST contain)

- source-karpathy-2026
- claim
- base
- question

## Forbidden mentions (output MUST NOT contain)

- deleted the
- rewrote the older claim
- set effective to

## Pass criteria

The agent registered the source, created typed pages with only `base` set on
claims, recorded any contradiction as a bidirectional edge without rewriting an
older claim, and created a question page — deleting nothing.
