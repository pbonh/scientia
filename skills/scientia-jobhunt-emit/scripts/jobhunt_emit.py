#!/usr/bin/env python3
"""jobhunt_emit.py — emit Hermes browser tasks for a job-hunt campaign.

Reads a campaign brief (development/job-hunt/briefs/<id>/brief.md) and emits
flat kanban rows assigned to the scientia-jobhunt-agent profile. Mirrors
scientia-kanban-emit's verified CLI shape, but the job-hunt model is flat
(no impl/review/integrate pipeline, no Gherkin).

Two-step by design — applying to a job is consequential:

  1. DEFAULT: emit one **search** task per (board × role) in the brief's
     Search Plan. Workers find postings; scientia-jobhunt-ingest writes
     wiki/jobhunt/postings pages.
  2. --apply <slug,slug> (or --apply-all): for chosen postings, emit an
     **author → form-fill → submit** chain. The form-fill is emitted with
     --triage and BLOCKS before submit; the submit row is --parent'd to the
     form-fill so the dispatcher cannot run it until a human promotes the
     gate.

Idempotent: re-emitting a task with the same idempotency key returns the
existing id (no double-apply).

Usage:
    jobhunt_emit.py --campaign <id> [--repo-root <path>]
                    [--apply <slug,slug> | --apply-all]
                    [--dry-run]

Exit: 0 ok; 1 preflight refusal; 2 usage/IO error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_THIS = Path(__file__).resolve()
_SKILLS = _THIS.parent.parent.parent  # …/skills/
sys.path.insert(0, str(_SKILLS / "scientia-kanban-emit" / "scripts"))
sys.path.insert(0, str(_SKILLS / "scientia-kanban-init" / "scripts"))

from emit import _parse_yaml_subset  # noqa: E402
from profile_models import (  # noqa: E402
    resolve_profile_name,
    check_profile_models_drift,
)
from check_browser_provider import check_browser_provider  # noqa: E402

ASSIGNEE_ROLE = "jobhunt"
DEFAULT_CDP_ENDPOINT = "http://127.0.0.1:9222"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
SEARCH_LINE_RE = re.compile(r"-\s*board=`([^`]+)`\s+query=\"([^\"]+)\"")


def sha16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def strip_wikilink(v: str) -> str:
    m = re.match(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", v or "")
    return (m.group(1) if m else (v or "")).split("/")[-1]


@dataclass
class TaskSpec:
    kind: str
    title: str
    key: str
    body: str
    parents: list = field(default_factory=list)  # parent idempotency keys
    triage: bool = False


# --------------------------------------------------------------- body render

def _handoff_pointer() -> str:
    return ("See references/JOBHUNT_HANDOFF_SCHEMA.md — fill every field "
            "(task_kind, campaign_id, posting_url, company, "
            "postings_captured, application_status, gate_state, "
            "screenshot_path, résumé/cover artifacts+sha256, "
            "interview_datetime, contacts, blocked_reason).")


def _search_body(campaign, board, query, cdp, captures_dir) -> str:
    return f"""# @jobhunt-brief: {campaign}

## Goal
Search the `{board}` job board for "{query}" and capture matching postings.

## Target
board={board}; query="{query}"

## Approach
Run the query, page through results, and record each plausible posting.
Discard postings below the brief's comp floor or matching its exclusions.

## Acceptance
A capture file written under `{captures_dir}/search/` listing
`{{url, company, role, comp}}` for each kept posting.

## Browser Plan
- attach: CDP endpoint `{cdp}`
- browser_navigate to the `{board}` search for "{query}"
- browser_snapshot; page through results; collect posting links
- write the capture file; complete

## Glossary
- posting: a specific role at a company (becomes a wiki/jobhunt/postings page)
- comp floor / exclusions: filters declared in the campaign criteria

## Required Handoff
{_handoff_pointer()}

---
campaign_id: {campaign}
task_kind: search
idempotency_key: jobhunt-search:{campaign}:{board}:{sha16(query)}
"""


def _author_body(campaign, company, role, url, cdp, app_slug) -> str:
    return f"""# @jobhunt-brief: {campaign}

## Goal
Tailor a résumé and cover letter for {role} @ {company}, seeded from the
profile/résumé-source in the campaign brief.

