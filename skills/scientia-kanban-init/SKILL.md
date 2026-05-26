---
name: scientia-kanban-init
description: One-shot Hermes Kanban bootstrap for the host. Creates the four scientia agent profile directories via `hermes profile create` (plus an optional fifth `scientia-jobhunt-agent` browser profile, with its browser toolset enabled and provider reachability preflighted, when development/config.yaml declares a `jobhunt:` block), writes their SOUL.md bodies from this skill's assets/profiles/, applies per-profile model configuration declared under `hermes.profiles` in development/config.yaml (propagating any referenced host `custom_providers` entries into each profile's own config.yaml so workers can resolve `custom:<name>`), runs an API-key reachability preflight that refuses init when a declared `custom:<name>` provider's `key_env` is absent from process env, host `.env`, and the profile's own `.env`, symlinks the scientia skills (kanban-worker, grill, …) into both `~/.hermes/skills/` (for emit-time `--skill` validation) and each `~/.hermes/profiles/<name>/skills/` (for worker-time skill loading; required — workers crash on spawn without it), verifies the hermes CLI is on PATH and the kanban.db path declared in development/config.yaml is writable, propagates the per-repo `hermes.max_concurrent_children` cap to *both* `~/.hermes/config.yaml` and each scientia profile's `delegation.max_concurrent_children` (so sub-delegations from a worker honour the same cap), and confirms the Hermes gateway is up. Run once per host (not per repo) on first scientia use, or whenever the user says "initialize Hermes". Idempotent — never overwrites a hand-edited SOUL.md or pre-existing skill symlink; per-profile model config is authoritative and re-applied to converge; profile configs that already declare `custom_providers:` are left alone.
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

3. **Create the four scientia agent profiles.** Hermes profiles are
   *directories* (created by `hermes profile create`), not loose
   `.md` files. For each name in
   `scientia-{implementer,reviewer,integrator,aggregator}`:

   ```bash
   if ! hermes profile show "$name" >/dev/null 2>&1; then
     hermes profile create "$name" --no-alias
   fi
   ```

   `--no-alias` skips writing a `~/.local/bin/<name>` wrapper script;
   these profiles are spawn-only, not user-facing. `profile create`
   scaffolds `~/.hermes/profiles/<name>/` with `config.yaml`, `.env`,
   `SOUL.md`, `skills/`, `sessions/`, etc.

   Then overwrite the auto-generated `SOUL.md` with the scientia
   profile body from this skill's `assets/profiles/` directory
   (resolved relative to the skill's on-disk location, e.g.
   `~/.agents/skills/scientia/skills/scientia-kanban-init/assets/profiles/`):

   ```bash
   cp "$ASSETS/profiles/$name.md" ~/.hermes/profiles/"$name"/SOUL.md
   ```

   **Idempotency.** If `SOUL.md` already exists and its sha256 differs
   from the asset's sha256, **do not overwrite** — log
   `profile-already-present` to `development/log.md` and continue
   (the user may have hand-edited). To force an overwrite (e.g.,
   after upgrading scientia), the user must explicitly remove the
   existing `SOUL.md` first: `rm ~/.hermes/profiles/$name/SOUL.md`
   and re-run this skill.

