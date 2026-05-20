---
name: scientia-kanban-init
description: One-shot Hermes Kanban bootstrap for the host. Copies the four scientia agent profiles from this skill's assets/profiles/ to ~/.hermes/profiles/, verifies the hermes CLI is on PATH, confirms the kanban.db path declared in development/config.yaml is writable, and registers scientia-kanban-worker as the required worker skill. Run once per host (not per repo) on first scientia use, or whenever the user says "initialize Hermes". Idempotent — never overwrites a hand-edited profile.
license: MIT
metadata:
  bundle: scientia
  phase: kanban
  order: "1"
---

# scientia-kanban-init

Make this host ready to run the scientia kanban phase.

## Procedure

1. **Verify Hermes is available.** Run `command -v hermes`. If missing,
   report and refuse to proceed; scientia depends on Hermes as one of
   its two allowed external dependencies.

2. **Verify `kanban.db` is reachable.** Read
   `development/config.yaml` for `hermes.kanban_db` (default
   `~/.hermes/kanban.db`). Verify the parent directory exists and is
   writable. If the file does not exist, let Hermes create it on first
   use; do not pre-create.

3. **Copy the four scientia agent profiles** from this skill's
   `assets/profiles/` directory (resolved relative to the skill's
   on-disk location, e.g. `~/.agents/skills/scientia/skills/scientia-kanban-init/assets/profiles/`)
   into `~/.hermes/profiles/`:

   - `scientia-implementer.md`
   - `scientia-reviewer.md`
   - `scientia-integrator.md`
   - `scientia-aggregator.md`

   Create `~/.hermes/profiles/` if it does not exist. If a profile of
   the same name already exists at the target, **do not overwrite**.
   Log `profile-already-present` to `development/log.md` and continue.
   To force an overwrite (e.g., after upgrading scientia), the user
   must explicitly remove the existing profile first:
   `rm ~/.hermes/profiles/scientia-implementer.md` and re-run this
   skill.

4. **Register `scientia-kanban-worker` as the worker skill.** Each
   profile's body already names `scientia-kanban-worker` in its
   `Skills:` section. This skill verifies that the corresponding skill
   directory exists in the client's skills directory.

5. **Smoke-test.** Run `hermes kanban list --format json` and verify
   it returns valid JSON (even if empty). If it errors, report and
   refuse to mark init complete.

6. **Append to `development/log.md`**:

   ```markdown
   - YYYY-MM-DDTHH:MM:SSZ — scientia-kanban-init — host-ready — — profiles=4 kanban_db=<path>
   ```

7. **Report ready.** The host is now ready to run
   `scientia-kanban-emit` for any tenant.

## What this skill never does

- Creates kanban tasks. Emission is `scientia-kanban-emit`.
- Modifies `kanban.db` schema. The schema is owned by Hermes.
- Touches per-repo `development/`, `openspec/`, or `wiki/`.