## Target
{role} @ {company} — {url}

## Approach
Read the posting requirements; tailor the base résumé and draft a cover
letter that maps the profile's experience to the requirements.

## Acceptance
Artifacts written under `development/job-hunt/artifacts/{app_slug}/`
(resume + cover); their paths and sha256 recorded in the handoff.

## Browser Plan
- attach: CDP endpoint `{cdp}` (browser_navigate to the posting for context)
- author the documents (no form submission in this task)

## Glossary
- application: one tracked attempt at one posting

## Required Handoff
{_handoff_pointer()}

---
campaign_id: {campaign}
task_kind: author
idempotency_key: jobhunt-author:{company}:{sha16(url)}
"""


def _formfill_body(campaign, company, role, url, cdp, app_slug, campaign_caps) -> str:
    return f"""# @jobhunt-brief: {campaign}

## Goal
Pre-fill the application form for {role} @ {company}. DO NOT SUBMIT.

## Target
{role} @ {company} — {url}

## Approach
Open the application form, fill every field from the profile data and the
authored résumé/cover artifacts.

## Acceptance
Form filled completely; a preview screenshot written to
`{campaign_caps}/{app_slug}/preview.png`; task BLOCKED awaiting human
approval (gate_state: awaiting-approval).

## Browser Plan
- attach: CDP endpoint `{cdp}`
- browser_navigate to {url}; open the application form
- fill all fields; browser_vision screenshot -> preview.png
- DO NOT click Submit/Apply
- hermes kanban block <id> --reason "form filled; awaiting human submit approval"

## Human Gate
This is the gated task. Fill, screenshot, then BLOCK. The actual submit is
a separate task a human promotes after reviewing the preview. Never click
the final Submit here.

## Glossary
- human gate: the irreversible submit requires explicit human approval

## Required Handoff
{_handoff_pointer()}

---
campaign_id: {campaign}
task_kind: form-fill
idempotency_key: jobhunt-formfill:{company}:{sha16(url)}
"""


def _submit_body(campaign, company, role, url, cdp, app_slug) -> str:
    return f"""# @jobhunt-brief: {campaign}

## Goal
Submit the (human-approved) application for {role} @ {company}.

## Target
{role} @ {company} — {url}

## Approach
This task only dispatches after a human promoted the matching form-fill.
Re-attach, ensure the form is still filled (re-fill idempotently if the
session expired), click Submit, and capture the confirmation.

## Acceptance
Application submitted; confirmation captured; application_status: applied.

## Browser Plan
- attach: CDP endpoint `{cdp}`
- browser_navigate to {url}; confirm the form state
- click the final Submit; browser_snapshot the confirmation
- complete with application_status: applied

## Glossary
- applied: the submitted state in STATUS_ENUM.md

## Required Handoff
{_handoff_pointer()}