3b. **Apply per-profile model config (optional).** Read
   `development/config.yaml` for `hermes.profiles`. The block is keyed
   by scientia *role* (`implementer`, `reviewer`, `integrator`,
   `aggregator`) and mirrors Hermes' per-profile config schema 1:1 (see
   `references/profile-models.md` for the full key reference, or
   https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models).

   If the block is absent, scientia touches no model config — every
   profile inherits Hermes' host-level defaults. Log
   `model-config-skipped — reason=hermes.profiles-absent` to
   `development/log.md` and skip to step 4.

   **`custom:<name>` propagation.** Per Hermes' documented profile
   isolation, profile configs do not inherit `custom_providers:` from
   `~/.hermes/config.yaml`. Before applying scalar leaves, the script
   scans each role's declared block for `custom:<name>` references
   (under `model.provider`, `auxiliary.<task>.provider`, or
   `model_aliases.<alias>.provider`) and, for each name found, copies
   the matching host `custom_providers` entry into the profile's own
   `~/.hermes/profiles/<name>/config.yaml`. Idempotent: a profile
   whose config already contains `custom_providers:` is left alone
   (treated as user-managed) and logged as
   `custom-providers-already-present`. Successful propagation is
   logged as:

   ```
   - <ISO-Z> — scientia-kanban-init — custom-providers-propagated — — profile=<role>(<resolved-name>) providers=<csv>
   ```

   Per-profile `.env` files are *not* touched — the API key that backs
   each custom provider is your domain (set it in
   `~/.hermes/profiles/<name>/.env`, `~/.hermes/.env`, or your shell
   environment). Built-in providers (`anthropic`, `openrouter`, etc.)
   need no propagation and resolve directly in profile context.

   If present, for each declared role:

   ```bash
   python3 "$BUNDLE_ROOT/skills/scientia-kanban-init/scripts/apply_profile_models.py" \
     --repo-root "$REPO_ROOT"
   ```

   The script flattens each declared block to dotted-key leaves
   (e.g. `model.default`, `auxiliary.vision.provider`,
   `model_aliases.fav.model`), reads the profile's current effective
   values via `hermes -p <resolved-name> config show --json`, and runs
   `hermes -p <resolved-name> config set <key> <value>` only for leaves
   that don't already match. **scientia config is authoritative** — any
   hand-edit to `~/.hermes/profiles/<name>/config.yaml` that disagrees
   with `hermes.profiles` is overwritten when the script runs.

   **Idempotency.** Re-running is safe: keys already at their declared
   values are no-ops. Per-role lines are appended to
   `development/log.md`:

   ```
   - <ISO-Z> — scientia-kanban-init — model-config-applied — — profile=<role>(<resolved-name>) applied=<N> unchanged=<M>
   ```

   **On failure.** If `hermes config set` returns non-zero for any leaf
   (invalid model string, provider not configured, etc.), the script
   aborts with the failing key + Hermes' stderr surfaced verbatim. Fix
   the value in `development/config.yaml` and re-run; partial
   application is acceptable because the next run reconciles.

   `scientia-kanban-emit` runs the same comparison as a preflight gate
   and refuses to emit on drift — so any divergence after this step is
   surfaced before workers spawn.

3c. **Verify API keys reach worker context.** When any role in
   `hermes.profiles` references `custom:<name>`, the matching host
   `custom_providers` entry has a `key_env` (e.g. `FIREWORKS_API_KEY`).
   For a spawned worker to authenticate, that var must be set in at
   least one of: the current process env, `~/.hermes/.env`, or the
   profile's own `~/.hermes/profiles/<resolved-name>/.env`. Run:

   ```bash
   python3 "$BUNDLE_ROOT/skills/scientia-kanban-init/scripts/check_env_keys.py" \
     --repo-root "$REPO_ROOT"
   ```

   Exit 0 means every required key is reachable. Exit 1 prints a
   refusal naming each missing var and which profile(s) need it; the
   skill must refuse to mark init complete. Remediation is one of:
   set the var in your shell, add it to `~/.hermes/.env`, or add it
   to `~/.hermes/profiles/<name>/.env`. scientia does not write
   secrets — these edits are the user's.

   Keyless custom providers (no `key_env` in the host entry) are
   skipped. Built-in providers (`anthropic`, `openrouter`, …) handle
   their own key resolution and are not part of this gate.

