---
name: scientia-wiki-init
description: Scaffold a fresh scientia-managed repository. Creates raw/, wiki/ (with index.md and log.md), development/ (with config.yaml and log.md), and openspec/ (with config.yaml and the intent-driven schema). Use exactly once per repository, the first time the scientia orchestrator detects no scientia layout. Idempotent — re-running fills in missing files without overwriting existing ones.
license: MIT
metadata:
  bundle: scientia
  phase: wiki
  order: "1"
---

# scientia-wiki-init

Scaffold the on-disk layout scientia depends on, in this exact order:

```
<repo>/
├── AGENTS.md                # how AI agents operate in this repo (front door)
├── raw/                     # immutable source documents
├── wiki/
│   ├── index.md             # master catalog
│   ├── log.md               # append-only activity log
│   ├── concepts/            # concept pages
│   ├── entities/            # entity pages
│   ├── summaries/           # one summary per raw source
│   ├── syntheses/           # cross-source syntheses; ingest writes proposed edits here
│   ├── contexts/            # bounded-context pages (strategy phase populates)
│   ├── context-maps/        # context maps
│   ├── decisions/           # ADR mirrors for living documentation
│   └── specs/               # spec mirrors for living documentation
├── development/
│   ├── config.yaml          # scientia per-repo config
│   ├── log.md               # orchestrator audit trail
│   ├── manifests/           # per-tenant manifests
│   └── tasks/               # per-tenant per-change kanban task index
└── openspec/
    ├── config.yaml          # OpenSpec config (scientia writes scientia bindings here)
    ├── schemas/intent-driven/
    └── changes/             # per-change OpenSpec change directories
```

## Procedure

0. **Collect the repo purpose.** Ask the user for 1–3 sentences
   describing what this scientia-managed repo is for (e.g. *"Track
   open-source LLM research papers and turn weekly findings into
   design briefs."*). Echo the text back, get explicit confirmation,
   then pass it verbatim as `bootstrap.py --purpose "<text>"`.
   `bootstrap.py` rejects an empty or whitespace-only value with a
   non-zero exit, so do not skip this step or pass `""`.

1. **Check what's already there.** For every path above, decide:
   - missing → create from template
   - present + identical to template → leave alone
   - present + different from template → do not overwrite; log to
     `development/log.md` as `init-skipped:<path>` so the user knows.

2. **Copy templates.** All templates live in `assets/templates/`,
   mirroring the on-disk layout:

   - `assets/templates/AGENTS.md.tmpl` → `AGENTS.md`
   - `assets/templates/wiki/index.md.tmpl` → `wiki/index.md`
   - `assets/templates/wiki/log.md.tmpl` → `wiki/log.md`
   - `assets/templates/development/config.yaml.tmpl` → `development/config.yaml`
   - `assets/templates/development/log.md.tmpl` → `development/log.md`
   - `assets/templates/openspec/config.yaml.tmpl` → `openspec/config.yaml`
   - `assets/templates/openspec/schemas/intent-driven/*` → `openspec/schemas/intent-driven/`

   Each `.tmpl` file uses `{{repo_name}}` and `{{date}}` placeholders;
   `AGENTS.md.tmpl` additionally uses `{{repo_purpose}}` (from step 0)
   and `{{bundle_version}}`. Substitute at copy time.

3. **Run `scripts/bootstrap.py --purpose "<text>"`** to perform the
   copy, substitution, and directory creation. The script is
   idempotent and prints exactly what it did.

4. **Verify** by reading the resulting `wiki/index.md` and
   `development/config.yaml` and confirming the structure matches the
   skeleton above. Append a line to `development/log.md`:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-wiki-init — bootstrap-complete — bundle <version>' >> development/log.md
   ```

5. **Hand off.** Inform the user the scaffold is complete and the next
   recommended action (from the orchestrator's SKILL_MAP) is usually:
   - `scientia-wiki-ingest` if `raw/` contains source documents, or
   - `scientia-wiki-strategy` if the user already knows the bounded
     contexts and wants to seed them, or
   - directly naming a new change tenant if the wiki is intended to grow
     alongside the first change.

## What this skill never does

- Writes anything outside the scaffold directories listed above.
- Overwrites a user-edited file (only creates missing files).
- Installs Hermes profiles (that is `scientia-kanban-init`'s job).
- Decides which bounded contexts exist (that is `scientia-wiki-strategy`'s job).

This skill does prompt **once** — for the repo purpose in step 0 —
and that is the only interactive question it asks; everything else is
derived from the filesystem, clock, and bundle manifest.

## Upgrades

When invoked under `install.sh --upgrade`, this skill re-runs the
template copy with the diff-aware logic above. Any files added in newer
bundle versions are filled in; user-edited files are never touched.
Migration scripts (under `skills/scientia/scripts/migrations/`) are
responsible for in-place transformations of *existing* files; this skill
does not perform transformations.
