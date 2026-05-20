# Installing scientia

scientia is an installable bundle of Agent Skills. The bundle ships skills
under `skills/`, Hermes profiles under
`skills/scientia-kanban-init/assets/profiles/`, and templates under
`skills/scientia-wiki-init/assets/templates/`. Installation has two
distinct steps:

1. **Place the skills where your Agent Skills client can discover them.**
   This is a per-host concern handled by `install.sh`.
2. **Scaffold the target repository's `raw/`, `wiki/`, `development/`, and
   `openspec/` directories.** This is a per-repo concern handled by
   `scientia-wiki-init` (which runs the first time you invoke the
   `scientia` orchestrator in a target repo).

## Quick start

```bash
git clone https://github.com/<you>/scientia.git
cd scientia
./install.sh /path/to/target/repo
```

Then in the target repo, activate the `scientia` skill and say:

> *"Initialize this repository for scientia."*

The orchestrator detects no wiki / openspec / development directories
exist and recommends `scientia-wiki-init`, which scaffolds everything.

## Per-client install paths

`install.sh` accepts `--client <name>` to choose where to place skills.
Supported clients and their default paths (declared in `scientia.json`):

| Client | Default install path inside target repo |
|---|---|
| `opencode` | `.opencode/skills/`, falling back to `.agents/skills/` |
| `claude-code` | `.claude/skills/` |
| `cursor` | `.cursor/skills/` |
| `generic` (default) | `.agents/skills/` |

Override with `--skills-path <abs-path>`. The Hermes profiles always go to
`~/.hermes/profiles/` regardless of client (Hermes is host-scoped, not
repo-scoped).

```bash
./install.sh /path/to/target/repo --client opencode
./install.sh /path/to/target/repo --skills-path /custom/skills/dir
```

## What install.sh does

1. Read `scientia.json` to enumerate the skills and profiles to install.
2. Resolve the target skill directory based on `--client` or
   `--skills-path`.
3. Copy each `skills/<skill>/` directory into the target skill directory.
4. Copy each profile from `skills/scientia-kanban-init/assets/profiles/`
   into `~/.hermes/profiles/` (unless `--no-profiles`).
5. Write a tiny breadcrumb to `<target-repo>/.scientia-install.json`
   recording the bundle version installed, so `--upgrade` knows what to do.

`install.sh` is idempotent. Re-running it copies any missing files and
does not overwrite skills the user has hand-edited (a warning is printed
and the file is left alone). To force overwrite, pass `--force`.

## Upgrade

```bash
cd /path/to/scientia
git pull
./install.sh /path/to/target/repo --upgrade
```

`--upgrade` reads the breadcrumb at `<target-repo>/.scientia-install.json`
to determine the previously installed version, then runs any matching
migration scripts from `skills/scientia/scripts/migrations/`. Migrations
are append-only and idempotent. Each migration appends a line to
`<target-repo>/development/log.md`.

In-flight changes (those whose `manifests/.../core.md` was bound under the
previous `scientia_schema_version`) continue to use the old schema until
archived; only new changes use the new schema.

## Uninstall

```bash
./install.sh /path/to/target/repo --uninstall
```

Removes only files that `install.sh` placed. Does not touch `raw/`,
`wiki/`, `development/`, or `openspec/` (the repo's data). To fully
remove scientia, you can additionally delete those directories yourself.

## Verifying an install

After install, in the target repo:

```bash
/path/to/scientia/skills/scientia/scripts/verify_all.py
```

This is the same script that scientia's CI integration uses. On a freshly
initialized repo with no changes in flight, it exits 0 with an empty
report.
