#!/usr/bin/env python3
"""idempotency_key.py — compute scientia idempotency-key triples.

The triple:
- Parent key:           <spec-slug>:<adr-id>:<sha256(spec-body)>
- Per-scenario child:   <spec-slug>:<adr-id>:<scenario-slug>:<sha256(scenario-block)>
- Aggregator key:       <parent-key>:aggregator

The sha256 over the spec body excludes (a) YAML frontmatter and
(b) the auto-generated `## Kanban Tasks` section, otherwise emitting a
spec would change its own hash and create an infinite loop.

Usage:
    idempotency_key.py --spec <path-to-spec.md> --adr <ADR-NNNN>
                       [--scenario <slug>] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable


FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
KANBAN_SECTION_RE = re.compile(r"^## Kanban Tasks\b.*?(?=^## |\Z)",
                               re.MULTILINE | re.DOTALL)
SCENARIO_HEADING_RE = re.compile(r"^### Scenario:\s*(.+?)\s*$",
                                  re.MULTILINE)


def strip_for_hash(text: str) -> str:
    text = FRONTMATTER_RE.sub("", text, count=1)
    text = KANBAN_SECTION_RE.sub("", text)
    return text.strip()


def slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def hash_body(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def parent_key(spec_slug: str, adr_id: str, spec_text: str) -> str:
    return f"{spec_slug}:{adr_id}:{hash_body(strip_for_hash(spec_text))}"


def extract_scenarios(spec_text: str) -> list[tuple[str, str]]:
    """Return [(scenario-slug, scenario-block-text), ...]."""
    headings = list(SCENARIO_HEADING_RE.finditer(spec_text))
    scenarios: list[tuple[str, str]] = []
    for i, m in enumerate(headings):
        title = m.group(1)
        slug = slugify(title)
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(spec_text)
        block = spec_text[start:end].strip()
        scenarios.append((slug, block))
    return scenarios


def child_keys(spec_slug: str, adr_id: str, spec_text: str) -> list[tuple[str, str]]:
    """[(scenario-slug, child-key), ...]"""
    out: list[tuple[str, str]] = []
    for slug, block in extract_scenarios(spec_text):
        out.append((slug, f"{spec_slug}:{adr_id}:{slug}:{hash_body(block)}"))
    return out


def aggregator_key(parent: str) -> str:
    return f"{parent}:aggregator"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--adr", required=True, help="ADR-NNNN")
    ap.add_argument("--scenario", default=None,
                    help="If given, emit only this scenario's child key.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        print(f"spec not found: {spec_path}", file=sys.stderr)
        return 1

    text = spec_path.read_text(encoding="utf-8")
    spec_slug = spec_path.parent.name

    pk = parent_key(spec_slug, args.adr, text)
    children = child_keys(spec_slug, args.adr, text)
    agg = aggregator_key(pk)

    if args.scenario:
        match = next((c for s, c in children if s == args.scenario), None)
        if not match:
            print(f"scenario slug not found: {args.scenario}", file=sys.stderr)
            return 1
        print(match)
        return 0

    out = {
        "spec_slug": spec_slug,
        "adr_id": args.adr,
        "parent_key": pk,
        "aggregator_key": agg,
        "child_keys": [{"scenario_slug": s, "key": c} for s, c in children],
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"parent     {pk}")
        print(f"aggregator {agg}")
        for s, c in children:
            print(f"child  {s}  {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
