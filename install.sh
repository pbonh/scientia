#!/usr/bin/env bash
# install.sh — install the scientia bundle into a target repo.
#
# Usage:
#   ./install.sh <target-repo> [--client <name>] [--skills-path <abs>]
#                              [--no-profiles] [--force] [--upgrade] [--uninstall]
#
# See INSTALL.md for details.

set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_VERSION="$(grep -E '"version"' "$BUNDLE_ROOT/scientia.json" | head -1 | sed -E 's/.*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/')"

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

[[ $# -lt 1 ]] && usage

TARGET="$1"; shift
CLIENT="generic"
SKILLS_PATH=""
WITH_PROFILES=1
FORCE=0
MODE="install"  # install | upgrade | uninstall

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client)        CLIENT="$2"; shift 2 ;;
    --skills-path)   SKILLS_PATH="$2"; shift 2 ;;
    --no-profiles)   WITH_PROFILES=0; shift ;;
    --force)         FORCE=1; shift ;;
    --upgrade)       MODE="upgrade"; shift ;;
    --uninstall)     MODE="uninstall"; shift ;;
    -h|--help)       usage ;;
    *) echo "unknown flag: $1" >&2; usage ;;
  esac
done

[[ -d "$TARGET" ]] || { echo "target repo does not exist: $TARGET" >&2; exit 1; }
TARGET="$(cd "$TARGET" && pwd)"

# Resolve skills install path.
if [[ -z "$SKILLS_PATH" ]]; then
  case "$CLIENT" in
    opencode)    SKILLS_PATH="$TARGET/.opencode/skills" ;;
    claude-code) SKILLS_PATH="$TARGET/.claude/skills" ;;
    cursor)      SKILLS_PATH="$TARGET/.cursor/skills" ;;
    generic)     SKILLS_PATH="$TARGET/.agents/skills" ;;
    *) echo "unknown client: $CLIENT (use --skills-path to override)" >&2; exit 1 ;;
  esac
fi

BREADCRUMB="$TARGET/.scientia-install.json"

log() { printf "  %s\n" "$*"; }
say() { printf "scientia: %s\n" "$*"; }

write_breadcrumb() {
  cat > "$BREADCRUMB" <<EOF
{
  "bundle_version": "$BUNDLE_VERSION",
  "scientia_schema_version": 1,
  "client": "$CLIENT",
  "skills_path": "$SKILLS_PATH",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
}

copy_skill() {
  local skill="$1"
  local src="$BUNDLE_ROOT/skills/$skill"
  local dst="$SKILLS_PATH/$skill"
  if [[ ! -d "$src" ]]; then
    log "skip $skill (not present in bundle)"
    return
  fi
  if [[ -d "$dst" && $FORCE -eq 0 ]]; then
    # Refresh anything that hasn't been hand-edited (no robust diff here — best-effort).
    log "refresh $skill -> $dst"
  else
    log "install $skill -> $dst"
  fi
  mkdir -p "$dst"
  # Use rsync if available for safer copy; fall back to cp -R.
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$src/" "$dst/"
  else
    rm -rf "$dst"
    cp -R "$src" "$dst"
  fi
}

install_skills() {
  mkdir -p "$SKILLS_PATH"
  # Enumerate skills from scientia.json (poor-man's JSON parse: pull quoted entries between "skills": [ ... ]).
  local skills
  skills=$(awk '/"skills":/{flag=1;next} flag && /]/{flag=0} flag' "$BUNDLE_ROOT/scientia.json" \
           | sed -E 's/.*"([a-z][a-z0-9-]*)".*/\1/' | grep -E '^[a-z]')
  for s in $skills; do
    copy_skill "$s"
  done
}

install_profiles() {
  [[ $WITH_PROFILES -eq 0 ]] && { log "skipping Hermes profiles (--no-profiles)"; return; }
  local src="$BUNDLE_ROOT/skills/scientia-kanban-init/assets/profiles"
  local dst="$HOME/.hermes/profiles"
  if [[ ! -d "$src" ]]; then
    log "skip profiles (not present in bundle)"
    return
  fi
  mkdir -p "$dst"
  for p in "$src"/*.md; do
    [[ -e "$p" ]] || continue
    local name; name="$(basename "$p")"
    if [[ -e "$dst/$name" && $FORCE -eq 0 ]]; then
      log "profile $name already present (use --force to overwrite)"
    else
      cp "$p" "$dst/$name"
      log "install profile $name -> $dst/"
    fi
  done
}

uninstall_skills() {
  local skills
  skills=$(awk '/"skills":/{flag=1;next} flag && /]/{flag=0} flag' "$BUNDLE_ROOT/scientia.json" \
           | sed -E 's/.*"([a-z][a-z0-9-]*)".*/\1/' | grep -E '^[a-z]')
  for s in $skills; do
    if [[ -d "$SKILLS_PATH/$s" ]]; then
      rm -rf "$SKILLS_PATH/$s"
      log "removed $SKILLS_PATH/$s"
    fi
  done
  if [[ -e "$BREADCRUMB" ]]; then
    rm "$BREADCRUMB"
    log "removed $BREADCRUMB"
  fi
}

run_migrations() {
  local mig_dir="$BUNDLE_ROOT/skills/scientia/scripts/migrations"
  [[ -d "$mig_dir" ]] || return 0
  local from="unknown"
  if [[ -e "$BREADCRUMB" ]]; then
    from=$(grep -E '"bundle_version"' "$BREADCRUMB" | sed -E 's/.*"([0-9.]+)".*/\1/' || echo "unknown")
  fi
  say "running migrations from $from to $BUNDLE_VERSION"
  for m in "$mig_dir"/*.py; do
    [[ -e "$m" ]] || continue
    log "migration: $(basename "$m")"
    python3 "$m" "$TARGET" || { echo "migration failed: $m" >&2; exit 1; }
  done
}

case "$MODE" in
  install)
    say "installing scientia $BUNDLE_VERSION into $TARGET (client=$CLIENT)"
    install_skills
    install_profiles
    write_breadcrumb
    say "done. Activate the 'scientia' skill in your client and start with: 'Initialize this repository for scientia.'"
    ;;
  upgrade)
    say "upgrading scientia in $TARGET to $BUNDLE_VERSION"
    install_skills
    install_profiles
    run_migrations
    write_breadcrumb
    say "upgrade complete."
    ;;
  uninstall)
    say "uninstalling scientia from $TARGET"
    uninstall_skills
    say "uninstall complete. (raw/, wiki/, development/, openspec/ left intact.)"
    ;;
esac
