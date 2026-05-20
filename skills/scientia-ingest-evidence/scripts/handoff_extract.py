#!/usr/bin/env python3
"""handoff_extract.py — parse a kanban task's Required Handoff block.

Reads a markdown document (typically the task's latest completion
comment) and extracts the structured fields defined in
scientia-kanban-emit/references/HANDOFF_SCHEMA.md.

Usage:
    handoff_extract.py --task-file <path> [--json]
    handoff_extract.py --stdin [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_FIELDS = [
    "summary", "verification", "changed_files", "dependencies",
    "blocked_reason", "retry_notes", "residual_risk", "branch_head",
    "wiki_spec", "wiki_adr_ids",
]
LIST_FIELDS = {"changed_files", "dependencies", "wiki_adr_ids"}

FIELD_LABEL_RE = re.compile(
    r"^\s*-?\s*\*\*([a-z_]+)\*\*\s*[\u2014:\-]\s*(.*?)\s*$"
)
YAML_FENCE_RE = re.compile(r"^\s*```(?:yaml|yml)?\s*$")


def extract_handoff_section(text: str) -> str:
    m = re.search(r"^##\s*Required Handoff\s*\n(.*?)(?=^##\s|\Z)",
                  text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_inline_list(value: str) -> list[str] | None:
    """Parse an inline YAML-ish list like '[a, b, c]'. Returns None if not a list."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inside = value[1:-1].strip()
        if not inside:
            return []
        return [s.strip().strip('"').strip("'") for s in inside.split(",")]
    return None


def parse_yaml_list_block(yaml_text: str, key: str) -> list[str] | None:
    """Extract a list under a given key from a small YAML snippet."""
    pattern = re.compile(
        rf"^\s*{re.escape(key)}:\s*\n((?:\s*-\s+.+\n?)+)",
        re.MULTILINE,
    )
    m = pattern.search(yaml_text)
    if not m:
        return None
    items: list[str] = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        item = line[1:].strip().strip('"').strip("'")
        items.append(item)
    return items


def parse_handoff(text: str) -> dict:
    section = extract_handoff_section(text)
    if not section:
        return {"_error": "no `## Required Handoff` section found"}

    result: dict = {f: None for f in REQUIRED_FIELDS}

    # 1) Field-label pass: capture every "**field** — value" pair.
    pending_list_field: str | None = None
    for line in section.splitlines():
        if YAML_FENCE_RE.match(line):
            continue  # YAML fences are handled in the YAML pass below.

        m = FIELD_LABEL_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if key not in REQUIRED_FIELDS:
            continue

        if key in LIST_FIELDS:
            inline = parse_inline_list(value)
            if inline is not None:
                result[key] = inline
            elif value.lower() in ("none", "", "[]"):
                result[key] = []
            else:
                # Mark for resolution from a following YAML block.
                pending_list_field = key
        else:
            # Non-list scalar fields: empty value is still an answer.
            result[key] = value

    # 2) YAML-block pass: each ```yaml ... ``` may carry a list for any LIST_FIELDS key.
    for fence_match in re.finditer(
        r"```(?:yaml|yml)?\s*\n(.*?)\n\s*```",
        section, re.DOTALL,
    ):
        block = fence_match.group(1)
        for key in LIST_FIELDS:
            items = parse_yaml_list_block(block, key)
            if items is not None and (result.get(key) in (None, [])):
                result[key] = items

    # 3) Final defaults: any list field still None becomes [].
    for key in LIST_FIELDS:
        if result[key] is None:
            result[key] = []

    missing = [f for f in REQUIRED_FIELDS if result.get(f) is None]
    if missing:
        result["_missing"] = missing
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-file")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.stdin:
        text = sys.stdin.read()
    elif args.task_file:
        text = Path(args.task_file).read_text(encoding="utf-8")
    else:
        ap.error("either --task-file or --stdin is required")
        return 2

    result = parse_handoff(text)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for k, v in result.items():
            print(f"{k}: {v}")

    return 0 if not result.get("_error") and not result.get("_missing") else 1


if __name__ == "__main__":
    sys.exit(main())
