---
name: scientia-wiki-lint
description: Validate the wiki's structural and link integrity. Checks YAML frontmatter on every page, verifies wiki-link targets resolve, ensures wiki/index.md lists every page in the wiki, and confirms wiki/log.md is append-only and well-formed. Run as a gate before scientia-wiki-bind and on every CI invocation of verify_all.py. Idempotent and read-only — produces a report; never edits the wiki.
license: MIT
metadata:
  bundle: scientia
  phase: wiki
  order: "5"
---

# scientia-wiki-lint

Validate the wiki. Read-only. Output is a markdown report with findings
classified by severity (CRITICAL / WARNING / SUGGESTION). The script
that does the work is `scripts/lint.py`; this `SKILL.md` documents what
the linter checks and how to act on the report.

## What the linter checks

| Check | Severity | Description |
|---|---|---|
| `frontmatter-missing` | CRITICAL | A `.md` file in `wiki/` lacks YAML frontmatter. |
| `frontmatter-required-fields` | CRITICAL | A page's frontmatter is missing `title`, `type`, or `updated`. |
| `frontmatter-type-mismatch` | WARNING | `type:` does not match the page's directory (e.g., a `type: entity` page under `concepts/`). |
| `wikilink-unresolved` | CRITICAL | `[[concepts/foo]]` references a file that does not exist. |
| `index-missing-row` | WARNING | A page exists on disk but is not listed in `wiki/index.md`. |
| `index-stale-row` | WARNING | `wiki/index.md` lists a page that does not exist on disk. |
| `log-not-monotonic` | WARNING | `wiki/log.md` has a non-monotonic timestamp (later line earlier date). |
| `confidence-missing` | SUGGESTION | A page has no `confidence:` field. |
| `sources-missing` | SUGGESTION | A page has no `sources:` field (acceptable for hand-authored pages). |
| `orphan-page` | SUGGESTION | A concept/entity page is not referenced by any context page. |

## Procedure

1. **Run the linter:**

   ```bash
   skills/scientia-wiki-lint/scripts/lint.py --repo <path> [--json]
   ```

2. **Read the report.** Markdown by default; JSON on `--json` for
   programmatic consumption (e.g., by `verify_all.py`).

3. **Act on findings:**
   - CRITICAL findings block `scientia-wiki-bind` and CI.
   - WARNING findings surface in the orchestrator's recommendation but
     do not block by default (configurable via
     `development/config.yaml`'s `verify.block_on_severity`).
   - SUGGESTION findings are advisory.

4. **Append a summary line** to `development/log.md`:

   ```markdown
   - YYYY-MM-DDTHH:MM:SSZ — scientia-wiki-lint — completed — — critical=0 warning=2 suggestion=5
   ```

## What this skill never does

- Edits the wiki. The linter is read-only. Fixes are made by the user
  or by re-running the relevant `scientia-wiki-*` skill.
- Touches `development/`, `openspec/`, or `kanban.db`.