3d. **Optional — the job-hunt browser profile.** Run this step **only**
   when `development/config.yaml` contains a `jobhunt:` block (the
   optional job-hunt browser-automation sub-loop). When the block is
   absent, skip entirely — nothing here runs and existing repos are
   unaffected.

   When present:

   - **Create the fifth profile** the same way as the four above:

     ```bash
     name=scientia-jobhunt-agent
     if ! hermes profile show "$name" >/dev/null 2>&1; then
       hermes profile create "$name" --no-alias
     fi
     cp "$ASSETS/profiles/$name.md" ~/.hermes/profiles/"$name"/SOUL.md
     ```

     Same sha256 idempotency guard as step 3 — never overwrite a
     hand-edited `SOUL.md`. The profile name honours
     `hermes.profile_names.jobhunt` if the user overrode it.

   - **Symlink the scientia skills** into the profile-local tree (step 4
     also covers this if you add `scientia-jobhunt-agent` to its profile
     loop; doing it here keeps the optional path self-contained):

     ```bash
     PROFILE_SKILLS=~/.hermes/profiles/scientia-jobhunt-agent/skills
     mkdir -p "$PROFILE_SKILLS"
     for skill in "$BUNDLE_ROOT"/skills/scientia-*; do
       name=$(basename "$skill")
       [ -e "$PROFILE_SKILLS/$name" ] || ln -s "$skill" "$PROFILE_SKILLS/$name"
     done
     ```

   - **Enable the browser toolset** (idempotent):

     ```bash
     python3 "$BUNDLE_ROOT/skills/scientia-kanban-init/scripts/apply_browser_toolset.py" \
       --repo-root "$REPO_ROOT"
     ```

     This appends `browser` to the profile's `toolsets`. If Hermes
     rejects the write, the script refuses and prints the manual
     fallback (`hermes setup tools` → Browser Automation, then confirm
     with `hermes -p scientia-jobhunt-agent config show --json`). Which
     browser backend and its credentials (a logged-in Chrome over CDP, a
     Browserbase key, a Camofox URL) are yours to configure via
     `hermes setup tools` / `~/.hermes/.env` — scientia only ensures the
     toolset is on.

   - **Preflight the provider reachability** (refuse init on failure):

     ```bash
     python3 "$BUNDLE_ROOT/skills/scientia-kanban-init/scripts/check_browser_provider.py" \
       --repo-root "$REPO_ROOT"
     ```

     For `provider: cdp` this checks the `cdp_endpoint` answers (launch
     Chrome with `--remote-debugging-port=9222` first). For
     `camofox`/`browserbase`/etc. it checks the provider's API-key env
     var is reachable, mirroring step 3c.

   - **Model config** for the jobhunt profile is applied automatically by
     step 3b's `apply_profile_models.py` when `hermes.profiles.jobhunt`
     is declared (the `jobhunt` role resolves to `scientia-jobhunt-agent`).

   - **Smoke-test** that the profile resolves its worker skill:

     ```bash
     hermes -p scientia-jobhunt-agent skills list --source local \
       | grep -q scientia-jobhunt-worker \
       || { echo "jobhunt profile cannot resolve scientia-jobhunt-worker" >&2; exit 1; }
     ```

   Append `- <ISO-Z> — scientia-kanban-init — jobhunt-profile-ready — — profile=scientia-jobhunt-agent`
   to `development/log.md` on success.