---
campaign_id: {campaign}
task_kind: submit
idempotency_key: jobhunt-submit:{company}:{sha16(url)}
"""


# --------------------------------------------------------------- spec builders

def read_brief(repo: Path, campaign: str) -> tuple[dict, list[tuple[str, str]]]:
    brief_path = repo / "development" / "job-hunt" / "briefs" / campaign / "brief.md"
    if not brief_path.exists():
        raise FileNotFoundError(brief_path)
    text = brief_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    plan = SEARCH_LINE_RE.findall(text)  # list of (board, query)
    return fm, plan


def build_search_specs(campaign: str, plan, cdp: str) -> list[TaskSpec]:
    captures_dir = f"development/job-hunt/captures/{campaign}"
    specs = []
    for board, query in plan:
        specs.append(TaskSpec(
            kind="search",
            title=f"[jobhunt:{campaign}] search {board}: {query}",
            key=f"jobhunt-search:{campaign}:{board}:{sha16(query)}",
            body=_search_body(campaign, board, query, cdp, captures_dir),
        ))
    return specs


def _postings(repo: Path) -> dict[str, dict]:
    """slug -> {url, company, role} for every wiki/jobhunt/postings page."""
    d = repo / "wiki" / "jobhunt" / "postings"
    out = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.md")):
        fm = parse_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        out[p.stem] = {
            "url": fm.get("posting_url", ""),
            "company": strip_wikilink(fm.get("company", "")) or "unknown",
            "role": fm.get("role", p.stem),
        }
    return out


def build_apply_specs(repo: Path, campaign: str, cdp: str,
                      selected: Optional[set]) -> list[TaskSpec]:
    """For each selected posting, an author→form-fill→submit chain."""
    postings = _postings(repo)
    if selected is not None:
        missing = selected - set(postings)
        if missing:
            raise ValueError(
                f"--apply names postings with no wiki/jobhunt/postings page: "
                f"{sorted(missing)}")
        chosen = {s: postings[s] for s in selected}
    else:
        chosen = postings  # --apply-all

    caps = f"development/job-hunt/captures/{campaign}"
    specs: list[TaskSpec] = []
    for slug, meta in chosen.items():
        url = meta["url"] or slug
        company = meta["company"]
        role = meta["role"]
        author_key = f"jobhunt-author:{company}:{sha16(url)}"
        formfill_key = f"jobhunt-formfill:{company}:{sha16(url)}"
        submit_key = f"jobhunt-submit:{company}:{sha16(url)}"
        specs.append(TaskSpec(
            kind="author",
            title=f"[jobhunt:{campaign}] author {role} @ {company}",
            key=author_key,
            body=_author_body(campaign, company, role, url, cdp, slug)))
        specs.append(TaskSpec(
            kind="form-fill",
            title=f"[jobhunt:{campaign}] form-fill {role} @ {company}",
            key=formfill_key,
            body=_formfill_body(campaign, company, role, url, cdp, slug, caps),
            parents=[author_key],
            triage=True))
        specs.append(TaskSpec(
            kind="submit",
            title=f"[jobhunt:{campaign}] SUBMIT (gated) {role} @ {company}",
            key=submit_key,
            body=_submit_body(campaign, company, role, url, cdp, slug),
            parents=[formfill_key]))
    return specs


# --------------------------------------------------------------- preflight

def preflight(repo: Path, config: dict) -> Optional[str]:
    """Return a refusal string, or None when clear. Hermes-dependent."""
    # Provider reachability.
    reason = check_browser_provider(config=config)
    if reason:
        return reason
    # Profile existence.
    hermes_cfg = config.get("hermes") or {}
    profile = resolve_profile_name(ASSIGNEE_ROLE, hermes_cfg.get("profile_names"))
    try:
        r = subprocess.run(["hermes", "profile", "show", profile],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return (f"jobhunt profile {profile!r} is not registered with "
                    "Hermes. Fix: run scientia-kanban-init (with the jobhunt "
                    "block enabled).")
    except FileNotFoundError:
        return "hermes CLI not on PATH."
    # Gateway up.
    procs = Path.home() / ".hermes" / "processes.json"
    try:
        data = json.loads(procs.read_text(encoding="utf-8")) if procs.exists() else {}
        text = json.dumps(data)
        if "gateway" not in text:
            return ("Hermes gateway is not running — emitted tasks would sit "
                    "in todo forever. Start it: `hermes gateway start` (or "
                    "`hermes gateway run`).")
    except Exception:
        pass
    # Model drift (only if hermes.profiles declared).
    drift = check_profile_models_drift(
        profiles_block=hermes_cfg.get("profiles"),
        profile_names=hermes_cfg.get("profile_names"),
    )
    if drift:
        return drift
    return None


# --------------------------------------------------------------- emit

def emit_specs(repo: Path, campaign: str, specs: list[TaskSpec],
               *, dry_run: bool, runner: Callable = subprocess.run) -> dict:
    """Create each spec via hermes kanban create, resolving parent keys to
    ids. Writes per-task index files. Returns {key: task_id}."""
    abs_repo = str(repo.resolve())
    key_to_id: dict[str, str] = {}
    tasks_dir = repo / "development" / "job-hunt" / "tasks" / campaign
    for spec in specs:
        argv = [
            "hermes", "kanban", "create",
            "--idempotency-key", spec.key,
            "--tenant", "jobhunt",
            "--assignee", "scientia-jobhunt-agent",
            "--workspace", f"dir:{abs_repo}",
            "--skill", "scientia-jobhunt-worker",
            "--skill", "scientia-grill",
            "--json",
        ]
        for pkey in spec.parents:
            pid = key_to_id.get(pkey)
            if pid:
                argv += ["--parent", pid]
        if spec.triage:
            argv.append("--triage")
        # body via tmpfile-style inline; mirrors emit's "$(cat ...)".
        argv += ["--body", spec.body, spec.title]

        if dry_run:
            print(f"[dry-run] {spec.kind}: {spec.title}")
            print("  " + " ".join(
                a if not a.startswith("#") and "\n" not in a else "<body>"
                for a in argv))
            key_to_id[spec.key] = f"dry_{spec.kind}_{sha16(spec.key)[:6]}"
            continue

        proc = runner(argv, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"hermes kanban create failed for {spec.key}: "
                f"{proc.stderr.strip() or 'no stderr'}")
        try:
            task_id = (json.loads(proc.stdout) or {}).get("id") or proc.stdout.strip()
        except json.JSONDecodeError:
            task_id = proc.stdout.strip()
        key_to_id[spec.key] = task_id
        # index entry
        tasks_dir.mkdir(parents=True, exist_ok=True)
        (tasks_dir / f"{spec.key.replace(':', '_').replace('/', '_')}.md").write_text(
            f"---\ntask_id: {task_id}\nkind: {spec.kind}\n"
            f"idempotency_key: {spec.key}\ntriage: {str(spec.triage).lower()}\n---\n"
            f"{spec.title}\n", encoding="utf-8")
    return key_to_id


def run(args) -> int:
    repo = Path(args.repo_root).resolve()
    config_path = repo / "development" / "config.yaml"
    config = _parse_yaml_subset(config_path.read_text(encoding="utf-8")) \
        if config_path.exists() else {}

    if not isinstance(config.get("jobhunt"), dict):
        print("jobhunt feature OFF (no jobhunt: block in config) — nothing to emit.",
              file=sys.stderr)
        return 1

    try:
        fm, plan = read_brief(repo, args.campaign)
    except FileNotFoundError as e:
        print(f"no brief for campaign {args.campaign!r}: {e}. Run "
              "scientia-jobhunt-brief first.", file=sys.stderr)
        return 1

    # Snapshot pin must still resolve.
    snap = fm.get("wiki_snapshot")
    if snap and snap != "(no-git)":
        r = subprocess.run(["git", "rev-parse", "--verify", snap + "^{commit}"],
                          cwd=repo, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"brief wiki_snapshot {snap[:8]} no longer resolves; re-bind "
                  "with scientia-jobhunt-brief.", file=sys.stderr)
            return 1

    cdp = ((config.get("jobhunt") or {}).get("browser") or {}).get(
        "cdp_endpoint") or DEFAULT_CDP_ENDPOINT

    if not args.dry_run:
        refusal = preflight(repo, config)
        if refusal:
            print(refusal, file=sys.stderr)
            return 1

    specs: list[TaskSpec] = []
    if args.apply_all or args.apply:
        selected = None if args.apply_all else {
            s.strip() for s in args.apply.split(",") if s.strip()}
        try:
            specs += build_apply_specs(repo, args.campaign, cdp, selected)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
    else:
        specs += build_search_specs(args.campaign, plan, cdp)

    if not specs:
        print("nothing to emit (no search plan / no selected postings).",
              file=sys.stderr)
        return 1

    key_to_id = emit_specs(repo, args.campaign, specs, dry_run=args.dry_run)

    kinds = {}
    for s in specs:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    if not args.dry_run:
        log = repo / "development" / "log.md"
        if log.exists():
            with log.open("a", encoding="utf-8") as fh:
                fh.write(f"- {utc_now()} — scientia-jobhunt-emit — emitted — "
                         f"{args.campaign} — "
                         f"{' '.join(f'{k}={v}' for k, v in sorted(kinds.items()))}\n")
    print(f"scientia-jobhunt-emit: {'(dry-run) ' if args.dry_run else ''}"
          f"emitted {len(specs)} task(s): "
          f"{', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--repo-root", default=os.getcwd())
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", default=None,
                   help="Comma-separated posting slugs to emit apply pipelines for.")
    g.add_argument("--apply-all", action="store_true",
                   help="Emit apply pipelines for every known posting (power user).")
    ap.add_argument("--dry-run", action="store_true")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
