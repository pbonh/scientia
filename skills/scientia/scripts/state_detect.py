#!/usr/bin/env python3
"""state_detect.py — emit a JSON state report for the scientia pipeline.

Reads the target repo's on-disk artifacts (wiki/, development/, openspec/,
kanban.db via `hermes kanban`) and produces the JSON object documented in
skills/scientia/references/SKILL_MAP.md.

Usage:
    state_detect.py [--repo <path>] [--pretty]

Defaults: --repo $(pwd). Prints JSON to stdout.

This script is invoked by the orchestrator skill on activation. It is
read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

STAGE_ORDER = [
    "absent", "bound", "proposed", "specs", "design",
    "adr", "tasks", "verified", "emitted", "running", "done", "archived",
]


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

    return {
        "wiki_present": wiki_present,
        "openspec_present": openspec_present,
        "development_present": development_present,
        "hermes_available": hermes_available,
        "scientia_schema_version_repo": schema_repo,
        "scientia_schema_version_bundle": schema_bundle,
        "tenants": tenants,
        "lint_status": lint_status,
    }


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
            "kanban_status": detect_kanban_status(tenant, change_id),
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
    kstat = detect_kanban_status(tenant, change_id)
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
    body = reports[-1].read_text(encoding="utf-8", errors="ignore").lower()
    if "critical" in body:
        return "critical"
    if "warning" in body:
        return "warning"
    return "clean"


def detect_kanban_status(tenant: str, change_id: str) -> str:
    if shutil.which("hermes") is None:
        return "none"
    try:
        result = subprocess.run(
            ["hermes", "kanban", "list", "--tenant", tenant, "--format", "json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return "none"
        rows = json.loads(result.stdout or "[]")
    except Exception:
        return "none"
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


def scan_lint_status(repo_root: Path) -> str:
    # Surface latest scientia-wiki-lint report if present.
    log = repo_root / "development" / "log.md"
    if not log.exists():
        return "clean"
    try:
        body = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return "clean"
    # Look at the most recent lint entry (last 50 lines suffice).
    for line in reversed(body[-200:]):
        if "scientia-wiki-lint" in line:
            if "critical" in line.lower():
                return "critical"
            if "warning" in line.lower():
                return "warning"
            return "clean"
    return "clean"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    state = detect_repo(root)
    indent = 2 if args.pretty else None
    print(json.dumps(state, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
