#!/usr/bin/env python3
"""brief.py — bind wiki/jobhunt knowledge into a campaign brief.

The wiki→browser seam of the optional job-hunt sub-loop. Reads the
human-authored profile + target-criteria pages, pins the wiki's current git
rev, and writes development/job-hunt/briefs/<campaign-id>/brief.md — the
single artifact scientia-jobhunt-emit reads to materialise browser tasks.

Modelled on scientia-wiki-bind, but the brief lives under
development/job-hunt/ (NOT development/manifests/) so the mainline tenant
scanner in state_detect.py never mistakes a job-hunt campaign for an
OpenSpec tenant.

Usage:
    brief.py --campaign <slug> [--repo-root <path>]
             [--profile <wiki/jobhunt/profile/x.md>]
             [--criteria <slug,slug>] [--allow-dirty]

Exit codes: 0 ok; 1 preflight refusal; 2 usage/IO error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


# ----------------------------------------------------------- frontmatter

def parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def fm_scalar(fm: dict, key: str, default=None):
    if key not in fm:
        return default
    v = _unquote(fm[key])
    return default if v.lower() in ("null", "none", "") else v


def fm_list(fm: dict, key: str) -> list[str]:
    raw = fm.get(key, "").strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [_unquote(x.strip()) for x in inner.split(",") if x.strip()]
    return [_unquote(raw)] if raw and raw.lower() not in ("null", "none") else []


def section_body(text: str, heading: str) -> str:
    pat = re.compile(rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)",
                     re.MULTILINE | re.DOTALL)
    m = pat.search(text)
    return m.group(1).strip() if m else ""


# ----------------------------------------------------- jobhunt config block
# Minimal stdlib reader for the optional `jobhunt:` block in
# development/config.yaml (PyYAML is not a scientia dependency). Supports
# nested mappings, inline `{k: v}` maps, inline `[a, b]` lists, scalars, and
# full-line / trailing `#` comments. Duplicated (small, self-contained) in
# the other jobhunt scripts that need it.

def _strip_inline_comment(v: str) -> str:
    return re.split(r"\s+#", v, maxsplit=1)[0]


def _parse_scalar(v: str):
    v = v.strip()
    if v.startswith("{") and v.endswith("}"):
        inner = v[1:-1].strip()
        d = {}
        if inner:
            for part in inner.split(","):
                k, _, val = part.partition(":")
                d[k.strip()] = _parse_scalar(val)
        return d
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_parse_scalar(x) for x in inner.split(",")] if inner else []
    return _unquote(v)


def _parse_block(lines: list[str]) -> dict:
    items = [l for l in lines if l.strip() and not l.lstrip().startswith("#")]
    if not items:
        return {}
    indent0 = min(len(l) - len(l.lstrip()) for l in items)
    out: dict = {}
    i = 0
    while i < len(items):
        l = items[i]
        if len(l) - len(l.lstrip()) != indent0:
            i += 1
            continue
        key, _, val = l.strip().partition(":")
        val = _strip_inline_comment(val).strip()
        if val == "":
            j = i + 1
            children = []
            while j < len(items) and (len(items[j]) - len(items[j].lstrip())) > indent0:
                children.append(items[j])
                j += 1
            out[key.strip()] = _parse_block(children) if children else {}
            i = j
        else:
            out[key.strip()] = _parse_scalar(val)
            i += 1
    return out


def load_jobhunt(repo: Path) -> dict | None:
    cfg = repo / "development" / "config.yaml"
    if not cfg.exists():
        return None
    lines = cfg.read_text(encoding="utf-8").splitlines()
    start = None
    for i, l in enumerate(lines):
        if re.match(r"^jobhunt:\s*(#.*)?$", l):
            start = i
            break
    if start is None:
        return None
    block = []
    for l in lines[start + 1:]:
        if l.strip() == "":
            block.append(l)
            continue
        if not l[:1].isspace():           # next top-level key ends the block
            break
        block.append(l)
    return _parse_block(block)


def cfg_get(d: dict | None, dotted: str, default=None):
    cur = d or {}
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


# --------------------------------------------------------------- git pin

def git_rev(repo: Path) -> tuple[str, bool]:
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                      cwd=repo, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain"],
                                         cwd=repo, text=True).strip()
        return rev, bool(status)
    except Exception:
        return "(no-git)", True


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------- build

def build(args: argparse.Namespace) -> int:
    repo = Path(args.repo_root).resolve()
    wiki = repo / "wiki"
    jh = wiki / "jobhunt"

    # Preflight 1: feature enabled.
    jhc = load_jobhunt(repo)
    if jhc is None:
        print("scientia-jobhunt-brief: no `jobhunt:` block in "
              "development/config.yaml — the job-hunt sub-loop is OFF. "
              "Uncomment the block (and re-run scientia-kanban-init) first.",
              file=sys.stderr)
        return 1

    # Resolve the profile page.
    profile_dir = jh / "profile"
    if args.profile:
        profile_page = repo / args.profile
    else:
        cfg_profile = cfg_get(jhc, "user_profile_page")
        if cfg_profile:
            profile_page = repo / cfg_profile
        else:
            pages = sorted(profile_dir.glob("*.md")) if profile_dir.is_dir() else []
            if len(pages) != 1:
                print("scientia-jobhunt-brief: cannot auto-pick a profile page "
                      f"({len(pages)} found under {profile_dir}). Set "
                      "jobhunt.user_profile_page in config or pass --profile.",
                      file=sys.stderr)
                return 1
            profile_page = pages[0]
    if not profile_page.exists():
        print(f"scientia-jobhunt-brief: profile page not found: {profile_page}",
              file=sys.stderr)
        return 1

    # Resolve criteria pages.
    crit_dir = jh / "criteria"
    if args.criteria:
        crit_pages = [crit_dir / f"{s.strip()}.md" for s in args.criteria.split(",") if s.strip()]
    else:
        crit_pages = sorted(crit_dir.glob("*.md")) if crit_dir.is_dir() else []
    crit_pages = [p for p in crit_pages if p.exists()]
    if not crit_pages:
        print(f"scientia-jobhunt-brief: no target-criteria pages under {crit_dir}. "
              "Author at least one wiki/jobhunt/criteria/<slug>.md first.",
              file=sys.stderr)
        return 1

    # Preflight: clean wiki (snapshot pin).
    rev, dirty = git_rev(repo)
    if dirty and not args.allow_dirty:
        print("scientia-jobhunt-brief: wiki has uncommitted changes; commit "
              "first or pass --allow-dirty (records dirty state in the brief).",
              file=sys.stderr)
        return 1

    today = dt.date.today().isoformat()
    campaign_id = args.campaign if re.match(r"^\d{4}-\d{2}-\d{2}-", args.campaign) \
        else f"{today}-{args.campaign}"

    out_dir = repo / "development" / "job-hunt" / "briefs" / campaign_id
    out_path = out_dir / "brief.md"
    if out_path.exists():
        print(f"scientia-jobhunt-brief: brief already exists at {out_path}; "
              "use a new --campaign slug to start another campaign.",
              file=sys.stderr)
        return 1

    provider = cfg_get(jhc, "browser.provider", "cdp")

    # Read profile.
    ptext = profile_page.read_text(encoding="utf-8", errors="ignore")
    pfm = parse_frontmatter(ptext)
    resume_source = fm_scalar(pfm, "resume_source", "(none declared)")

    # Read criteria.
    all_boards: list[str] = []
    all_roles: list[str] = []
    crit_summaries: list[str] = []
    for cp in crit_pages:
        cfm = parse_frontmatter(cp.read_text(encoding="utf-8", errors="ignore"))
        roles = fm_list(cfm, "roles")
        locations = fm_list(cfm, "locations")
        boards = fm_list(cfm, "boards")
        exclusions = fm_list(cfm, "exclusions")
        seniority = fm_scalar(cfm, "seniority", "(any)")
        comp_floor = fm_scalar(cfm, "comp_floor", "(unset)")
        comp_currency = fm_scalar(cfm, "comp_currency", "USD")
        all_boards += boards
        all_roles += roles
        rel = cp.relative_to(repo)
        crit_summaries.append(
            f"- [[{cp.relative_to(wiki).with_suffix('')}]] — roles={roles or '(any)'}; "
            f"locations={locations or '(any)'}; seniority={seniority}; "
            f"comp_floor={comp_floor} {comp_currency}; boards={boards or '(any)'}; "
            f"exclusions={exclusions or '(none)'}  ({rel})")

    boards = list(dict.fromkeys(all_boards)) or ["(none declared)"]
    roles = list(dict.fromkeys(all_roles)) or ["(none declared)"]

    # Compose.
    body: list[str] = []
    body.append("---")
    body.append(f'title: "Job-hunt brief — {campaign_id}"')
    body.append("type: jobhunt-brief")
    body.append(f"campaign_id: {campaign_id}")
    body.append(f"wiki_snapshot: {rev}")
    body.append(f"wiki_dirty: {'true' if dirty else 'false'}")
    body.append(f"user_profile_page: {profile_page.relative_to(repo)}")
    body.append("criteria_pages: ["
                + ", ".join(str(p.relative_to(repo)) for p in crit_pages) + "]")
    body.append(f"provider: {provider}")
    body.append("scientia_schema: 1")
    body.append(f"created: {today}")
    body.append("---")
    body.append("")
    body.append("## 1 — User Profile")
    body.append("")
    body.append(f"**Source page:** [[{profile_page.relative_to(wiki).with_suffix('')}]]")
    body.append("")
    for heading in ("Contact", "Skills", "Experience", "Preferences"):
        sec = section_body(ptext, heading)
        body.append(f"### {heading}")
        body.append("")
        body.append(sec or "_(empty on profile page)_")
        body.append("")
    body.append("## 2 — Target Criteria")
    body.append("")
    body.extend(crit_summaries)
    body.append("")
    body.append("## 3 — Résumé Source")
    body.append("")
    body.append(f"Tailor from: `{resume_source}`")
    body.append("")
    body.append("## 4 — Search Plan")
    body.append("")
    body.append("One search task is emitted per (board × role) pair below; the "
                "browser worker filters results against the criteria.")
    body.append("")
    for board in boards:
        for role in roles:
            body.append(f"- board=`{board}` query=\"{role}\"")
    body.append("")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(body), encoding="utf-8")

    dev_log = repo / "development" / "log.md"
    if dev_log.exists():
        with dev_log.open("a", encoding="utf-8") as f:
            f.write(f"- {utc_now()} — scientia-jobhunt-brief — brief-bound "
                    f"— {campaign_id} — wiki_snapshot={rev[:8]} provider={provider}\n")

    print(f"scientia-jobhunt-brief: wrote {out_path.relative_to(repo)}")
    print(f"  campaign_id={campaign_id} provider={provider} "
          f"boards={len(boards)} roles={len(roles)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=os.getcwd())
    ap.add_argument("--campaign", required=True,
                    help="Campaign slug; prefixed with today's date unless it "
                         "already starts with YYYY-MM-DD-.")
    ap.add_argument("--profile", default=None,
                    help="Path to the profile page (default: config or auto).")
    ap.add_argument("--criteria", default=None,
                    help="Comma-separated criteria slugs (default: all pages).")
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
