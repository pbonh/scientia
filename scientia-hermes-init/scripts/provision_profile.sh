#!/usr/bin/env bash
# provision_profile.sh — the canonical, idempotent recipe for deploying ONE
# scientia Hermes profile. Every scientia profile is deployed the SAME WAY so
# the roster stays consistent (see scientia-hermes-init/SKILL.md):
#
#   1. plain `hermes profile create` — seeds the bundled skill set, which
#      includes devops/kanban-worker. The kanban dispatcher AUTO-LOADS
#      `kanban-worker` into every worker (`--skills kanban-worker`), so profiles
#      need NO scientia-specific worker skill. Do not symlink scientia-* skills
#      into a profile; they only dangle when the shared skills source moves.
#   2. a Fireworks custom-provider config.yaml carrying the profile's model.default
#      (the per-role model from references/config.yaml's hermes.profiles block).
#   3. a SOUL.md persona + <name>.md sidecar from a repo-tracked or init-generated
#      body file (e.g. scientia-conflict-resolver/SKILL.md, or a project-specific
#      SOUL.md composed by scientia-hermes-init from the project's C4/ADR/spec
#      artifacts). Omit for profiles without a body.
#   4. a description (used by the kanban decomposer to route by role).
#   5. a ~/.local/bin wrapper (so every profile is invokable the same way).
#   6. best-effort btrfs NOCOW on the profile dir (the kanban.db CoW-corruption
#      mitigation, generalized to per-profile state.db).
#
# Idempotent and non-clobbering: an existing config.yaml keeps its other keys;
# only model.default is reconciled. Re-running is safe. An existing SOUL.md is
# overwritten when a new body file is provided (so re-provisioning picks up
# updated project context).
#
# Profile names are now project-prefixed (e.g. circuit-solver-beta-implementer)
# so different boards can have different execution profiles on the same Hermes
# install. The prefix is resolved by scientia-hermes-init from the board slug
# or the profile_prefix config key.
#
# Usage:
#   provision_profile.sh <name> <full-model-id> [body.md] [description]
# Example:
#   provision_profile.sh circuit-solver-beta-implementer \
#     accounts/fireworks/models/glm-5p1 \
#     proposals/2026-05-28-csb/hermes/souls/circuit-solver-beta-implementer.md \
#     "Complete your work card when tests pass; do not self-block for review — the pipeline has a dedicated reviewer stage."
set -euo pipefail

NAME="${1:?profile name}"; MODEL="${2:?full model id, e.g. accounts/fireworks/models/glm-5p1}"
BODY="${3:-}"; DESC="${4:-}"
PROFILES_DIR="${HERMES_PROFILES_DIR:-$HOME/.hermes/profiles}"
PDIR="$PROFILES_DIR/$NAME"

# 1. Create the profile if missing (idempotent; seeds bundled skills).
if ! hermes profile list 2>/dev/null | grep -qE "[[:space:]]${NAME}[[:space:]]"; then
  if [ -n "$DESC" ]; then hermes profile create "$NAME" --description "$DESC"
  else hermes profile create "$NAME"; fi
fi

# 2. Fireworks custom-provider config + this profile's default model.
if [ ! -f "$PDIR/config.yaml" ]; then
  cat > "$PDIR/config.yaml" <<YAML
custom_providers:
- api_mode: chat_completions
  base_url: https://api.fireworks.ai/inference/v1
  key_env: FIREWORKS_API_KEY
  models:
    accounts/fireworks/models/deepseek-v4-pro:
      context_length: 384000
    accounts/fireworks/models/deepseek-v4-flash:
      context_length: 384000
    accounts/fireworks/models/glm-5p1:
      context_length: 131072
    accounts/fireworks/models/kimi-k2p6:
      context_length: 131072
    accounts/fireworks/models/minimax-m2p7:
      context_length: 131072
    accounts/fireworks/models/qwen3p6-plus:
      context_length: 131072
  name: fireworks
agent:
  max_turns: 150
model:
  default: $MODEL
  provider: custom:fireworks
delegation:
  max_concurrent_children: 3
YAML
else
  # Reconcile only model.default; preserve every other key.
  sed -i "s#^\(  default: \).*#\1$MODEL#" "$PDIR/config.yaml"
fi

# 3. Persona body (SOUL.md = runtime persona; <name>.md = sidecar definition).
#    Overwrite on re-provision so updated project context takes effect.
if [ -n "$BODY" ] && [ -f "$BODY" ]; then
  cp "$BODY" "$PDIR/SOUL.md"
  cp "$BODY" "$PROFILES_DIR/$NAME.md"
fi

# 4. Description (used by the kanban decomposer for role routing).
[ -n "$DESC" ] && hermes profile describe "$NAME" --text "$DESC" --overwrite >/dev/null 2>&1 || true

# 5. Wrapper script.
hermes profile alias "$NAME" >/dev/null 2>&1 || true

# 6. Best-effort btrfs NOCOW on the profile dir.
python3 - "$PDIR" <<'PY' 2>/dev/null || true
import array, fcntl, os, sys
GET, SET, NOCOW = 0x80086601, 0x40086602, 0x00800000
fd = os.open(sys.argv[1], os.O_RDONLY); buf = array.array('L', [0])
fcntl.ioctl(fd, GET, buf, True); buf[0] |= NOCOW; fcntl.ioctl(fd, SET, buf); os.close(fd)
PY

echo "provisioned: $NAME (model=$MODEL)"
