#!/usr/bin/env python3
"""state_detect.py — emit a JSON state report for the scientia pipeline.

Reads the target repo's on-disk artifacts (wiki/, development/, openspec/,
kanban.db via `hermes kanban`) and produces the JSON object documented in
skills/scientia/references/SKILL_MAP.md.

Usage:
    state_detect.py [--repo <path>] [--pretty]

When `--repo` is omitted, the script self-locates the project root:

- If `$(pwd)` is inside the scientia skill bundle, the script exits 2
  with an error — the bundle is never a scientia project, and silently
  treating it as one is the bug that motivated this guard.
- Otherwise the script walks up from `$(pwd)` looking for a directory
  with `.git/`, `wiki/index.md`, `development/`, or `openspec/`. The
  first match wins; if none match, it falls back to `$(pwd)` (consistent
  with a fresh project before `scientia-wiki-init`).

Pass `--repo <path>` to bypass auto-detection entirely.

This script is invoked by the orchestrator skill on activation. It is
read-only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

STAGE_ORDER = [
    "absent", "bound", "proposed", "specs", "design",
    "adr", "tasks", "verified", "emitted", "running", "done", "archived",
]


def bundle_root() -> Path:
    # scripts/state_detect.py → scripts/ → bundle root (skills/scientia/).
    return Path(__file__).resolve().parent.parent


def is_inside_bundle(path: Path) -> bool:
    try:
        path.resolve().relative_to(bundle_root())
        return True
    except ValueError:
        return False


def has_scientia_markers(path: Path) -> bool:
    return (path / "wiki" / "index.md").exists() \
        or (path / "development").is_dir() \
        or (path / "openspec").is_dir()


def find_project_root(start: Path) -> Path | None:
    """Walk up from `start` to find a scientia project or git root.

    Returns the first ancestor (including `start` itself) with either
    scientia markers or a `.git` entry. Returns `None` if no match before
    the filesystem root.
    """
    start = start.resolve()
    for ancestor in [start, *start.parents]:
        if has_scientia_markers(ancestor) or (ancestor / ".git").exists():
            return ancestor
    return None


def detect_repo(root: Path) -> dict:
    wiki_present = (root / "wiki" / "index.md").exists()
    openspec_present = (root / "openspec" / "config.yaml").exists() \
                       or (root / "openspec").is_dir()
    development_present = (root / "development").is_dir()

    hermes_available = shutil.which("hermes") is not None

    schema_repo = read_schema_version(root / "development" / "config.yaml")
    schema_bundle = read_bundle_schema_version(root)

    tenants = scan_tenants(root)

    lint_status = scan_lint_status(root)

    state = {
        "wiki_present": wiki_present,
        "openspec_present": openspec_present,
        "development_present": development_present,
        "hermes_available": hermes_available,
        "scientia_schema_version_repo": schema_repo,
        "scientia_schema_version_bundle": schema_bundle,
        "tenants": tenants,
        "lint_status": lint_status,
    }

    # Optional job-hunt sub-loop. Absent artifacts => no `jobhunt` key =>
    # zero behavioural change for repos that never enabled the feature.
    jobhunt = detect_jobhunt(root)
    if jobhunt is not None:
        state["jobhunt"] = jobhunt

    return state


def read_schema_version(config_path: Path) -> int | None:
    if not config_path.exists():
        return None
    try:
        for line in config_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("scientia_schema_version:"):
                return int(line.split(":", 1)[1].strip())
    except Exception:
        return None
    return None


def read_bundle_schema_version(repo_root: Path) -> int | None:
    # Walk up to find scientia.json in the bundle, if invoked from within the bundle.
    here = Path(__file__).resolve()
    for ancestor in [here.parent, *here.parents]:
        candidate = ancestor / "scientia.json"
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return int(data.get("scientia_schema_version", 1))
            except Exception:
                pass
    return 1


def scan_tenants(repo_root: Path) -> dict:
    manifests_dir = repo_root / "development" / "manifests"
    if not manifests_dir.is_dir():
        return {}
    out: dict = {}
    for tenant_dir in sorted(manifests_dir.iterdir()):
        if not tenant_dir.is_dir():
            continue
        tenant = tenant_dir.name
        # `jobhunt` is the dedicated tenant of the optional browser sub-loop;
        # it has no OpenSpec manifest and must never register as a pipeline
        # tenant (which would make the orchestrator offer intent stages for
        # it). Guard defensively in case a stray dir appears here.
        if tenant == "jobhunt":
            continue
        # The single active change for a tenant is the most recently created subdir.
        changes = sorted([d for d in tenant_dir.iterdir() if d.is_dir()])
        if not changes:
            continue
        # Pick the youngest non-archived change.
        active = pick_active_change(repo_root, tenant, changes)
        if active is None:
            continue
        change_id = active.name
        stage = detect_stage(repo_root, tenant, change_id)
        out[tenant] = {
            "active_change": change_id,
            "stage": stage,
            "wiki_snapshot_resolves": wiki_snapshot_resolves(repo_root, active),
            "verify_status": detect_verify_status(repo_root, tenant, change_id),
            "kanban_status": detect_kanban_status(repo_root, tenant, change_id),
        }
    return out


def pick_active_change(repo_root: Path, tenant: str, changes: list[Path]) -> Path | None:
    archive_dir = repo_root / "openspec" / "archive"
    for ch in reversed(changes):
        if archive_dir.is_dir() and (archive_dir / f"{tenant}-{ch.name}").exists():
            continue
        return ch
    return None


def detect_stage(repo_root: Path, tenant: str, change_id: str) -> str:
    change_dir = repo_root / "openspec" / "changes" / f"{tenant}-{change_id}"
    manifest_dir = repo_root / "development" / "manifests" / tenant / change_id

    if not manifest_dir.exists():
        return "absent"
    if not (manifest_dir / "core.md").exists():
        return "absent"
    if not change_dir.exists():
        return "bound"
    if (change_dir / "proposal.md").exists() and not (change_dir / "specs").exists():
        return "proposed"
    if (change_dir / "specs").exists() and not (change_dir / "design.md").exists():
        return "specs"
    if (change_dir / "design.md").exists() and not has_any_adr(change_dir):
        return "design"
    if has_any_adr(change_dir) and not (change_dir / "tasks.md").exists():
        return "adr"
    if (change_dir / "tasks.md").exists() and not verify_report_exists(change_dir):
        return "tasks"
    if verify_report_exists(change_dir) and not kanban_emitted(repo_root, tenant, change_id):
        return "verified"
    kstat = detect_kanban_status(repo_root, tenant, change_id)
    if kstat == "running":
        return "running"
    if kstat == "done":
        return "done"
    if kstat in ("blocked", "mixed"):
        return "running"
    if kanban_emitted(repo_root, tenant, change_id):
        return "emitted"
    return "verified"


def has_any_adr(change_dir: Path) -> bool:
    adr_dir = change_dir / "adr"
    if not adr_dir.is_dir():
        return False
    return any(p.suffix == ".md" for p in adr_dir.iterdir())


def verify_report_exists(change_dir: Path) -> bool:
    return any(p.name.startswith("verify-") for p in change_dir.glob("verify-*.md"))


def kanban_emitted(repo_root: Path, tenant: str, change_id: str) -> bool:
    # The emit step records idempotency keys under the spec's `## Kanban Tasks` section
    # and writes index entries to development/tasks/<tenant>/<change-id>/.
    tasks_index = repo_root / "development" / "tasks" / tenant / change_id
    return tasks_index.is_dir() and any(tasks_index.iterdir())


def wiki_snapshot_resolves(repo_root: Path, manifest_dir: Path) -> bool:
    core = manifest_dir / "core.md"
    if not core.exists():
        return False
    snapshot = None
    try:
        for line in core.read_text(encoding="utf-8").splitlines():
            if line.startswith("wiki_snapshot:"):
                snapshot = line.split(":", 1)[1].strip().strip('"').strip("'")
                break
    except Exception:
        return False
    if not snapshot:
        return False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", snapshot + "^{commit}"],
            cwd=repo_root, capture_output=True, text=True, check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def detect_verify_status(repo_root: Path, tenant: str, change_id: str) -> str:
    change_dir = repo_root / "openspec" / "changes" / f"{tenant}-{change_id}"
    reports = sorted(change_dir.glob("verify-*.md")) if change_dir.exists() else []
    if not reports:
        return "pending"
    body = reports[-1].read_text(encoding="utf-8", errors="ignore")
    parsed = _parse_verify_frontmatter(body)
    worst = parsed.get("worst_severity")
    if worst == "critical":
        return "critical"
    if worst == "warning":
        return "warning"
    if worst in ("suggestion", "clean"):
        return "clean"
    # No worst_severity → try counts.*
    if "critical" in parsed or "warning" in parsed:
        if parsed.get("critical", 0) > 0:
            return "critical"
        if parsed.get("warning", 0) > 0:
            return "warning"
        return "clean"
    # Last resort for reports lacking structured frontmatter. Less reliable
    # (prose may legitimately mention "critical" or "warning"), but better
    # than nothing for handwritten reports.
    lower = body.lower()
    if "critical" in lower:
        return "critical"
    if "warning" in lower:
        return "warning"
    return "clean"


def _parse_verify_frontmatter(body: str) -> dict:
    """Extract `worst_severity` and `counts.*` values from a verify
    report's YAML frontmatter. Returns {} if no frontmatter is present.
    """
    lines = body.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict = {}
    in_counts = False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"\s*worst_severity:\s*([A-Za-z]+)\s*$", line)
        if m:
            out["worst_severity"] = m.group(1).lower()
            in_counts = False
            continue
        if re.match(r"\s*counts:\s*$", line):
            in_counts = True
            continue
        if in_counts:
            m = re.match(r"\s+(critical|warning|suggestion):\s*(\d+)\s*$", line)
            if m:
                out[m.group(1).lower()] = int(m.group(2))
                continue
            if line and not line.startswith((" ", "\t")):
                in_counts = False
    return out


def detect_kanban_status(repo_root: Path, tenant: str, change_id: str) -> str:
    if shutil.which("hermes") is None:
        return "none"
    # The per-task index at development/tasks/<tenant>/<change_id>/*.md
    # records the idempotency_key of every task emitted for this change.
    # That's the authoritative key set — use it to filter the kanban list
    # by exact `idempotency_key` match (substring matching on title/body
    # is too loose; e.g. `2026-05-21-add-refunds` would also match
    # `2026-05-21-add-refunds-v2`).
    keys = _read_change_idempotency_keys(repo_root, tenant, change_id)
    try:
        result = subprocess.run(
            ["hermes", "kanban", "list", "--tenant", tenant, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return "none"
        rows = json.loads(result.stdout or "[]")
    except Exception:
        return "none"
    if keys:
        rows = [
            r for r in rows
            if (r.get("idempotency_key") or r.get("key")) in keys
        ]
    else:
        # No index yet — fall back to substring on title+body. Less precise
        # but only relevant in legacy or partially-emitted states.
        rows = [r for r in rows if change_id in (r.get("title", "") + r.get("body", ""))]
    if not rows:
        return "none"
    statuses = {r.get("status") for r in rows}
    if "running" in statuses:
        return "running"
    if "blocked" in statuses:
        return "blocked"
    if statuses <= {"done", "archived"}:
        return "done"
    return "mixed"


def _read_change_idempotency_keys(repo_root: Path, tenant: str, change_id: str) -> set:
    """Collect idempotency keys recorded in this change's per-task index.

    `scientia-kanban-emit` writes `development/tasks/<tenant>/<change_id>/<task>.md`
    files containing an `idempotency_key: <key>` line. Returns the set of
    keys; empty set if the index doesn't exist yet.
    """
    tasks_dir = repo_root / "development" / "tasks" / tenant / change_id
    if not tasks_dir.is_dir():
        return set()
    keys = set()
    for md in tasks_dir.glob("*.md"):
        try:
            for line in md.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if s.startswith("idempotency_key:"):
                    k = s.split(":", 1)[1].strip().strip('"').strip("'")
                    if k:
                        keys.add(k)
                    break
        except Exception:
            continue
    return keys


_LINT_COUNT_RE = re.compile(r"\b(critical|warning)=(\d+)", re.IGNORECASE)


def scan_lint_status(repo_root: Path) -> str:
    # Surface latest scientia-wiki-lint report if present. Log entries look
    # like `... — scientia-wiki-lint — completed — — critical=0 warning=11 ...`,
    # so we parse the counts rather than substring-match (which would treat
    # `critical=0` as critical).
    log = repo_root / "development" / "log.md"
    if not log.exists():
        return "clean"
    try:
        body = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return "clean"
    for line in reversed(body[-200:]):
        if "scientia-wiki-lint" not in line:
            continue
        counts = {
            k.lower(): int(v) for k, v in _LINT_COUNT_RE.findall(line)
        }
        if counts:
            if counts.get("critical", 0) > 0:
                return "critical"
            if counts.get("warning", 0) > 0:
                return "warning"
            return "clean"
        # Fallback for older entries without explicit counts.
        lower = line.lower()
        if "critical" in lower:
            return "critical"
        if "warning" in lower:
            return "warning"
        return "clean"
    return "clean"


# ---------------------------------------------------------------------------
# Optional job-hunt sub-loop detection
# ---------------------------------------------------------------------------


def _jobhunt_enabled(root: Path) -> bool:
    """True when development/config.yaml has an uncommented top-level
    `jobhunt:` key."""
    cfg = root / "development" / "config.yaml"
    if not cfg.exists():
        return False
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if re.match(r"^jobhunt:\s*(#.*)?$", line):
                return True
    except Exception:
        return False
    return False


def _jobhunt_kanban(root: Path) -> tuple[str, int]:
    """Return (kanban_status, gated_count) for the `jobhunt` tenant.

    gated_count is the number of blocked tasks (proxy for form-fills parked
    awaiting human submit approval). Returns ("none", 0) without Hermes.
    """
    if shutil.which("hermes") is None:
        return "none", 0
    try:
        result = subprocess.run(
            ["hermes", "kanban", "list", "--tenant", "jobhunt", "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return "none", 0
        rows = json.loads(result.stdout or "[]")
    except Exception:
        return "none", 0
    if not rows:
        return "none", 0
    statuses = {r.get("status") for r in rows}
    gated = sum(1 for r in rows if r.get("status") == "blocked")
    if "running" in statuses:
        kstat = "running"
    elif "blocked" in statuses:
        kstat = "blocked"
    elif statuses <= {"done", "archived"}:
        kstat = "done"
    else:
        kstat = "mixed"
    return kstat, gated


def detect_jobhunt(root: Path) -> dict | None:
    """Detect the optional job-hunt sub-loop's state.

    Returns None when no job-hunt artifacts exist (so the emitted JSON has
    no `jobhunt` key and existing repos are unaffected). When present,
    returns {enabled, active_campaign, phase, kanban_status, gated_count}
    where phase ∈ none|briefed|emitted|running|gated|ingested.
    """
    jh_dev = root / "development" / "job-hunt"
    jh_wiki = root / "wiki" / "jobhunt"
    if not jh_dev.is_dir() and not jh_wiki.is_dir():
        return None

    briefs = jh_dev / "briefs"
    campaigns = sorted(d.name for d in briefs.iterdir() if d.is_dir()) \
        if briefs.is_dir() else []
    active = campaigns[-1] if campaigns else None

    tasks_root = jh_dev / "tasks"
    emitted = bool(active) and (tasks_root / active).is_dir() \
        and any((tasks_root / active).glob("*.md"))

    apps = jh_wiki / "applications"
    has_apps = apps.is_dir() and any(apps.glob("*.md"))

    kstat, gated = _jobhunt_kanban(root)

    # Surface the most actionable state first: a parked gate needs a human.
    if gated > 0 or kstat == "blocked":
        phase = "gated"
    elif kstat == "running":
        phase = "running"
    elif has_apps:
        phase = "ingested"
    elif emitted:
        phase = "emitted"
    elif active:
        phase = "briefed"
    else:
        phase = "none"

    return {
        "enabled": _jobhunt_enabled(root),
        "active_campaign": active,
        "phase": phase,
        "kanban_status": kstat,
        "gated_count": gated,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--repo",
        default=None,
        help="Path to the scientia project (default: auto-detect from cwd).",
    )
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    if args.repo is not None:
        root = Path(args.repo).resolve()
        if not (root / ".git").exists() \
                and not (root / "development").is_dir() \
                and not (root / "openspec").is_dir():
            print(
                f"warning: --repo {root} has no `.git/`, `development/`, "
                f"or `openspec/`. A bare `wiki/` is not enough — the path "
                f"may be a home/parent directory rather than the project "
                f"root. The scientia project root is the directory the "
                f"session was launched in (`pwd`), not anything inferred "
                f"from the skill bundle's location.",
                file=sys.stderr,
            )
    else:
        cwd = Path.cwd().resolve()
        if is_inside_bundle(cwd):
            print(
                "error: state_detect.py was invoked from inside the scientia "
                "skill bundle. The bundle is not a scientia project; running "
                "the script here will always report `wiki_present: false` "
                "even when your project has a fully initialized wiki.\n"
                "  Fix: run the script from your project directory without "
                "`cd`ing into the bundle, or pass --repo <project-path>.\n"
                f"  cwd:    {cwd}\n"
                f"  bundle: {bundle_root()}",
                file=sys.stderr,
            )
            return 2
        resolved = find_project_root(cwd)
        root = resolved if resolved is not None else cwd
        if resolved is not None and resolved != cwd:
            print(
                f"note: state_detect.py auto-detected project root {resolved} "
                f"(invoked from {cwd}). Pass --repo to silence.",
                file=sys.stderr,
            )

    state = detect_repo(root)
    indent = 2 if args.pretty else None
    print(json.dumps(state, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