4. **Install the scientia skills — both host-globally and per-profile.**
   Hermes resolves skill names in two independent places:

   - `~/.hermes/skills/<name>/` is the host-global tree. The
     `hermes kanban create --skill <name>` call in
     `scientia-kanban-emit` validates skill names against this tree
     before accepting a task.
   - `~/.hermes/profiles/<profile>/skills/<name>/` is the
     profile-local tree. When the dispatcher spawns a worker against
     a profile, that worker's skill loader reads from *its own*
     profile-local `skills/` directory — not the global tree. A
     scientia skill that exists only host-globally will pass the
     dispatcher's spawnable check but the worker process will exit
     immediately with
     `Error: Unknown skill(s): scientia-kanban-worker, scientia-grill`,
     and the task transitions to `blocked`. Recovery then requires
     `hermes kanban unblock <task-id>` — see
     `scientia-kanban-emit`'s "Recovery" section.

   Symlink **both** trees. `$BUNDLE_ROOT` is the scientia clone (e.g.
   `~/.agents/skills/scientia/`); resolve it relative to this
   `SKILL.md`'s on-disk location (`../../`).

   ```bash
   # 4a — host-global tree (for emit's --skill name validation):
   mkdir -p ~/.hermes/skills
   for skill in "$BUNDLE_ROOT"/skills/scientia-*; do
     name=$(basename "$skill")
     if [ ! -e ~/.hermes/skills/"$name" ]; then
       ln -s "$skill" ~/.hermes/skills/"$name"
     fi
   done

   # 4b — profile-local trees (for worker-time skill loading):
   for profile in scientia-implementer scientia-reviewer \
                  scientia-integrator scientia-aggregator; do
     PROFILE_SKILLS=~/.hermes/profiles/"$profile"/skills
     mkdir -p "$PROFILE_SKILLS"
     for skill in "$BUNDLE_ROOT"/skills/scientia-*; do
       name=$(basename "$skill")
       if [ ! -e "$PROFILE_SKILLS/$name" ]; then
         ln -s "$skill" "$PROFILE_SKILLS/$name"
       fi
     done
   done
   ```

   Verify with a profile-scoped listing (this is the canonical
   check — the host-global tree is necessary but not sufficient):

   ```bash
   hermes -p scientia-implementer skills list --source local \
     | grep scientia-kanban-worker
   ```

   You should see `scientia-kanban-worker` (and `scientia-grill`,
   and any other scientia skills you symlinked) reported as
   `enabled`. If this command returns empty, the profile-local
   symlinks are missing and workers will crash on spawn.

5. **Smoke-test.** Two stages — kanban.db reachability first, then
   per-profile skill resolution.

   **5a — kanban.db reachable.** Run `hermes kanban list --json` and
   verify it returns valid JSON (even if empty). If it errors,
   report and refuse to mark init complete.

   **5b — each profile resolves `scientia-kanban-worker`.** This
   catches the worker-spawn failure mode at init time rather than
   surfacing it later as `Unknown skill(s)` worker crashes (with
   tasks parked in `blocked`). For each of the four profiles:

   ```bash
   for profile in scientia-implementer scientia-reviewer \
                  scientia-integrator scientia-aggregator; do
     if ! hermes -p "$profile" skills list --source local \
            | grep -q scientia-kanban-worker; then
       echo "init smoke-test failed: $profile cannot resolve scientia-kanban-worker" >&2
       echo "fix: re-run step 4 (the profile-local symlink loop)" >&2
       exit 1
     fi
   done
   ```

   Refuse to mark init complete if any profile fails the check.

