#!/usr/bin/env python3
"""bootstrap.py — scaffold raw/, wiki/, development/, openspec/ in a target repo.

Idempotent. Safe to re-run. Will not overwrite user-edited files.

Usage:
    bootstrap.py [--repo <path>] [--bundle-version <semver>]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent  # skills/scientia-wiki-init/
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"
BUNDLE_ROOT = SKILL_ROOT.parent.parent                # the scientia bundle root


def detect_bundle_version() -> str:
    """Read scientia.json at the bundle root and return its version."""
    manifest = BUNDLE_ROOT / "scientia.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))["version"]
    except Exception:
        return "unknown"

# Directories to create (empty if no template).
DIRS = [
    "raw",
    "wiki/concepts",
    "wiki/entities",
    "wiki/summaries",
    "wiki/syntheses",
    "wiki/contexts",
    "wiki/context-maps",
    "wiki/decisions",
    "wiki/specs",
    "development/manifests",
    "development/tasks",
    "openspec/changes",
    "openspec/archive",
    "openspec/schemas/intent-driven",
]

# Templates to copy: relative path under assets/templates/ -> destination in repo.
TEMPLATES = {
    "AGENTS.md.tmpl":                           "AGENTS.md",
    "wiki/index.md.tmpl":                       "wiki/index.md",
    "wiki/log.md.tmpl":                         "wiki/log.md",
    "development/config.yaml.tmpl":             "development/config.yaml",
    "development/log.md.tmpl":                  "development/log.md",
    "openspec/config.yaml.tmpl":                "openspec/config.yaml",
    "openspec/schemas/intent-driven/schema.yaml.tmpl": "openspec/schemas/intent-driven/schema.yaml",
    "openspec/schemas/intent-driven/README.md.tmpl":   "openspec/schemas/intent-driven/README.md",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def substitute(text: str, mapping: dict[str, str]) -> str:
    for k, v in mapping.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--bundle-version", default=None,
                    help="Override bundle version (default: read from scientia.json)")
    args = ap.parse_args()
    if args.bundle_version is None:
        args.bundle_version = detect_bundle_version()

    repo = Path(args.repo).resolve()
    repo_name = repo.name
    today = dt.date.today().isoformat()
    mapping = {
        "repo_name": repo_name,
        "date": today,
        "now": utc_now(),
        "bundle_version": args.bundle_version,
    }

    log_lines: list[str] = []

    # 1) Create directories.
    for d in DIRS:
        target = repo / d
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            log_lines.append(f"created dir {d}/")

    # 2) Copy templates.
    for src_rel, dst_rel in TEMPLATES.items():
        src = TEMPLATE_ROOT / src_rel
        dst = repo / dst_rel
        if not src.exists():
            log_lines.append(f"WARNING template missing: {src_rel}")
            continue
        if dst.exists():
            log_lines.append(f"skipped (exists): {dst_rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")
        dst.write_text(substitute(text, mapping), encoding="utf-8")
        log_lines.append(f"wrote {dst_rel}")

    # 3) Append a bootstrap entry to development/log.md.
    dev_log = repo / "development" / "log.md"
    if dev_log.exists():
        with dev_log.open("a", encoding="utf-8") as f:
            f.write(f"- {utc_now()} — scientia-wiki-init — bootstrap-complete — bundle {args.bundle_version}\n")
        log_lines.append("appended bootstrap entry to development/log.md")

    print(f"scientia-wiki-init: scaffolded {repo}")
    for line in log_lines:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
