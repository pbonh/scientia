#!/usr/bin/env python3
"""rebuild_index.py — derive the job-hunt pipeline index from wiki frontmatter.

The wiki is the source of truth. This script reads every page under
`wiki/jobhunt/` and rebuilds `development/job-hunt/pipeline.(sqlite|yaml)`
from scratch — it is a pure function of the wiki and never writes back to
it. Because it always rebuilds in full, the index can never silently
drift; `gate_jobhunt()` in verify_all.py asserts that with `--check`.

Alongside the index file a `pipeline.sha256` sidecar is written holding the
sha256 of the canonical record set. `--check` recomputes that hash from the
current wiki and compares it to the sidecar, so the consistency check is
independent of the index file format (and of sqlite's non-deterministic
on-disk bytes).

Usage:
    rebuild_index.py [--repo-root <path>] [--format sqlite|yaml]
                     [--report] [--check]

Exit codes:
    0  index rebuilt (or, with --check, index matches the wiki)
    1  with --check: index is stale or missing (the only divergence signal)
    2  usage / IO error
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# Kept in sync with skills/scientia-jobhunt-ingest/references/STATUS_ENUM.md
FUNNEL_STAGES = ["applied", "screening", "interviewing", "offer", "accepted"]
ALL_STATUSES = ["draft", *FUNNEL_STAGES, "rejected", "withdrawn"]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
STATUS_LINE_RE = re.compile(
    r"^-\s*(?P<ts>\S+)\s*—\s*(?P<from>[^—]+?)\s*→\s*(?P<to>[^—]+?)\s*—\s*"
    r"(?P<source>[^—]+?)\s*—\s*(?P<note>.*)$"
)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar frontmatter only (matches scientia's other scripts)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def scalar(fm: dict, key: str, default=None):
    if key not in fm:
        return default
    v = unquote(fm[key])
    if v.lower() in ("null", "none", ""):
        return default
    return v


def strip_wikilink(v) -> str | None:
    if not v:
        return None
    v = unquote(str(v))
    m = re.match(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", v)
    return m.group(1).strip() if m else v


def section_body(text: str, heading: str) -> str:
    pat = re.compile(rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)",
                     re.MULTILINE | re.DOTALL)
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def parse_status_history(text: str) -> list[dict]:
    body = section_body(text, "Status History")
    out: list[dict] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        m = STATUS_LINE_RE.match(line)
        if not m:
            continue
        out.append({
            "at": m.group("ts").strip(),
            "from_status": m.group("from").strip().strip("()"),
            "to_status": m.group("to").strip(),
            "source": m.group("source").strip(),
            "note": m.group("note").strip(),
        })
    return out


def _iter_pages(d: Path):
    if not d.is_dir():
        return
    for p in sorted(d.glob("*.md")):
        yield p, p.read_text(encoding="utf-8", errors="ignore")


def build_records(repo: Path) -> dict:
    jh = repo / "wiki" / "jobhunt"

    applications: list[dict] = []
    status_history: list[dict] = []
    for p, text in _iter_pages(jh / "applications"):
        fm = parse_frontmatter(text)
        slug = p.stem
        status = scalar(fm, "status", "draft")
        history = parse_status_history(text)
        ever = {h["to_status"] for h in history} | {status}
        applications.append({
            "app_slug": slug,
            "title": scalar(fm, "title", slug),
            "company": strip_wikilink(scalar(fm, "company")),
            "posting": strip_wikilink(scalar(fm, "posting")),
            "status": status,
            "applied_at": scalar(fm, "applied_at"),
            "campaign_id": scalar(fm, "campaign_id"),
            "kanban_task_id": scalar(fm, "kanban_task_id"),
            "submit_task_id": scalar(fm, "submit_task_id"),
            "idempotency_key": scalar(fm, "idempotency_key"),
            "ever_statuses": sorted(ever),
            "wiki_page": str((jh / "applications" / p.name).relative_to(repo)),
        })
        for h in history:
            status_history.append({"app_slug": slug, **h})

    interviews: list[dict] = []
    for p, text in _iter_pages(jh / "interviews"):
        fm = parse_frontmatter(text)
        interviews.append({
            "slug": p.stem,
            "application": strip_wikilink(scalar(fm, "application")),
            "interview_type": scalar(fm, "interview_type"),
            "scheduled_at": scalar(fm, "scheduled_at"),
            "status": scalar(fm, "status", "scheduled"),
            "rating": scalar(fm, "rating"),
            "wiki_page": str((jh / "interviews" / p.name).relative_to(repo)),
        })

    contacts: list[dict] = []
    for p, text in _iter_pages(jh / "contacts"):
        fm = parse_frontmatter(text)
        contacts.append({
            "slug": p.stem,
            "company": strip_wikilink(scalar(fm, "company")),
            "name": scalar(fm, "name", p.stem),
            "role_in_process": scalar(fm, "role_in_process"),
            "wiki_page": str((jh / "contacts" / p.name).relative_to(repo)),
        })

    return {
        "applications": applications,
        "status_history": status_history,
        "interviews": interviews,
        "contacts": contacts,
    }


def canonical_hash(records: dict) -> str:
    payload = json.dumps(records, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ writers

def write_sqlite(records: dict, path: Path) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        cur = con.cursor()
        cur.executescript("""
            CREATE TABLE applications (
                app_slug TEXT PRIMARY KEY, title TEXT, company TEXT,
                posting TEXT, status TEXT, applied_at TEXT, campaign_id TEXT,
                kanban_task_id TEXT, submit_task_id TEXT, idempotency_key TEXT,
                wiki_page TEXT);
            CREATE TABLE status_history (
                app_slug TEXT, at TEXT, from_status TEXT, to_status TEXT,
                source TEXT, note TEXT);
            CREATE TABLE interviews (
                slug TEXT PRIMARY KEY, application TEXT, interview_type TEXT,
                scheduled_at TEXT, status TEXT, rating TEXT, wiki_page TEXT);
            CREATE TABLE contacts (
                slug TEXT PRIMARY KEY, company TEXT, name TEXT,
                role_in_process TEXT, wiki_page TEXT);
        """)
        cur.executemany(
            "INSERT INTO applications VALUES "
            "(:app_slug,:title,:company,:posting,:status,:applied_at,"
            ":campaign_id,:kanban_task_id,:submit_task_id,:idempotency_key,"
            ":wiki_page)",
            [{k: a.get(k) for k in (
                "app_slug", "title", "company", "posting", "status",
                "applied_at", "campaign_id", "kanban_task_id",
                "submit_task_id", "idempotency_key", "wiki_page")}
             for a in records["applications"]])
        cur.executemany(
            "INSERT INTO status_history VALUES "
            "(:app_slug,:at,:from_status,:to_status,:source,:note)",
            records["status_history"])
        cur.executemany(
            "INSERT INTO interviews VALUES "
            "(:slug,:application,:interview_type,:scheduled_at,:status,"
            ":rating,:wiki_page)",
            records["interviews"])
        cur.executemany(
            "INSERT INTO contacts VALUES "
            "(:slug,:company,:name,:role_in_process,:wiki_page)",
            records["contacts"])
        con.commit()
    finally:
        con.close()


def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_yaml_scalar(x) for x in v) + "]"
    s = str(v)
    return json.dumps(s, ensure_ascii=False)  # always-valid double-quoted scalar


def write_yaml(records: dict, path: Path) -> None:
    lines: list[str] = ["# Derived from wiki/jobhunt/ — do not edit by hand.",
                        "# Rebuild with scientia-jobhunt-index.", ""]
    for table in ("applications", "status_history", "interviews", "contacts"):
        lines.append(f"{table}:")
        rows = records[table]
        if not rows:
            lines[-1] = f"{table}: []"
            continue
        for row in rows:
            first = True
            for k, v in row.items():
                prefix = "  - " if first else "    "
                lines.append(f"{prefix}{k}: {_yaml_scalar(v)}")
                first = False
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ------------------------------------------------------------------ report

def _parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def build_report(records: dict) -> str:
    apps = records["applications"]
    total = len(apps)
    lines = ["# Job-hunt pipeline report", "",
             f"Total applications tracked: {total}", ""]

    # Current-status distribution.
    lines.append("## Current status distribution")
    by_status = {s: 0 for s in ALL_STATUSES}
    for a in apps:
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
    for s in ALL_STATUSES:
        if by_status.get(s):
            lines.append(f"- {s}: {by_status[s]}")
    lines.append("")

    # Funnel + conversion (based on stages ever reached).
    lines.append("## Funnel (stages ever reached) + conversion")
    reached = {s: sum(1 for a in apps if s in a["ever_statuses"])
               for s in FUNNEL_STAGES}
    prev = None
    for s in FUNNEL_STAGES:
        n = reached[s]
        if prev is not None and prev[1] > 0:
            rate = 100.0 * n / prev[1]
            lines.append(f"- {prev[0]} → {s}: {n}/{prev[1]} ({rate:.0f}%)")
        else:
            lines.append(f"- {s}: {n}")
        prev = (s, n)
    lines.append("")

    # Upcoming interviews.
    now = dt.datetime.now(dt.timezone.utc)
    upcoming = []
    for iv in records["interviews"]:
        when = _parse_ts(iv.get("scheduled_at"))
        if when and iv.get("status") == "scheduled":
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
            if when >= now:
                upcoming.append((when, iv))
    lines.append("## Upcoming interviews")
    if not upcoming:
        lines.append("- (none scheduled)")
    for when, iv in sorted(upcoming, key=lambda t: t[0]):
        lines.append(f"- {iv['scheduled_at']} — {iv.get('interview_type','?')} "
                     f"— {iv.get('application','?')}")
    lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ main

def index_paths(repo: Path, fmt: str) -> tuple[Path, Path]:
    base = repo / "development" / "job-hunt"
    name = "pipeline.sqlite" if fmt == "sqlite" else "pipeline.yaml"
    return base / name, base / "pipeline.sha256"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=os.getcwd())
    ap.add_argument("--format", choices=("sqlite", "yaml"), default="sqlite")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="Do not write; exit 1 if the on-disk index is stale.")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    records = build_records(repo)
    digest = canonical_hash(records)
    index_path, sha_path = index_paths(repo, args.format)

    if args.check:
        if not sha_path.exists():
            print(f"job-hunt index missing (no {sha_path.relative_to(repo)}); "
                  f"run scientia-jobhunt-index", file=sys.stderr)
            return 1
        on_disk = sha_path.read_text(encoding="utf-8").strip()
        if on_disk != digest:
            print("job-hunt index is stale relative to wiki/jobhunt/ "
                  f"(wiki={digest[:12]}…, index={on_disk[:12]}…); "
                  "re-run scientia-jobhunt-index", file=sys.stderr)
            return 1
        if args.report:
            print(build_report(records))
        return 0

    index_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "sqlite":
        write_sqlite(records, index_path)
    else:
        write_yaml(records, index_path)
    sha_path.write_text(digest + "\n", encoding="utf-8")
    print(f"scientia-jobhunt-index: wrote {index_path.relative_to(repo)} "
          f"({len(records['applications'])} applications)")

    if args.report:
        print()
        print(build_report(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
