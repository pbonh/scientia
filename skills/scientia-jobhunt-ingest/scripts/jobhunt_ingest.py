#!/usr/bin/env python3
"""jobhunt_ingest.py — turn browser captures into wiki/jobhunt pages.

The browser→wiki seam of the optional job-hunt sub-loop. Reads the JSON
capture files written by scientia-jobhunt-agent workers under
development/job-hunt/captures/<campaign>/ (schema: references/CAPTURE_SCHEMA.md)
and upserts wiki/jobhunt/{companies,postings,applications,interviews,contacts}
pages. Application status transitions are append-only and validated against
STATUS_ENUM.md. Then regenerates the wiki/index.md "## Job-Hunt" section,
appends wiki/log.md lines, and rebuilds the pipeline analytics index.

Usage:
    jobhunt_ingest.py --campaign <id> [--repo-root <path>] [--no-index]

Exit: 0 ok (even with skipped illegal transitions, which are reported);
      2 usage/IO error.
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
from typing import Optional

# Canonical transition graph — kept in sync with
# scientia-jobhunt-ingest/references/STATUS_ENUM.md.
LEGAL_TRANSITIONS = {
    "draft":        {"applied", "withdrawn"},
    "applied":      {"screening", "interviewing", "offer", "rejected", "withdrawn"},
    "screening":    {"interviewing", "offer", "rejected", "withdrawn"},
    "interviewing": {"offer", "rejected", "withdrawn"},
    "offer":        {"accepted", "rejected", "withdrawn"},
    "accepted":     set(),
    "rejected":     set(),
    "withdrawn":    set(),
}
ALL_STATUSES = ["draft", "applied", "screening", "interviewing", "offer",
                "accepted", "rejected", "withdrawn"]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)

_THIS = Path(__file__).resolve()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return dt.date.today().isoformat()


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip().lower())
    return s.strip("-") or "unknown"


# --------------------------------------------------------------- page IO

def split_page(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict of top-level scalars, body text)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def render_page(fm_order: list[tuple[str, str]], body: str) -> str:
    lines = ["---"]
    for k, v in fm_order:
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body.lstrip("\n")


def _q(v) -> str:
    """Quote a frontmatter value when needed."""
    if v is None:
        return "null"
    s = str(v)
    if s == "":
        return '""'
    if re.search(r'[:#\[\]]', s) or s != s.strip():
        return '"' + s.replace('"', '\\"') + '"'
    return s


# --------------------------------------------------------------- upserts

def _merge_base_fm(existing: dict, page_type: str, title: str,
                   sources: list[str]) -> dict:
    created = existing.get("created") or today()
    src = existing.get("sources")
    if not src:
        src = "[" + ", ".join(_q(s) for s in sources) + "]"
    return {
        "title": title, "type": page_type,
        "tags": existing.get("tags") or f"[jobhunt, {page_type.split('-', 1)[1]}]",
        "created": created, "updated": today(),
        "sources": src, "confidence": existing.get("confidence") or "high",
    }


def _write(repo: Path, rel: str, fm_order, body, touched, verb):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    path.write_text(render_page(fm_order, body), encoding="utf-8")
    touched.append((rel, "updated" if existed else "created"))


def upsert_company(repo, cap, touched):
    slug = cap.get("company_slug") or slugify(cap.get("company", ""))
    rel = f"wiki/jobhunt/companies/{slug}.md"
    path = repo / rel
    existing, body = split_page(path.read_text(encoding="utf-8")) if path.exists() else ({}, "")
    base = _merge_base_fm(existing, "jobhunt-company",
                          cap.get("company", slug), [cap.get("url", "self")])
    fm = list(base.items()) + [
        ("careers_url", _q(cap.get("careers_url") or existing.get("careers_url", ""))),
        ("ats", cap.get("ats") or existing.get("ats", "unknown")),
        ("location", _q(cap.get("location") or existing.get("location", ""))),
    ]
    if not body.strip():
        body = "\n## Overview\n\n## Notes\n"
    _write(repo, rel, fm, body, touched, "company")
    return slug


def upsert_posting(repo, cap, touched):
    slug = cap.get("slug") or slugify(cap.get("role", "posting"))
    company_slug = cap.get("company_slug") or slugify(cap.get("company", ""))
    rel = f"wiki/jobhunt/postings/{slug}.md"
    path = repo / rel
    existing, body = split_page(path.read_text(encoding="utf-8")) if path.exists() else ({}, "")
    url = cap.get("url", "")
    base = _merge_base_fm(existing, "jobhunt-posting",
                          f"{cap.get('role', slug)} @ {cap.get('company', company_slug)}",
                          [url or "capture"])
    fm = list(base.items()) + [
        ("company", _q(f"[[jobhunt/companies/{company_slug}]]")),
        ("posting_url", _q(url)),
        ("posting_id", _q(cap.get("posting_id", ""))),
        ("role", _q(cap.get("role", slug))),
        ("location", _q(cap.get("location", ""))),
        ("comp", _q(cap.get("comp", ""))),
        ("source_board", cap.get("board") or existing.get("source_board", "other")),
        ("found_at", existing.get("found_at") or now_iso()),
    ]
    if not body.strip():
        body = "\n## Summary\n\n## Requirements\n\n## Nice-to-haves\n"
    _write(repo, rel, fm, body, touched, "posting")
    return slug


STATUS_LINE_HDR = "## Status History"


def _append_history(body: str, line: str) -> str:
    if STATUS_LINE_HDR in body:
        # Insert the line at the end of the Status History section.
        pat = re.compile(rf"({re.escape(STATUS_LINE_HDR)}\n)(.*?)(\n##\s|\Z)",
                         re.DOTALL)
        m = pat.search(body)
        if m:
            section = m.group(2).rstrip("\n")
            new_section = (section + "\n" + line).strip("\n")
            return body[:m.start(2)] + new_section + "\n" + body[m.end(2):]
    # No section yet — create one near the top of the body.
    return f"\n{STATUS_LINE_HDR}\n{line}\n\n## Notes\n" + body.lstrip("\n")


def upsert_application(repo, cap, campaign, touched, errors):
    slug = cap.get("slug") or cap.get("posting_slug") or slugify(cap.get("role", "app"))
    company_slug = cap.get("company_slug") or slugify(cap.get("company", ""))
    posting_slug = cap.get("posting_slug") or slug
    target = cap.get("status", "draft")
    if target not in ALL_STATUSES:
        errors.append(f"application {slug}: unknown status {target!r}")
        return None

    rel = f"wiki/jobhunt/applications/{slug}.md"
    path = repo / rel
    existing, body = split_page(path.read_text(encoding="utf-8")) if path.exists() else ({}, "")
    current = existing.get("status")

    transitions: list[tuple[str, str]] = []
    if current is None:
        transitions.append(("(none)", "draft"))
        cur = "draft"
    else:
        cur = current
    if target != cur:
        # Walk only a single hop; refuse if illegal.
        if target in LEGAL_TRANSITIONS.get(cur, set()):
            transitions.append((cur, target))
            cur = target
        else:
            errors.append(
                f"application {slug}: illegal transition {cur} → {target} "
                f"(see STATUS_ENUM.md); leaving status at {cur}")
            target = cur  # keep current

    # Apply history lines.
    for frm, to in transitions:
        src = "scientia-jobhunt-ingest"
        note = cap.get("note") or (cap.get("kanban_task_id") or "")
        body = _append_history(body, f"- {now_iso()} — {frm} → {to} — {src} — {note}")

    url = cap.get("url", "")
    base = _merge_base_fm(existing, "jobhunt-application",
                          f"Application — {cap.get('role', slug)} @ {cap.get('company', company_slug)}",
                          [url or "capture"])
    applied_at = existing.get("applied_at")
    if applied_at in (None, "", "null") and cur == "applied":
        applied_at = cap.get("applied_at") or now_iso()
    fm = list(base.items()) + [
        ("posting", _q(f"[[jobhunt/postings/{posting_slug}]]")),
        ("company", _q(f"[[jobhunt/companies/{company_slug}]]")),
        ("status", cur),
        ("applied_at", applied_at or "null"),
        ("campaign_id", _q(cap.get("campaign_id") or campaign)),
        ("kanban_task_id", _q(cap.get("kanban_task_id") or existing.get("kanban_task_id", ""))),
        ("submit_task_id", _q(cap.get("submit_task_id") or existing.get("submit_task_id", ""))),
        ("idempotency_key", _q(cap.get("idempotency_key")
                               or existing.get("idempotency_key")
                               or f"application:{company_slug}:{slug}")),
        ("resume_artifact", _q(cap.get("resume_artifact") or existing.get("resume_artifact", ""))),
        ("resume_sha256", _q(cap.get("resume_sha256") or existing.get("resume_sha256", "none"))),
        ("cover_letter_artifact", _q(cap.get("cover_letter_artifact") or existing.get("cover_letter_artifact", ""))),
        ("cover_letter_sha256", _q(cap.get("cover_letter_sha256") or existing.get("cover_letter_sha256", "none"))),
        ("preview_capture", _q(cap.get("screenshot_path") or existing.get("preview_capture", ""))),
    ]
    if STATUS_LINE_HDR not in body:
        body = f"\n{STATUS_LINE_HDR}\n\n## Notes\n" + body.lstrip("\n")
    _write(repo, rel, fm, body, touched, "application")
    return slug


def upsert_interview(repo, cap, touched):
    slug = cap.get("slug") or slugify(cap.get("interview_type", "interview"))
    app_slug = cap.get("application_slug") or "unknown"
    rel = f"wiki/jobhunt/interviews/{slug}.md"
    path = repo / rel
    existing, body = split_page(path.read_text(encoding="utf-8")) if path.exists() else ({}, "")
    base = _merge_base_fm(existing, "jobhunt-interview",
                          f"{cap.get('interview_type', 'interview')} — {app_slug}",
                          [cap.get("source", "capture")])
    fm = list(base.items()) + [
        ("application", _q(f"[[jobhunt/applications/{app_slug}]]")),
        ("interview_type", cap.get("interview_type") or existing.get("interview_type", "phone_screen")),
        ("scheduled_at", _q(cap.get("scheduled_at") or existing.get("scheduled_at", "null"))),
        ("format", cap.get("format") or existing.get("format", "video")),
        ("status", cap.get("status") or existing.get("status", "scheduled")),
        ("rating", cap.get("rating") or existing.get("rating", "null")),
    ]
    if not body.strip():
        body = "\n## Prep Notes\n\n## Feedback\n"
    _write(repo, rel, fm, body, touched, "interview")
    return slug


def upsert_contact(repo, cap, touched):
    slug = cap.get("slug") or slugify(cap.get("name", "contact"))
    company_slug = cap.get("company_slug") or slugify(cap.get("company", ""))
    rel = f"wiki/jobhunt/contacts/{slug}.md"
    path = repo / rel
    existing, body = split_page(path.read_text(encoding="utf-8")) if path.exists() else ({}, "")
    base = _merge_base_fm(existing, "jobhunt-contact",
                          f"{cap.get('name', slug)} — {cap.get('company', company_slug)}",
                          [cap.get("source", "capture")])
    fm = list(base.items()) + [
        ("company", _q(f"[[jobhunt/companies/{company_slug}]]")),
        ("name", _q(cap.get("name", slug))),
        ("role_in_process", cap.get("role_in_process") or existing.get("role_in_process", "other")),
        ("email", _q(cap.get("email") or existing.get("email", "none"))),
        ("linkedin_url", _q(cap.get("linkedin_url") or existing.get("linkedin_url", "none"))),
        ("last_contacted", _q(cap.get("last_contacted") or existing.get("last_contacted", "null"))),
    ]
    if not body.strip():
        body = "\n## Notes\n"
    _write(repo, rel, fm, body, touched, "contact")
    return slug


# --------------------------------------------------------------- index.md

JOBHUNT_HDR = "## Job-Hunt"


def rebuild_index_md_section(repo: Path) -> None:
    index = repo / "wiki" / "index.md"
    if not index.exists():
        return
    jh = repo / "wiki" / "jobhunt"

    def rows(sub):
        d = jh / sub
        return sorted(p.stem for p in d.glob("*.md")) if d.is_dir() else []

    section = [JOBHUNT_HDR, "",
               "Operational records for the optional job-hunt sub-loop. "
               "Analytics live in `development/job-hunt/pipeline.*` "
               "(scientia-jobhunt-index).", ""]
    for label, sub in (("Applications", "applications"), ("Postings", "postings"),
                       ("Companies", "companies"), ("Interviews", "interviews"),
                       ("Contacts", "contacts")):
        items = rows(sub)
        section.append(f"### {label} ({len(items)})")
        for slug in items:
            section.append(f"- [[jobhunt/{sub}/{slug}]]")
        section.append("")
    block = "\n".join(section).rstrip() + "\n"

    text = index.read_text(encoding="utf-8")
    if JOBHUNT_HDR in text:
        pat = re.compile(rf"^{re.escape(JOBHUNT_HDR)}\b.*?(?=^##\s|\Z)",
                         re.MULTILINE | re.DOTALL)
        text = pat.sub(block, text, count=1)
    else:
        text = text.rstrip() + "\n\n" + block
    index.write_text(text, encoding="utf-8")


def append_log(repo: Path, touched) -> None:
    log = repo / "wiki" / "log.md"
    if not log.exists():
        return
    with log.open("a", encoding="utf-8") as fh:
        for rel, verb in touched:
            short = rel[len("wiki/"):] if rel.startswith("wiki/") else rel
            fh.write(f"- {now_iso()} — scientia-jobhunt-ingest — {verb} — "
                     f"{short} — from capture\n")


# --------------------------------------------------------------- driver

def ingest(repo: Path, campaign: str) -> dict:
    cap_dir = repo / "development" / "job-hunt" / "captures" / campaign
    touched: list = []
    errors: list = []
    counts = {"search": 0, "application": 0, "interview": 0, "contact": 0}
    if cap_dir.is_dir():
        for jf in sorted(cap_dir.rglob("*.json")):
            try:
                cap = json.loads(jf.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"{jf}: invalid JSON ({e})")
                continue
            kind = cap.get("kind")
            if kind == "search":
                for posting in cap.get("postings", []):
                    posting.setdefault("board", cap.get("board"))
                    upsert_company(repo, posting, touched)
                    upsert_posting(repo, posting, touched)
                counts["search"] += 1
            elif kind == "application":
                upsert_company(repo, cap, touched)
                upsert_application(repo, cap, campaign, touched, errors)
                counts["application"] += 1
            elif kind == "interview":
                upsert_interview(repo, cap, touched)
                counts["interview"] += 1
            elif kind == "contact":
                upsert_company(repo, cap, touched)
                upsert_contact(repo, cap, touched)
                counts["contact"] += 1
            else:
                errors.append(f"{jf}: unknown capture kind {kind!r}")

    rebuild_index_md_section(repo)
    append_log(repo, touched)
    return {"touched": touched, "errors": errors, "counts": counts}


def rebuild_pipeline_index(repo: Path, fmt: str) -> None:
    script = (_THIS.parent.parent.parent / "scientia-jobhunt-index"
              / "scripts" / "rebuild_index.py")
    if not script.exists():
        return
    subprocess.run(["python3", str(script), "--repo-root", str(repo),
                    "--format", fmt], check=False)


def _index_format(repo: Path) -> str:
    cfg = repo / "development" / "config.yaml"
    if cfg.exists():
        m = re.search(r"^\s*format:\s*(sqlite|yaml)\s*$",
                      cfg.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            return m.group(1)
    return "sqlite"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--repo-root", default=os.getcwd())
    ap.add_argument("--no-index", action="store_true",
                    help="Skip the pipeline analytics rebuild.")
    args = ap.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    result = ingest(repo, args.campaign)

    if not args.no_index:
        rebuild_pipeline_index(repo, _index_format(repo))

    c = result["counts"]
    print(f"scientia-jobhunt-ingest: captures search={c['search']} "
          f"application={c['application']} interview={c['interview']} "
          f"contact={c['contact']}; pages touched={len(result['touched'])}")
    for err in result["errors"]:
        print(f"  ! {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
