# Installing scientia

scientia is a bundle of [Agent Skills](https://agentskills.io). It
installs by cloning into the user-level skills directory every tested
client discovers — `~/.agents/skills/`. There is no install script.

## Install

```bash
git clone https://github.com/pbonh/scientia.git ~/.agents/skills/scientia
```

That is the entire install step. The 22 skills (and the 4 Hermes
profiles bundled inside `scientia-kanban-init/assets/profiles/`)
become discoverable by any client that walks
`~/.agents/skills/` recursively for `SKILL.md` files. Tested clients:
OpenCode, Claude Code, Cursor.

If a client looks at a different path (e.g., `.opencode/skills/`,
`.claude/skills/`), point it at `~/.agents/skills/scientia/skills/`
or symlink:

```bash
mkdir -p ~/.opencode
ln -s ~/.agents/skills ~/.opencode/skills
```

## Verify

Activate the `scientia` skill in your client of choice:

> *"Use the scientia skill."*

The orchestrator reads on-disk state and, for an empty repo, will
recommend `scientia-wiki-init` as the next action. That skill
scaffolds `raw/`, `wiki/`, `development/`, and `openspec/` in the
target repository.

## Hermes profiles

The four scientia agent profiles
(`scientia-implementer`, `scientia-reviewer`, `scientia-integrator`,
`scientia-aggregator`) are bundled at:

```
~/.agents/skills/scientia/skills/scientia-kanban-init/assets/profiles/
```

They are **not** copied to `~/.hermes/profiles/` at install time —
the `scientia-kanban-init` skill copies them on its first run for a
host. Activating the orchestrator and saying *"initialize Hermes"*
triggers it; the skill is idempotent and refuses to overwrite
hand-edited profiles.

If you prefer to copy them yourself:

```bash
mkdir -p ~/.hermes/profiles
cp ~/.agents/skills/scientia/skills/scientia-kanban-init/assets/profiles/*.md ~/.hermes/profiles/
```

## Upgrade

```bash
cd ~/.agents/skills/scientia
git pull
```

If a schema migration is required (rare; only when
`scientia_schema_version` changes), `verify_all.py` will report it as
a CRITICAL finding pointing at the appropriate migration script in
`skills/scientia/scripts/migrations/`. v0.1 has no migrations.

## Uninstall

```bash
rm -rf ~/.agents/skills/scientia
```

Existing target repos retain their `raw/`, `wiki/`, `development/`,
and `openspec/` directories — scientia owns no state outside the
bundle and the per-repo scaffold. Hermes profiles installed by
`scientia-kanban-init` remain in `~/.hermes/profiles/`; remove them
by hand if you no longer want them:

```bash
rm ~/.hermes/profiles/scientia-{implementer,reviewer,integrator,aggregator}.md
```

## Why a clone install, not a copy install

The bundle layout is spec-conformant per skill. Cloning the whole
repo to a single discoverable directory and letting the client walk
it recursively gives:

- **One command install.** No script, no flags, no per-client paths.
- **Trivial upgrade.** `git pull`.
- **Reviewable provenance.** The bundle is the git history; the user
  can audit `git log` to see what changed since their last `pull`.
- **No skill duplication.** Every client points at the same
  source-of-truth directory; if you fork, you fork once.