6. **Apply the concurrency cap — host *and* every profile.**
   `hermes.max_concurrent_children` in `development/config.yaml`
   (default `3`) maps to Hermes' `delegation.max_concurrent_children`
   (see https://hermes-agent.nousresearch.com/docs/guides/delegation-patterns#tuning-concurrency-and-depth
   — "parallel batch size per `delegate_task` call", default 3, range >=1).

   Hermes profiles are independent home directories, so writing the cap
   only to `~/.hermes/config.yaml` does **not** affect profile workers
   that sub-delegate (e.g., the integrator spawning a fixup task); each
   profile's own `config.yaml` controls its delegation depth. Without
   per-profile propagation, raising the host cap to 5 silently leaves
   integrator-spawned fixups capped at the profile default of 3. Run:

   ```bash
   python3 "$BUNDLE_ROOT/skills/scientia-kanban-init/scripts/apply_concurrency.py" \
     --repo-root "$REPO_ROOT"
   ```

   The script reads the declared cap, refuses with a clear message if
   it isn't a positive integer, then walks five targets — the host plus
   each scientia profile (`scientia-{implementer,reviewer,integrator,aggregator}`,
   or the names declared in `hermes.profile_names`). For each target it
   reads the effective `delegation.max_concurrent_children` via
   `hermes [-p <name>] config show --json` and runs
   `hermes [-p <name>] config set delegation.max_concurrent_children <N>`
   only when the value differs. Per-target lines land in
   `development/log.md`:

   ```
   - <ISO-Z> — scientia-kanban-init — concurrency-applied — — target=host N=<N> previous=<old>
   - <ISO-Z> — scientia-kanban-init — concurrency-applied — — target=<role>(<resolved-name>) N=<N> previous=<old>
   ```

   When a target already matches, the script logs
   `concurrency-already-set` instead and skips the write.

   **Host-vs-repo scope.** `~/.hermes/config.yaml` is host-global;
   `development/config.yaml` is per-repo. If you run scientia from
   multiple repos with different `hermes.max_concurrent_children`
   values, the most recent `scientia-kanban-init` (or manual
   `hermes config set`) wins. `scientia-kanban-emit` will refuse a
   repo whose value drifts from the host's setting, so the conflict
   is always surfaced — but resolution is manual. If you edit
   `hermes.max_concurrent_children` later, re-run `scientia-kanban-init`
   to apply, or `scientia-kanban-emit` will refuse with the drift reason.

7. **Verify the Hermes gateway is running.** The kanban dispatcher —
   the thing that polls `kanban.db` and spawns worker processes — only
   ticks while the gateway is up. This is the design today:
   `~/.hermes/config.yaml` sets `kanban.dispatch_in_gateway: true` with
   a `dispatch_interval_seconds: 60` cadence, and `hermes kanban
   daemon` is deprecated in favor of the gateway.

   Read `~/.hermes/processes.json`. If it contains no entry with
   `kind: gateway` (or equivalent), **refuse to mark init complete**
   and tell the user to start it themselves (scientia does not spawn
   long-running processes). The recommended path uses Hermes' built-in
   service installer:

   ```bash
   hermes gateway install   # one-time: writes the launchd (macOS) /
                            # systemd user (Linux) service definition
   hermes gateway start     # starts the now-installed service
   hermes gateway status    # confirms it's up
   ```

   The service survives logout/reboot and is restarted automatically
   by `hermes update`. Use `hermes gateway {stop,restart,uninstall}`
   to manage it after.

   Alternatives — only when a service manager isn't available or
   appropriate:

   - `hermes gateway run` — foreground process, documented as the
     recommended option for WSL, Docker, and Termux. Common pattern:
     run it inside `tmux`/`screen`.
   - `nohup hermes gateway start > ~/.hermes/logs/gateway.log 2>&1 &`
     — manual backgrounding. Works, but doesn't survive logout/reboot
     and doesn't auto-restart on crash.

   Re-run `scientia-kanban-init` once the gateway is up.

8. **Append to `development/log.md`**:

   ```bash
   printf '%s\n' '- YYYY-MM-DDTHH:MM:SSZ — scientia-kanban-init — host-ready — — profiles=4 kanban_db=<path> max_concurrent=<N>' >> development/log.md
   ```

9. **Report ready.** The host is now ready to run
   `scientia-kanban-emit` for any tenant.

## What this skill never does

- Creates kanban tasks. Emission is `scientia-kanban-emit`.
- Modifies `kanban.db` schema. The schema is owned by Hermes.
- Touches per-repo `development/`, `openspec/`, or `wiki/` (other than
  appending to `development/log.md`).
- Spawns the Hermes gateway. The user starts it themselves; this skill
  only refuses to mark the host ready until the gateway is running.
- Validates model strings against providers. `hermes config set`
  validates as much as Hermes itself does; everything beyond that
  (e.g., whether the chosen model exists on the chosen provider with
  the configured credentials) is the provider's call at first use.
- Manages provider credentials. `.env` files under
  `~/.hermes/profiles/<name>/` are the user's domain; scientia stays
  out of secret material.
