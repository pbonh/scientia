#!/usr/bin/env python3
"""manifest_build.py — build a core manifest for a new scientia change.

Given a tenant, change-id, and description, walks the wiki and writes
development/manifests/<tenant>/<change-id>/core.md.

Usage:
    manifest_build.py --repo <path> --tenant <slug> --change-id <id>
                      --description "..." [--capabilities a,b,c]
                      [--allow-dirty]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)",
                          re.MULTILINE | re.DOTALL)
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def first_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    m = re.search(r"^[^.\n]+[.\n]", text, re.MULTILINE)
    return (m.group(0) if m else text.split("\n", 1)[0]).strip().rstrip(".")


def git_rev(repo: Path) -> tuple[str, bool]:
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo, text=True
        ).strip()
        return rev, bool(status)
    except Exception:
        return "(no-git)", True


def read_context_page(wiki: Path, tenant: str) -> str:
    path = wiki / "contexts" / f"{tenant}.md"
    if not path.exists():
        raise FileNotFoundError(f"no context page for tenant {tenant!r} at {path}")
    return path.read_text(encoding="utf-8")


def parse_wiki_links(section_text: str) -> list[str]:
    return [m.group(1).split("#", 1)[0].strip()
            for m in WIKILINK_RE.finditer(section_text)]


def concept_synopsis(wiki: Path, slug: str) -> str:
    # slug like "concepts/aggregate"
    p = wiki / (slug + ".md")
    if not p.exists():
        return f"(missing page: {slug})"
    text = p.read_text(encoding="utf-8", errors="ignore")
    defn = section(text, "Definition")
    return first_sentence(defn) or "(no definition)"


def entity_synopsis(wiki: Path, slug: str) -> str:
    p = wiki / (slug + ".md")
    if not p.exists():
        return f"(missing page: {slug})"
    text = p.read_text(encoding="utf-8", errors="ignore")
    overview = section(text, "Overview")
    return first_sentence(overview) or "(no overview)"


def find_related_summaries(wiki: Path, scope_concepts: list[str]) -> list[tuple[str, str]]:
    summaries_dir = wiki / "summaries"
    if not summaries_dir.is_dir():
        return []
    out: list[tuple[str, str]] = []
    scope_set = {c.lower() for c in scope_concepts}
    for s in sorted(summaries_dir.glob("*.md")):
        text = s.read_text(encoding="utf-8", errors="ignore")
        relevant = section(text, "Relevant Concepts")
        if not relevant:
            continue
        cited = parse_wiki_links(relevant)
        cited_set = {c.lower() for c in cited}
        if scope_set & cited_set:
            fm = parse_frontmatter(text)
            title = fm.get("title", s.stem)
            out.append((str(s.relative_to(wiki).with_suffix("")), title))
    return out


def build(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    wiki = repo / "wiki"

    ctx_text = read_context_page(wiki, args.tenant)
    ctx_fm = parse_frontmatter(ctx_text)

    in_scope_concepts_section = section(ctx_text, "In-Scope Concepts")
    in_scope_entities_section = section(ctx_text, "In-Scope Entities")
    glossary_section = section(ctx_text, "Ubiquitous Language (Glossary)") \
                       or section(ctx_text, "Ubiquitous Language")
    false_cognates_section = section(ctx_text, "False Cognates with Adjacent Contexts")
    boundary_section = section(ctx_text, "Boundary")
    subdomain_section = section(ctx_text, "Subdomain Classification")

    in_scope_concepts = parse_wiki_links(in_scope_concepts_section)
    in_scope_entities = parse_wiki_links(in_scope_entities_section)

    rev, dirty = git_rev(repo)
    if dirty and not args.allow_dirty:
        print("scientia-wiki-bind: wiki has uncommitted changes; "
              "commit first or pass --allow-dirty", file=sys.stderr)
        return 1

    today = dt.date.today().isoformat()

    out_dir = repo / "development" / "manifests" / args.tenant / args.change_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "core.md"

    if out_path.exists():
        print(f"scientia-wiki-bind: core.md already exists at {out_path}; "
              f"re-bind by writing core-N.md alongside.", file=sys.stderr)
        return 1

    capabilities = [c.strip() for c in (args.capabilities or "").split(",") if c.strip()]

    body: list[str] = []
    body.append("---")
    body.append(f'title: "Core manifest — {args.tenant}/{args.change_id}"')
    body.append("type: manifest-core")
    body.append(f"tenant: {args.tenant}")
    body.append(f"change_id: {args.change_id}")
    body.append(f'description: "{args.description}"')
    body.append(f"capabilities: [{', '.join(capabilities)}]")
    body.append("scientia_schema: 1")
    body.append(f"wiki_snapshot: {rev}")
    body.append(f"wiki_dirty: {'true' if dirty else 'false'}")
    body.append(f"bundle_version: {args.bundle_version}")
    body.append(f"created: {today}")
    body.append("---")
    body.append("")
    body.append("## 1 — Domain Framing")
    body.append("")
    body.append(f"**Context:** [[contexts/{args.tenant}]] ({ctx_fm.get('title', args.tenant)})")
    body.append("")
    body.append("**Boundary:**")
    body.append("")
    body.append(boundary_section or "_(see context page)_")
    body.append("")
    body.append("**Subdomain Classification:**")
    body.append("")
    body.append(subdomain_section or "_(see context page)_")
    body.append("")

    body.append("## 2 — In-Scope Concepts")
    body.append("")
    if not in_scope_concepts:
        body.append("_(none declared on the context page)_")
    else:
        for slug in in_scope_concepts:
            body.append(f"- [[{slug}]] — {concept_synopsis(wiki, slug)}")
    body.append("")

    body.append("## 3 — In-Scope Entities")
    body.append("")
    if not in_scope_entities:
        body.append("_(none declared on the context page)_")
    else:
        for slug in in_scope_entities:
            body.append(f"- [[{slug}]] — {entity_synopsis(wiki, slug)}")
    body.append("")

    body.append("## 4 — Ubiquitous Language")
    body.append("")
    body.append(glossary_section or "_(no glossary on the context page)_")
    if false_cognates_section:
        body.append("")
        body.append("### False Cognates with Adjacent Contexts")
        body.append("")
        body.append(false_cognates_section)
    body.append("")

    body.append("## 7 — Related Prior Work")
    body.append("")
    summaries = find_related_summaries(wiki, in_scope_concepts)
    if not summaries:
        body.append("_(no related summaries found)_")
    else:
        for slug, title in summaries:
            body.append(f"- [[{slug}]] — {title}")
    body.append("")

    out_path.write_text("\n".join(body), encoding="utf-8")

    # Create the empty OpenSpec change directory.
    change_dir = repo / "openspec" / "changes" / f"{args.tenant}-{args.change_id}"
    change_dir.mkdir(parents=True, exist_ok=True)

    # Append to development/log.md.
    dev_log = repo / "development" / "log.md"
    if dev_log.exists():
        with dev_log.open("a", encoding="utf-8") as f:
            f.write(f"- {utc_now()} — scientia-wiki-bind — manifest-bound "
                    f"— {args.tenant}/{args.change_id} — wiki_snapshot={rev[:8]}\n")

    print(f"scientia-wiki-bind: wrote {out_path}")
    print(f"scientia-wiki-bind: created {change_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--change-id", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--capabilities", default="")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--bundle-version", default="0.1.0")
    args = ap.parse_args()
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
