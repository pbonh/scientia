#!/usr/bin/env python3
"""emit.py — orchestrate the scientia-kanban-emit pipeline.

Reads a verified OpenSpec change, runs preflight gates, picks a
collaboration pattern, builds per-task bodies, drives `hermes kanban`
to emit one parent + one aggregator + N per-scenario child tasks,
writes the `## Kanban Tasks` section back to each spec, drops per-task
index entries under `development/tasks/...`, and appends to
`development/log.md`.

Stdlib only. Imports helpers from idempotency_key.py in the same dir.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

# Reuse the idempotency-key helpers that live next to this module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from idempotency_key import (  # noqa: E402
    aggregator_key,
    extract_scenarios,
    hash_body,
    parent_key,
    slugify,
    strip_for_hash,
)
from profile_models import (  # noqa: E402
    check_profile_models_drift,
    check_profiles_exist,
)
from tasks_md import (  # noqa: E402
    TaskItem,
    items_for_scenario,
    parse_tasks_file,
    shared_infrastructure,
    topological_order,
)


# ---------------------------------------------------------------------------
# Tiny YAML-frontmatter reader (scalars only — we don't need nested mappings)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _read_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith(" ") or line.startswith("\t"):
            continue  # nested block — we don't need it
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if value in ("null", "~", ""):
            value = None  # type: ignore[assignment]
        out[key.strip()] = value
    return out


# ---------------------------------------------------------------------------
# Severity ordering for verify-*.md
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"clean": 0, "suggestion": 1, "warning": 2, "critical": 3}


# ---------------------------------------------------------------------------
# Preflight gates
#
# Each gate is a standalone function that takes its inputs explicitly and
# returns None when the gate passes, or a human-readable refusal string.
# ---------------------------------------------------------------------------


def check_gateway(processes_json_path: Path) -> Optional[str]:
    """Refuse if no `kind: gateway` entry is in ~/.hermes/processes.json.

    Without a gateway, the kanban dispatcher never ticks, so emitted tasks
    would sit in `todo` forever.
    """
    start_hint = (
        "Recommended: `hermes gateway install && hermes gateway start` "
        "(installs and starts the launchd/systemd service). "
        "Alternatives: `hermes gateway run` (foreground, for WSL/Docker/Termux) "
        "or `nohup hermes gateway start > ~/.hermes/logs/gateway.log 2>&1 &` "
        "(no-service-manager fallback; does not survive reboot)."
    )

    try:
        raw = processes_json_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f"Hermes gateway is not running: {processes_json_path} not found. "
            + start_hint
        )

    try:
        processes = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"Hermes gateway state unreadable: {processes_json_path} is not valid JSON ({e})."

    for entry in processes:
        if isinstance(entry, dict) and entry.get("kind") == "gateway":
            return None

    return (
        "Hermes gateway is not running: no `kind: gateway` entry in "
        f"{processes_json_path}. " + start_hint
    )


def check_hermes_on_path() -> Optional[str]:
    """Refuse if the `hermes` CLI is not resolvable on PATH."""
    if shutil.which("hermes"):
        return None
    return (
        "Hermes CLI not on PATH. Install Hermes Agent and re-run; "
        "scientia depends on it as a hard external dependency."
    )


def _read_hermes_max_concurrent_children(text: str) -> Optional[int]:
    """Extract `delegation.max_concurrent_children` from a hermes config.yaml.

    Scoped to the `delegation:` top-level block so we don't accidentally
    match a similarly-named key in another section. Returns None when the
    key is absent or its value is non-integer.
    """
    in_delegation = False
    for line in text.splitlines():
        if line and not line.startswith((" ", "\t")):
            in_delegation = line.startswith("delegation:")
            continue
        if not in_delegation:
            continue
        m = re.match(r"\s+max_concurrent_children:\s*(-?\d+)\s*(?:#.*)?$", line)
        if m:
            return int(m.group(1))
    return None


def check_concurrency_cap(
    *, desired: int, hermes_config_path: Path
) -> Optional[str]:
    """Refuse if hermes' `delegation.max_concurrent_children` differs from
    the per-repo desired value.

    Read-only: reads `~/.hermes/config.yaml` directly. When that file is
    missing or the key is absent, treats the host as hermes' built-in
    default (3) — matches the doc'd default at
    hermes-agent.nousresearch.com/docs/guides/delegation-patterns.
    """
    try:
        text = hermes_config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # No hermes config yet — check_hermes_on_path / init will cover it.
        return None

    host = _read_hermes_max_concurrent_children(text)
    if host is None:
        host = 3  # hermes' documented default when the key is absent

    if host == desired:
        return None

    return (
        f"delegation.max_concurrent_children drift: host={host} desired={desired}. "
        f"Fix: `hermes config set delegation.max_concurrent_children {desired}` "
        f"(or re-run scientia-kanban-init)."
    )


def check_verify_severity(change_dir: Path, *, block_on: str) -> Optional[str]:
    """Refuse if the latest `verify-*.md` has worst_severity >= block_on.

    "Latest" is determined by filename sort (timestamps are ISO-like).
    """
    reports = sorted(change_dir.glob("verify-*.md"))
    if not reports:
        return f"No verify-*.md report found in {change_dir}; run scientia-intent-verify first."

    latest = reports[-1]
    fm = _read_frontmatter(latest.read_text(encoding="utf-8"))
    worst = fm.get("worst_severity") or "clean"
    worst_rank = SEVERITY_ORDER.get(worst, 0)
    block_rank = SEVERITY_ORDER.get(block_on, 99)

    if worst_rank >= block_rank:
        return (
            f"Verify report {latest.name} has worst_severity={worst}, "
            f"which meets/exceeds block_on_severity={block_on}. Resolve and re-verify."
        )
    return None


def check_adr_status(change_dir: Path) -> Optional[str]:
    """Refuse if any ADR in adr/ is deprecated, or superseded without successor.

    No `adr/` directory at all is acceptable — not every change cites ADRs.
    """
    adr_dir = change_dir / "adr"
    if not adr_dir.is_dir():
        return None

    bad: List[str] = []
    for adr_file in sorted(adr_dir.glob("*.md")):
        fm = _read_frontmatter(adr_file.read_text(encoding="utf-8"))
        status = (fm.get("status") or "").lower()
        adr_id = fm.get("adr_id") or adr_file.stem
        if status == "deprecated":
            bad.append(f"{adr_id} is deprecated")
        elif status == "superseded" and not fm.get("superseded_by"):
            bad.append(f"{adr_id} is superseded without a successor")

    if bad:
        return "Stale ADRs cited: " + "; ".join(bad)
    return None


def check_spec_on_trunk(change_dir: Path, *, trunk: str) -> Optional[str]:
    """Refuse if any specs/*/spec.md is absent from `trunk`'s history.

    Uses `git log <trunk> -- <spec>`. Empty stdout means the file is not on
    trunk yet (lives only on a feature branch). The sha256 over a moving
    spec body would produce a meaningless idempotency key.
    """
    specs_dir = change_dir / "specs"
    if not specs_dir.is_dir():
        return None

    not_on_trunk: List[str] = []
    for spec in sorted(specs_dir.glob("*/spec.md")):
        proc = subprocess.run(
            ["git", "log", "--format=%H", "-1", trunk, "--", str(spec)],
            cwd=change_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            not_on_trunk.append(str(spec.relative_to(change_dir)))

    if not_on_trunk:
        return (
            f"Specs not yet on trunk ({trunk}): " + ", ".join(not_on_trunk)
            + ". Merge them before emitting; idempotency keys depend on stable spec bodies."
        )
    return None


# ---------------------------------------------------------------------------
# Governing ADR + section extraction
# ---------------------------------------------------------------------------


_ADR_NUM_RE = re.compile(r"ADR-(\d+)", re.IGNORECASE)


def _adr_number(adr_id: str) -> int:
    m = _ADR_NUM_RE.match(adr_id)
    return int(m.group(1)) if m else 10**9


def governing_adr(change_dir: Path) -> str:
    """Pick the governing ADR for idempotency-key purposes.

    Rule: lowest-numbered `accepted` ADR. If none are accepted, fall back to
    the lowest-numbered ADR regardless of status (some changes emit before
    any ADR is accepted, under P5).

    Raises ValueError when no `adr/` directory or no ADR files are present.
    """
    adr_dir = change_dir / "adr"
    if not adr_dir.is_dir():
        raise ValueError(f"{change_dir} has no adr/ directory")

    entries: List[tuple[int, str, str]] = []  # (number, status, adr_id)
    for adr_file in adr_dir.glob("*.md"):
        fm = _read_frontmatter(adr_file.read_text(encoding="utf-8"))
        adr_id = fm.get("adr_id") or adr_file.stem
        status = (fm.get("status") or "").lower()
        entries.append((_adr_number(adr_id), status, adr_id))

    if not entries:
        raise ValueError(f"{adr_dir} contains no ADR files")

    accepted = [e for e in entries if e[1] == "accepted"]
    chosen = sorted(accepted)[0] if accepted else sorted(entries)[0]
    return chosen[2]


_H1_CAPABILITY_RE = re.compile(
    r"^#\s+Capability:\s*.*?\n+(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)

_SECTION_RE_TEMPLATE = r"^##\s+{name}\b[^\n]*\n+(.*?)(?=^##\s|\Z)"


def _extract_capability_description(spec_text: str) -> str:
    m = _H1_CAPABILITY_RE.search(spec_text)
    return m.group(1).strip() if m else ""


def _extract_section(spec_text: str, name: str) -> str:
    """Return the body of `## <name>` (everything until the next ## or EOF)."""
    pattern = _SECTION_RE_TEMPLATE.format(name=re.escape(name))
    m = re.search(pattern, spec_text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Body construction
# ---------------------------------------------------------------------------


@dataclass
class TaskBody:
    title: str
    body_markdown: str
    idempotency_key: str
    assignee: str
    scenario_slug: Optional[str] = None  # None for parent/aggregator


@dataclass
class BodyBundle:
    parent: TaskBody
    aggregator: TaskBody
    children: List[TaskBody] = field(default_factory=list)


@dataclass
class TaskItemBody:
    """A per-tasks.md-item task body — the implementation-plan unit.

    Distinct from `TaskBody` because the source artifact is a single tasks.md
    bullet, not a Gherkin scenario. Each item drives its own impl/review/
    integrate pipeline; per-scenario impl rows are then wired to depend on the
    `:integrate` stage of every task whose `@spec` markers match the scenario,
    plus universal shared-infrastructure items with no `@spec` marker.
    """
    number: int                                # tasks.md "**N.**"
    title: str
    body_markdown: str
    idempotency_key: str                       # base key, before :impl/:review/:integrate suffix
    depends_on: List[int]                      # tasks.md item numbers this depends on
    spec_refs: List[tuple]                     # [(capability, scenario_slug), ...]
    non_behavioral: bool = False


@dataclass
class TaskItemBundle:
    """Output of `build_task_bodies` — one TaskItemBody per tasks.md item, in
    topological order so callers can emit them safely."""
    items: List[TaskItemBody] = field(default_factory=list)


def _governing_adrs_section(change_dir: Path) -> str:
    """Render `## Governing ADRs` body — a bullet per ADR file."""
    adr_dir = change_dir / "adr"
    if not adr_dir.is_dir():
        return "(none)"
    lines: List[str] = []
    for adr_file in sorted(adr_dir.glob("*.md")):
        fm = _read_frontmatter(adr_file.read_text(encoding="utf-8"))
        adr_id = fm.get("adr_id") or adr_file.stem
        title = fm.get("title") or adr_id
        status = fm.get("status") or "unknown"
        lines.append(f"- {adr_id} — {title} — status={status}")
    return "\n".join(lines) or "(none)"


def _render_body(
    *,
    capability: str,
    goal: str,
    acceptance_criteria: str,
    scenario_block: str,
    glossary: str,
    governing_adrs: str,
    checklist: str,
    handoff: str,
    wiki_backlink: str,
    idempotency_key_value: str,
) -> str:
    """Render a task body per the SKILL.md step 3 schema."""
    return f"""# @wiki-spec: {capability}

## Goal
{goal}

## Acceptance Criteria
{acceptance_criteria}

## Scenario
{scenario_block}

## Glossary (inlined; do not paraphrase)
{glossary}

## Governing ADRs
{governing_adrs}

## Implementation Checklist (from tasks.md, advisory)
{checklist}

{handoff}

---
wiki_backlink: {wiki_backlink}
idempotency_key: {idempotency_key_value}
"""


def build_bodies(
    *,
    change_dir: Path,
    spec_path: Path,
    handoff_path: Path,
    profiles: Optional[dict] = None,
) -> BodyBundle:
    """Build the parent + aggregator + per-scenario child bodies for one spec.

    `profiles` overrides assignee names (key = role); defaults to scientia-*.
    """
    profiles = profiles or {
        "parent": "scientia-implementer",
        "child": "scientia-implementer",
        "aggregator": "scientia-aggregator",
    }

    spec_text_raw = spec_path.read_text(encoding="utf-8")
    spec_text = strip_for_hash(spec_text_raw)  # excludes frontmatter + ## Kanban Tasks
    spec_slug = spec_path.parent.name

    fm = _read_frontmatter(spec_text_raw)
    capability = fm.get("capability") or spec_slug

    adr_id = governing_adr(change_dir)
    goal = _extract_capability_description(spec_text)
    acceptance = _extract_section(spec_text, "Acceptance Criteria")
    glossary = _extract_section(spec_text, "Glossary (inlined from manifest)")
    if not glossary:
        glossary = _extract_section(spec_text, "Glossary")
    governing_adrs = _governing_adrs_section(change_dir)

    tasks_md_path = change_dir / "tasks.md"
    full_checklist = ""
    if tasks_md_path.is_file():
        # The advisory checklist is the body of the tasks.md (after frontmatter).
        full_checklist = _FRONTMATTER_RE.sub("", tasks_md_path.read_text(encoding="utf-8"), count=1).strip()

    handoff = handoff_path.read_text(encoding="utf-8").strip()

    wiki_backlink = f"wiki/specs/{capability}.md"

    # ----- Children: one body per scenario -----
    children: List[TaskBody] = []
    for slug, block in extract_scenarios(spec_text):
        child_k = f"{spec_slug}:{adr_id}:{slug}:{hash_body(block)}"
        # Scenario rendered as fenced gherkin (the block already contains the fence).
        scenario_text = f"### Scenario: {slug}\n{block}"
        body = _render_body(
            capability=capability,
            goal=goal,
            acceptance_criteria=acceptance,
            scenario_block=scenario_text,
            glossary=glossary,
            governing_adrs=governing_adrs,
            checklist=full_checklist,  # advisory; per-scenario scoping TBD
            handoff=handoff,
            wiki_backlink=wiki_backlink,
            idempotency_key_value=child_k,
        )
        # Build a human-readable title from the scenario slug.
        title = slug.replace("-", " ").capitalize()
        children.append(TaskBody(
            title=f"[{capability}] {title}",
            body_markdown=body,
            idempotency_key=child_k,
            assignee=profiles["child"],
            scenario_slug=slug,
        ))

    # ----- Parent -----
    parent_k = parent_key(spec_slug, adr_id, spec_text_raw)
    parent_scenario_summary = "\n\n".join(
        f"### Scenario: {slug}\n{block}" for slug, block in extract_scenarios(spec_text)
    )
    parent_body = _render_body(
        capability=capability,
        goal=goal,
        acceptance_criteria=acceptance,
        scenario_block=parent_scenario_summary,
        glossary=glossary,
        governing_adrs=governing_adrs,
        checklist=full_checklist,
        handoff=handoff,
        wiki_backlink=wiki_backlink,
        idempotency_key_value=parent_k,
    )
    parent = TaskBody(
        title=f"[{capability}] {capability} — spec",
        body_markdown=parent_body,
        idempotency_key=parent_k,
        assignee=profiles["parent"],
    )

    # ----- Aggregator -----
    agg_k = aggregator_key(parent_k)
    child_lines = "\n".join(
        f"- `{c.idempotency_key}`" for c in children
    )
    agg_body = (
        f"# @wiki-spec: {capability}\n\n"
        f"## Role\nAggregate the per-scenario worker outputs for `{capability}` "
        "into a single completion comment for the parent task.\n\n"
        f"## Children\n{child_lines}\n\n"
        f"{handoff}\n\n"
        "---\n"
        f"wiki_backlink: {wiki_backlink}\n"
        f"idempotency_key: {agg_k}\n"
    )
    aggregator = TaskBody(
        title=f"[{capability}] aggregator",
        body_markdown=agg_body,
        idempotency_key=agg_k,
        assignee=profiles["aggregator"],
    )

    return BodyBundle(parent=parent, aggregator=aggregator, children=children)


def _render_task_item_body(
    *,
    item: TaskItem,
    change_slug: str,
    governing_adrs: str,
    handoff: str,
    idempotency_key_value: str,
) -> str:
    """Render the body for one tasks.md impl row.

    The body is intentionally narrower than the per-scenario body: tasks.md
    items are units of *plan*, not units of *acceptance*. They carry their
    own title and dependency chain, links back to spec scenarios they enable
    (for traceability — workers should read those specs), and the shared
    handoff schema. No Gherkin block — that lives on the per-scenario row.
    """
    spec_lines = "\n".join(
        f"- `{ref.capability}#{ref.scenario_slug}`" for ref in item.spec_refs
    ) or "(none — shared infrastructure)"
    adr_lines = "\n".join(f"- {adr}" for adr in item.adr_refs) or "(none)"
    dep_lines = ", ".join(f"#{n}" for n in item.depends_on) or "(none)"
    nonbeh = " (non-behavioral)" if item.non_behavioral else ""

    return f"""# @tasks-md: {change_slug} item #{item.number}{nonbeh}

## Goal
{item.title}

## Source
- tasks.md section: `{item.section or '(unsectioned)'}`
- tasks.md depends on: {dep_lines}

## Enables (spec scenarios)
{spec_lines}

## Governing ADRs (item-level)
{adr_lines}

## Change-level ADRs (full set)
{governing_adrs}

{handoff}

---
tasks_md_item: {item.number}
idempotency_key: {idempotency_key_value}
"""


def build_task_bodies(
    *,
    change_dir: Path,
    change_slug: str,
    handoff_path: Path,
) -> TaskItemBundle:
    """Build per-item TaskItemBody records from `tasks.md`.

    Returns items in topological order — callers can iterate and emit in
    sequence, knowing that each item's `depends_on` parents have already been
    emitted (and therefore their task ids are already known).

    If tasks.md is absent the bundle is empty; callers should fall back to
    the legacy per-scenario-only emit path.
    """
    tasks_md_path = change_dir / "tasks.md"
    if not tasks_md_path.is_file():
        return TaskItemBundle(items=[])

    raw_items = parse_tasks_file(tasks_md_path)
    ordered = topological_order(raw_items)

    handoff = handoff_path.read_text(encoding="utf-8").strip()
    governing_adrs = _governing_adrs_section(change_dir)

    items: List[TaskItemBody] = []
    for raw in ordered:
        base_key = f"{change_slug}:{raw.slug}:{raw.hash()}"
        title = f"[{change_slug}] #{raw.number:02d} — {raw.title}"
        body = _render_task_item_body(
            item=raw,
            change_slug=change_slug,
            governing_adrs=governing_adrs,
            handoff=handoff,
            idempotency_key_value=base_key,
        )
        items.append(TaskItemBody(
            number=raw.number,
            title=title,
            body_markdown=body,
            idempotency_key=base_key,
            depends_on=list(raw.depends_on),
            spec_refs=[(s.capability, s.scenario_slug) for s in raw.spec_refs],
            non_behavioral=raw.non_behavioral,
        ))

    return TaskItemBundle(items=items)


# ---------------------------------------------------------------------------
# Emission — driving `hermes kanban create`
# ---------------------------------------------------------------------------


P2_STAGES = (
    ("impl", "scientia-implementer"),
    ("review", "scientia-reviewer"),
    ("integrate", "scientia-integrator"),
)


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with seconds precision."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hermes_comment(
    *,
    runner,
    tenant: str,
    task_id: str,
    body: str,
) -> None:
    argv = ["hermes", "kanban", "comment", task_id,
            "--tenant", tenant,
            "--body", body]
    proc = runner(argv, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes kanban comment failed (rc={proc.returncode}): "
            f"{proc.stderr or proc.stdout}"
        )


@dataclass
class TaskRecord:
    """Per-task metadata captured during emit, used downstream by the
    writeback step to produce one index file per Hermes task."""
    task_id: str
    idempotency_key: str
    role: str                        # "parent" | "aggregator" | "child" | "approval" | "task-item"
    title: str
    assignee: str
    scenario_slug: Optional[str] = None
    stage: Optional[str] = None      # "impl" | "review" | "integrate" | None
    parent_task_id: Optional[str] = None
    tasks_md_number: Optional[int] = None   # set for role=="task-item"
    capability: Optional[str] = None        # set for role=="task-item" or "child" (writeback grouping)


@dataclass
class EmitResult:
    ids_by_key: dict
    commands: List[List[str]] = field(default_factory=list)
    records: List[TaskRecord] = field(default_factory=list)


def _hermes_create(
    *,
    runner,
    tenant: str,
    workspace: str,
    title: str,
    body: str,
    idempotency_key: str,
    assignee: Optional[str],
    parents: List[str],
    triage: bool = False,
    skills: Optional[List[str]] = None,
) -> str:
    """Invoke `hermes kanban create` and return the resulting task id."""
    argv = ["hermes", "kanban", "create",
            "--idempotency-key", idempotency_key,
            "--tenant", tenant,
            "--workspace", workspace,
            "--body", body,
            "--json"]
    if assignee is not None:
        argv += ["--assignee", assignee]
    for p in parents:
        argv += ["--parent", p]
    if triage:
        argv.append("--triage")
    for s in (skills or []):
        argv += ["--skill", s]
    argv.append(title)  # positional title last

    proc = runner(argv, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes kanban create failed (rc={proc.returncode}): "
            f"{proc.stderr or proc.stdout}"
        )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    tid = payload.get("task_id") or payload.get("id")
    if not tid:
        raise RuntimeError(
            f"hermes kanban create returned no task id: {proc.stdout!r}"
        )
    return tid


def _stage_title(child_title: str, stage: str) -> str:
    # "[cap] scenario X" -> "[cap] scenario X — review"
    return f"{child_title} — {stage}"


def emit_tasks(
    *,
    bundle: TaskItemBundle,
    tenant: str,
    workspace: str,
    runner,
    skills: Optional[List[str]] = None,
    existing_keys: Optional[dict] = None,
) -> EmitResult:
    """Emit the tasks.md impl/review/integrate pipeline for every TaskItemBody.

    Each tasks.md item becomes a 3-stage pipeline:

        impl       (assignee: scientia-implementer)
          \\__ --parent: every prereq item's :integrate stage
        review     (assignee: scientia-reviewer)
          \\__ --parent: this item's :impl
        integrate  (assignee: scientia-integrator)
          \\__ --parent: this item's :review

    The :integrate task id is the public signal that other tasks (downstream
    tasks.md items, or per-scenario impls) depend on. `EmitResult.ids_by_key`
    maps stage keys (`<base>:impl`/`:review`/`:integrate`) to Hermes task ids.

    `workspace` should typically be the literal string `"worktree"` so each
    item's worker gets an isolated git worktree to commit into; the integrate
    stage then merges back to trunk before the next tasks.md item starts.
    Existing per-scenario rows continue to use `dir:<change_dir>` separately.
    """
    skills = skills or ["scientia-kanban-worker", "scientia-grill"]
    existing_keys = existing_keys or {}
    refreshed_at = _utcnow_iso()
    ids: dict = {}
    records: List[TaskRecord] = []

    pre = list(getattr(runner, "calls", []))

    # Track each item's :integrate task id so later items (and per-scenario
    # impls) can declare them as --parent. Keyed by tasks.md item number.
    integrate_ids: dict[int, str] = {}

    def _emit_with_refresh(key: str, body: str, **create_kwargs) -> str:
        tid = _hermes_create(
            runner=runner,
            tenant=tenant,
            workspace=workspace,
            idempotency_key=key,
            body=body,
            skills=skills,
            **create_kwargs,
        )
        if key in existing_keys:
            _hermes_comment(
                runner=runner,
                tenant=tenant,
                task_id=tid,
                body=f"refreshed-at: {refreshed_at}\n\n{body}",
            )
        return tid

    for item in bundle.items:
        # Prereq parents: the :integrate task_id of every item this depends on.
        # The bundle is in topological order so all such ids are already known.
        prereq_parents: List[str] = []
        for dep_num in item.depends_on:
            dep_int = integrate_ids.get(dep_num)
            if dep_int is not None:
                prereq_parents.append(dep_int)

        prev_id: Optional[str] = None
        for stage, stage_assignee in P2_STAGES:
            stage_key = f"{item.idempotency_key}:{stage}"
            stage_title = f"{item.title} — {stage}"
            parents = list(prereq_parents) if stage == "impl" else []
            if prev_id is not None:
                parents.append(prev_id)
            stage_id = _emit_with_refresh(
                key=stage_key,
                body=item.body_markdown,
                title=stage_title,
                assignee=stage_assignee,
                parents=parents,
            )
            ids[stage_key] = stage_id
            records.append(TaskRecord(
                task_id=stage_id, idempotency_key=stage_key,
                role="task-item", title=stage_title, assignee=stage_assignee,
                stage=stage, parent_task_id=prev_id,
                tasks_md_number=item.number,
            ))
            prev_id = stage_id

        integrate_ids[item.number] = prev_id  # last stage = integrate

    commands: List[List[str]] = []
    if hasattr(runner, "calls"):
        commands = list(runner.calls[len(pre):])

    return EmitResult(ids_by_key=ids, commands=commands, records=records)


def emit_one(
    *,
    bundle: BodyBundle,
    pattern: str,
    tenant: str,
    workspace: str,
    runner,
    skills: Optional[List[str]] = None,
    existing_keys: Optional[dict] = None,
    task_prereqs_by_scenario: Optional[dict] = None,
) -> EmitResult:
    """Emit a BodyBundle under the given collaboration pattern.

    Returns an EmitResult whose ids_by_key maps every emitted idempotency
    key to the Hermes task id that was created (or already existed).

    `existing_keys`: optional {idempotency_key: task_id} map from a pre-emit
    `hermes kanban list --json --tenant T` lookup. Any key in this map is
    treated as a re-emit — emit_one issues a `hermes kanban comment` with
    the freshly-computed body and a refreshed-at timestamp, since Hermes
    has no `update body` verb.

    `task_prereqs_by_scenario`: optional {scenario_slug: [task_id, ...]} map.
    For each child whose `scenario_slug` is in the map, the listed task ids
    are added as additional `--parent` edges on the child's `:impl` stage.
    Typically these point at the `:integrate` stage of relevant tasks.md
    rows, so a scenario can't start until its shared-infrastructure prereqs
    are merged to trunk.
    """
    if pattern == "refuse":
        raise ValueError(
            "Pattern is 'refuse' — the governing ADR is deprecated or "
            "superseded without a successor. Resolve the ADR before emitting."
        )

    skills = skills or ["scientia-kanban-worker", "scientia-grill"]
    existing_keys = existing_keys or {}
    task_prereqs_by_scenario = task_prereqs_by_scenario or {}
    refreshed_at = _utcnow_iso()
    ids: dict = {}
    commands: List[List[str]] = []
    records: List[TaskRecord] = []

    def _emit_with_refresh(key: str, body: str, **create_kwargs) -> str:
        tid = _hermes_create(
            runner=runner,
            tenant=tenant,
            workspace=workspace,
            idempotency_key=key,
            body=body,
            skills=skills,
            **create_kwargs,
        )
        if key in existing_keys:
            _hermes_comment(
                runner=runner,
                tenant=tenant,
                task_id=tid,
                body=f"refreshed-at: {refreshed_at}\n\n{body}",
            )
        return tid

    # Snapshot runner.calls before/after so we can capture commands locally
    # even when a caller passes a runner that doesn't track them.
    pre = list(getattr(runner, "calls", []))

    parent_deps: List[str] = []

    # P5 prefix: one --triage approval gate that the parent waits on.
    if pattern == "P5-human-in-loop":
        approval_key = f"{bundle.parent.idempotency_key}:approval"
        approval_title = f"{bundle.parent.title} — approval"
        approval_id = _emit_with_refresh(
            key=approval_key,
            body="Human approval gate. Promote to scientia-implementer when ready.",
            title=approval_title,
            assignee="none",
            parents=[],
            triage=True,
        )
        ids[approval_key] = approval_id
        records.append(TaskRecord(
            task_id=approval_id, idempotency_key=approval_key,
            role="approval", title=approval_title, assignee="none",
        ))
        parent_deps.append(approval_id)

    # Parent task
    parent_id = _emit_with_refresh(
        key=bundle.parent.idempotency_key,
        body=bundle.parent.body_markdown,
        title=bundle.parent.title,
        assignee=bundle.parent.assignee,
        parents=parent_deps,
    )
    ids[bundle.parent.idempotency_key] = parent_id
    records.append(TaskRecord(
        task_id=parent_id, idempotency_key=bundle.parent.idempotency_key,
        role="parent", title=bundle.parent.title, assignee=bundle.parent.assignee,
    ))

    # Per-scenario pipeline stages (P2 and P5 share the same shape downstream)
    terminal_stage_ids: List[str] = []
    for child in bundle.children:
        prev_id = parent_id
        # Tasks.md prereqs apply only to the :impl stage (the gating step).
        # Review/integrate inherit the natural impl→review→integrate chain.
        extra_impl_parents: List[str] = []
        if child.scenario_slug and child.scenario_slug in task_prereqs_by_scenario:
            extra_impl_parents = list(task_prereqs_by_scenario[child.scenario_slug])
        for stage, stage_assignee in P2_STAGES:
            stage_key = f"{child.idempotency_key}:{stage}"
            stage_title = _stage_title(child.title, stage)
            stage_parents = [prev_id]
            if stage == "impl":
                stage_parents.extend(extra_impl_parents)
            stage_id = _emit_with_refresh(
                key=stage_key,
                body=child.body_markdown,
                title=stage_title,
                assignee=stage_assignee,
                parents=stage_parents,
            )
            ids[stage_key] = stage_id
            records.append(TaskRecord(
                task_id=stage_id, idempotency_key=stage_key, role="child",
                title=stage_title, assignee=stage_assignee,
                scenario_slug=child.scenario_slug, stage=stage,
                parent_task_id=prev_id,
            ))
            prev_id = stage_id
        terminal_stage_ids.append(prev_id)

    # Aggregator: depends on every terminal stage
    agg_id = _emit_with_refresh(
        key=bundle.aggregator.idempotency_key,
        body=bundle.aggregator.body_markdown,
        title=bundle.aggregator.title,
        assignee=bundle.aggregator.assignee,
        parents=terminal_stage_ids,
    )
    ids[bundle.aggregator.idempotency_key] = agg_id
    records.append(TaskRecord(
        task_id=agg_id, idempotency_key=bundle.aggregator.idempotency_key,
        role="aggregator", title=bundle.aggregator.title,
        assignee=bundle.aggregator.assignee,
    ))

    # Capture only the commands issued during this call (in case the runner
    # is shared across tests).
    if hasattr(runner, "calls"):
        commands = list(runner.calls[len(pre):])

    return EmitResult(ids_by_key=ids, commands=commands, records=records)


# ---------------------------------------------------------------------------
# Orchestration: tie preflight + pattern + bodies + emit + writeback together
# ---------------------------------------------------------------------------


class PreflightRefused(RuntimeError):
    """Raised when one or more preflight gates refuse the emit."""

    def __init__(self, reasons: List[str]):
        super().__init__("\n".join(reasons))
        self.reasons = reasons


def _split_change_id(change_id: str) -> tuple[str, str]:
    """`ansible/2026-05-20-foo` → ("ansible", "2026-05-20-foo")."""
    if "/" not in change_id:
        raise ValueError(
            f"Bad change_id {change_id!r}; expected '<tenant>/<change-slug>'."
        )
    tenant, slug = change_id.split("/", 1)
    return tenant, slug


def _scenario_prereq_map(
    *,
    items: List["TaskItemBody"],
    ids_by_key: dict,
) -> dict:
    """Build a {(capability, scenario_slug): [integrate_task_id, ...]} map.

    For each per-scenario impl row, this map names the tasks.md `:integrate`
    task ids that must complete before the scenario's impl is allowed to
    start. Two sources contribute:

    - **Per-scenario prereqs**: items whose `spec_refs` include
      `(capability, scenario_slug)`, plus their transitive `depends_on`
      closure (via `tasks_md.items_for_scenario`-equivalent traversal).
    - **Shared infrastructure**: items with no `@spec` marker that aren't
      marked non-behavioral. Universal prereqs for every scenario.

    Deduplicated per scenario. Non-behavioral items (docs/CI tail of
    tasks.md, which depend on the main pipeline rather than the other way
    around) are excluded from shared infrastructure.

    Returns {} when `items` is empty.
    """
    if not items:
        return {}

    by_number = {item.number: item for item in items}

    # Universal prereqs: items with no `@spec` markers AND no `depends_on`
    # parents. These are the true root-scaffolding rows that every scenario
    # impl needs before it can do anything. The set is deliberately narrow
    # so we don't serialise scenarios on each other's specialty cross-cutting
    # items — those flow to the relevant scenarios through the
    # `depends_on` closure below.
    def _is_universal(item: "TaskItemBody") -> bool:
        if item.spec_refs:
            return False
        return not item.depends_on

    universal = [item for item in items if _is_universal(item)]
    universal_ids = [
        ids_by_key[f"{item.idempotency_key}:integrate"]
        for item in universal
        if f"{item.idempotency_key}:integrate" in ids_by_key
    ]

    # Per-scenario closure: walk `depends_on` from each seed item.
    def _closure(seeds: list) -> list:
        seen: set = set()
        stack = list(seeds)
        out = []
        while stack:
            item = stack.pop()
            if item.number in seen:
                continue
            seen.add(item.number)
            out.append(item)
            for dep_num in item.depends_on:
                dep = by_number.get(dep_num)
                if dep is not None and dep.number not in seen:
                    stack.append(dep)
        return out

    out: dict = {}
    # Collect every (capability, scenario_slug) pair referenced by any item.
    all_refs: set = set()
    for item in items:
        for (cap, scn) in item.spec_refs:
            all_refs.add((cap, scn))

    for (cap, scn) in all_refs:
        seeds = [
            item for item in items
            if (cap, scn) in item.spec_refs
        ]
        closure_items = _closure(seeds)
        scenario_ids = [
            ids_by_key[f"{item.idempotency_key}:integrate"]
            for item in closure_items
            if f"{item.idempotency_key}:integrate" in ids_by_key
        ]
        # Dedupe while preserving order: universals first (foundational),
        # then per-scenario closure items.
        seen_ids: set = set()
        combined: List[str] = []
        for tid in list(universal_ids) + scenario_ids:
            if tid not in seen_ids:
                seen_ids.add(tid)
                combined.append(tid)
        out[(cap, scn)] = combined

    return out


def _lookup_existing_keys(*, runner, tenant: str) -> dict:
    """Pre-emit lookup: ask Hermes for existing tasks in this tenant and
    build {idempotency_key: task_id} for any that carry one.
    """
    argv = ["hermes", "kanban", "list", "--tenant", tenant, "--json"]
    proc = runner(argv, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    try:
        items = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
    out: dict = {}
    for item in items:
        key = item.get("idempotency_key") or item.get("key")
        tid = item.get("id") or item.get("task_id")
        if key and tid:
            out[key] = tid
    return out


def orchestrate(
    *,
    repo_root: Path,
    change_id: str,
    config: dict,
    processes_json_path: Path,
    handoff_path: Path,
    runner,
    dry_run: bool = False,
    only_spec: Optional[str] = None,
    trunk: str = "main",
    hermes_config_path: Optional[Path] = None,
) -> dict:
    """Full per-change emit flow. Returns a summary dict.

    Steps:
      1. Resolve change_dir, tenant, change_slug
      2. Run preflights — raises PreflightRefused if any fail
      3. For each spec under change_dir/specs/ (filtered by only_spec):
         a. Resolve governing ADR + its status
         b. pattern = pattern_for(adr_status, tenant, config)
         c. Build BodyBundle
         d. Look up existing keys (unless dry_run)
         e. Emit via emit_one (or via a recording dry-run runner)
         f. Writeback: spec `## Kanban Tasks`, per-task index, log
      4. Return {"pattern": ..., "tasks": N, "commands": [...]}.
    """
    tenant, change_slug = _split_change_id(change_id)
    change_dir = repo_root / "openspec" / "changes" / f"{tenant}-{change_slug}"

    block_on = config.get("verify", {}).get("block_on_severity", "critical")
    hermes_cfg = config.get("hermes", {}) or {}
    desired_concurrency = hermes_cfg.get("max_concurrent_children", 3)
    profiles_block = hermes_cfg.get("profiles")
    profile_names = hermes_cfg.get("profile_names")
    if hermes_config_path is None:
        hermes_config_path = Path.home() / ".hermes" / "config.yaml"
    if dry_run:
        # Inspecting what would emit doesn't require a running gateway or a
        # working hermes CLI on PATH. Other gates (verify, ADR, on-trunk)
        # still apply — they tell you whether emit would be appropriate.
        reasons = [
            r for r in (
                check_verify_severity(change_dir, block_on=block_on),
                check_adr_status(change_dir),
                check_spec_on_trunk(change_dir, trunk=trunk),
            )
            if r is not None
        ]
    else:
        reasons = preflight(
            change_dir=change_dir,
            processes_json_path=processes_json_path,
            block_on_severity=block_on,
            trunk=trunk,
            desired_concurrency=desired_concurrency,
            hermes_config_path=hermes_config_path,
            profiles_block=profiles_block,
            profile_names=profile_names,
        )
    if reasons:
        raise PreflightRefused(reasons)

    adr_id = governing_adr(change_dir)
    adr_status = _read_frontmatter(
        next((change_dir / "adr").glob("*.md")).read_text(encoding="utf-8")
    ).get("status", "")
    # We want the status of the governing ADR specifically, not just any.
    for adr_file in (change_dir / "adr").glob("*.md"):
        fm = _read_frontmatter(adr_file.read_text(encoding="utf-8"))
        if (fm.get("adr_id") or "").upper() == adr_id.upper():
            adr_status = fm.get("status") or adr_status
            break

    pattern = pattern_for(adr_status, tenant=tenant, config=config)

    specs = sorted((change_dir / "specs").glob("*/spec.md"))
    if only_spec:
        specs = [s for s in specs if s.parent.name == only_spec]
    if not specs:
        raise PreflightRefused([f"No specs found in {change_dir/'specs'} (only_spec={only_spec!r})"])

    # In dry-run, swap the live runner for a recording stub that returns fake ids.
    if dry_run:
        live_runner = runner

        class _DryRunner:
            def __init__(self):
                self.calls: list[list[str]] = []
                self._n = 0

            def __call__(self, argv, **kw):
                self.calls.append(list(argv))
                if "create" in argv:
                    self._n += 1
                    return SimpleNamespace(returncode=0,
                                           stdout=json.dumps({"task_id": f"dry_{self._n:02d}"}),
                                           stderr="")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

        runner = _DryRunner()

    total_tasks = 0
    commands: List[List[str]] = []

    # ---- Phase 1: tasks.md items ----
    # Emit shared-infrastructure rows FIRST so their :integrate task ids are
    # known when we wire per-scenario impls. If tasks.md is absent, the bundle
    # is empty and this phase is a no-op (back-compat with pre-tasks.md repos).
    task_bundle = build_task_bodies(
        change_dir=change_dir,
        change_slug=change_slug,
        handoff_path=handoff_path,
    )
    if dry_run:
        task_existing_keys: dict = {}
    else:
        task_existing_keys = _lookup_existing_keys(runner=runner, tenant=tenant)

    task_result: Optional[EmitResult] = None
    if task_bundle.items:
        task_result = emit_tasks(
            bundle=task_bundle,
            tenant=tenant,
            workspace="worktree",
            runner=runner,
            existing_keys=task_existing_keys,
        )
        total_tasks += len(task_result.ids_by_key)
        commands.extend(task_result.commands)

    # Build the (capability, scenario_slug) → [task integrate task_ids] map
    # that emit_one needs to wire per-scenario impls.
    task_prereqs_by_scenario_full = _scenario_prereq_map(
        items=task_bundle.items,
        ids_by_key=task_result.ids_by_key if task_result else {},
    )

    # ---- Phase 2: per-spec scenarios ----
    for spec_path in specs:
        capability = spec_path.parent.name
        bundle = build_bodies(
            change_dir=change_dir,
            spec_path=spec_path,
            handoff_path=handoff_path,
        )

        # Per-emit_one contract: keys are bare scenario slugs (already unique
        # within a spec). Filter the full map down to this capability.
        scenario_prereqs = {
            scn: task_ids
            for (cap, scn), task_ids in task_prereqs_by_scenario_full.items()
            if cap == capability
        }

        if dry_run:
            existing_keys: dict = {}
        else:
            existing_keys = _lookup_existing_keys(runner=runner, tenant=tenant)

        result = emit_one(
            bundle=bundle,
            pattern=pattern,
            tenant=tenant,
            workspace=f"dir:{change_dir.resolve()}",
            runner=runner,
            existing_keys=existing_keys,
            task_prereqs_by_scenario=scenario_prereqs,
        )
        total_tasks += len(result.ids_by_key)
        commands.extend(result.commands)

        if dry_run:
            continue

        # ---- Writeback (real run only) ----
        principals = _principals_for_writeback(bundle, result)
        write_kanban_section(spec_path, principals=principals)

        spec_rel = str(spec_path.relative_to(repo_root))

        # One index entry per emitted Hermes task — including each pipeline
        # stage — so `development/tasks/<tenant>/<change>/<task_id>.md`
        # is a 1:1 traceability map back to its spec/scenario/stage.
        for rec in result.records:
            write_index_entry(
                repo_root=repo_root,
                tenant=tenant,
                change_id=change_slug,
                capability=capability,
                task_id=rec.task_id,
                idempotency_key=rec.idempotency_key,
                role=rec.role,
                scenario_slug=rec.scenario_slug,
                parent_task_id=rec.parent_task_id,
                spec_rel_path=spec_rel,
                title=rec.title,
                assignee=rec.assignee,
            )

    # Tasks.md index entries (cross-spec, since a tasks.md item can serve
    # multiple capabilities). Written under the tenant/change root, not
    # nested under a capability.
    if not dry_run and task_result is not None:
        for rec in task_result.records:
            write_index_entry(
                repo_root=repo_root,
                tenant=tenant,
                change_id=change_slug,
                capability="(tasks.md)",
                task_id=rec.task_id,
                idempotency_key=rec.idempotency_key,
                role=rec.role,
                scenario_slug=None,
                parent_task_id=rec.parent_task_id,
                spec_rel_path=f"openspec/changes/{tenant}-{change_slug}/tasks.md",
                title=rec.title,
                assignee=rec.assignee,
            )

    if not dry_run:
        append_log_emitted(
            repo_root=repo_root,
            tenant=tenant,
            change_id=change_slug,
            pattern=pattern,
            tasks=total_tasks,
        )

    return {"pattern": pattern, "tasks": total_tasks, "commands": commands}


def _principals_for_writeback(bundle: BodyBundle, result: "EmitResult") -> dict:
    """Distill the per-spec writeback bullets from an EmitResult.

    The spec's `## Kanban Tasks` section lists ONE entry per scenario (the
    first stage — `:impl` for P2), plus the parent and aggregator.
    """
    children = []
    for child in bundle.children:
        impl_key = f"{child.idempotency_key}:impl"
        impl_id = result.ids_by_key.get(impl_key, "")
        children.append({
            "task_id": impl_id,
            "idempotency_key": child.idempotency_key,
            "scenario_slug": child.scenario_slug,
            "title": child.title,
            "assignee": child.assignee,
        })
    return {
        "parent": {
            "task_id": result.ids_by_key[bundle.parent.idempotency_key],
            "idempotency_key": bundle.parent.idempotency_key,
            "title": bundle.parent.title,
            "assignee": bundle.parent.assignee,
        },
        "aggregator": {
            "task_id": result.ids_by_key[bundle.aggregator.idempotency_key],
            "idempotency_key": bundle.aggregator.idempotency_key,
            "title": bundle.aggregator.title,
            "assignee": bundle.aggregator.assignee,
        },
        "children": children,
    }


# ---------------------------------------------------------------------------
# Writeback: spec.md `## Kanban Tasks`, index entries, development/log.md
# ---------------------------------------------------------------------------


_KANBAN_SECTION_RE = re.compile(
    r"^## Kanban Tasks\b.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL
)

_KANBAN_SIGIL = (
    "<!-- Populated by scientia-kanban-emit on first emit. Do not hand-edit. -->"
)


def _render_kanban_section(principals: dict) -> str:
    lines = ["## Kanban Tasks", _KANBAN_SIGIL, ""]
    parent = principals["parent"]
    aggregator = principals["aggregator"]
    lines.append(
        f"- **Parent** — `{parent['task_id']}` — `{parent['idempotency_key']}`"
    )
    lines.append(
        f"- **Aggregator** — `{aggregator['task_id']}` — `{aggregator['idempotency_key']}`"
    )
    for child in principals.get("children", []):
        slug = child.get("scenario_slug") or "child"
        lines.append(
            f"- **Child: {slug}** — `{child['task_id']}` — `{child['idempotency_key']}`"
        )
    # Trailing newline so the section is well-formed at EOF.
    return "\n".join(lines) + "\n"


def write_kanban_section(spec_path: Path, *, principals: dict) -> None:
    """Replace (or append) the `## Kanban Tasks` section in spec.md.

    The regex used matches everything from `## Kanban Tasks` up to the next
    `## ` heading or EOF. This must round-trip through
    `idempotency_key.KANBAN_SECTION_RE` — see test_writeback for the round-trip
    assertion.
    """
    text = spec_path.read_text(encoding="utf-8")
    new_section = _render_kanban_section(principals)

    if _KANBAN_SECTION_RE.search(text):
        text = _KANBAN_SECTION_RE.sub(new_section, text)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + new_section

    spec_path.write_text(text, encoding="utf-8")


def write_index_entry(
    *,
    repo_root: Path,
    tenant: str,
    change_id: str,
    capability: str,
    task_id: str,
    idempotency_key: str,
    role: str,                       # "parent" | "child" | "aggregator"
    scenario_slug: Optional[str],
    parent_task_id: Optional[str],
    spec_rel_path: str,
    title: str,
    assignee: str,
) -> Path:
    """Write development/tasks/<tenant>/<change_id>/<task_id>.md.

    Returns the resulting path.
    """
    out_dir = repo_root / "development" / "tasks" / tenant / change_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{task_id}.md"

    fm_lines = [
        "---",
        f"task_id: {task_id}",
        "type: kanban-index",
        f"tenant: {tenant}",
        f"change_id: {change_id}",
        f"capability: {capability}",
        f"role: {role}",
    ]
    if scenario_slug is not None:
        fm_lines.append(f"scenario: {scenario_slug}")
    fm_lines.append(f"idempotency_key: {idempotency_key}")
    fm_lines.append(f"spec_path: {spec_rel_path}")
    if parent_task_id is not None:
        fm_lines.append(f"parent_task: {parent_task_id}")
    fm_lines.append(f"created: {_utcnow_iso()[:10]}")  # YYYY-MM-DD
    fm_lines.append("---")

    body_lines = [
        "",
        f"## {role.capitalize()} Task",
        "",
        f"- **Hermes ID:** `{task_id}`",
        f"- **Title:** {title}",
        f"- **Assignee:** {assignee}",
    ]
    if scenario_slug:
        body_lines.append(f"- **Scenario:** {scenario_slug}")
    if parent_task_id:
        body_lines.append(f"- **Parent:** {parent_task_id}")

    out_path.write_text("\n".join(fm_lines + body_lines) + "\n", encoding="utf-8")
    return out_path


def append_log_emitted(
    *,
    repo_root: Path,
    tenant: str,
    change_id: str,
    pattern: str,
    tasks: int,
) -> None:
    """Append the canonical `emitted` line to development/log.md."""
    log_path = repo_root / "development" / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"- {_utcnow_iso()} — scientia-kanban-emit — emitted — "
        f"{tenant}/{change_id} — pattern={pattern} tasks={tasks}\n"
    )
    if log_path.is_file():
        existing = log_path.read_text(encoding="utf-8")
        if not existing.endswith("\n"):
            existing += "\n"
        log_path.write_text(existing + line, encoding="utf-8")
    else:
        log_path.write_text(line, encoding="utf-8")


def pattern_for(adr_status: str, *, tenant: str, config: dict) -> str:
    """Resolve the per-spec collaboration pattern.

    Reads `config["emit"]["default_pattern_by_adr_status"]` as the base
    mapping; if `tenant` is in `config["emit"]["require_approval_tenants"]`,
    the result is forced to `"P5-human-in-loop"` regardless of ADR status.

    Raises:
        KeyError: if `config["emit"]` is missing.
        ValueError: if `adr_status` is not in the configured mapping.
    """
    emit_cfg = config["emit"]
    mapping = emit_cfg.get("default_pattern_by_adr_status", {})
    if adr_status not in mapping:
        raise ValueError(
            f"Unknown ADR status {adr_status!r}; "
            f"expected one of {sorted(mapping)}."
        )

    if tenant in emit_cfg.get("require_approval_tenants", []):
        return "P5-human-in-loop"

    return mapping[adr_status]


def preflight(
    *,
    change_dir: Path,
    processes_json_path: Path,
    block_on_severity: str,
    trunk: str,
    desired_concurrency: int,
    hermes_config_path: Path,
    profiles_block: Optional[dict] = None,
    profile_names: Optional[dict] = None,
    profile_runner=None,
) -> List[str]:
    """Run every preflight gate and collect refusal reasons.

    Returns an empty list when all gates pass.

    `profiles_block` and `profile_names` come from development/config.yaml's
    `hermes.profiles` and `hermes.profile_names`. When `profiles_block` is
    falsy, the model-config drift check is a no-op (hands-off default). The
    profile-existence gate runs unconditionally (independent of
    `profiles_block`), since a missing profile would silently strand
    emitted tasks as `skipped_nonspawnable`.

    `profile_runner` is late-bound to `subprocess.run` when omitted so
    test patches of `subprocess.run` take effect.
    """
    if profile_runner is None:
        profile_runner = subprocess.run
    reasons: List[str] = []
    for reason in (
        check_hermes_on_path(),
        check_gateway(processes_json_path),
        check_concurrency_cap(
            desired=desired_concurrency,
            hermes_config_path=hermes_config_path,
        ),
        check_profiles_exist(
            profile_names=profile_names,
            runner=profile_runner,
        ),
        check_profile_models_drift(
            profiles_block=profiles_block,
            profile_names=profile_names,
            runner=profile_runner,
        ),
        check_verify_severity(change_dir, block_on=block_on_severity),
        check_adr_status(change_dir),
        check_spec_on_trunk(change_dir, trunk=trunk),
    ):
        if reason is not None:
            reasons.append(reason)
    return reasons


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_config(path: Path) -> dict:
    """Read development/config.yaml. Stdlib-only minimal YAML reader for
    the subset scientia uses (nested mappings, scalar values, no anchors)."""
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return _parse_yaml_subset(text)


def _parse_yaml_subset(text: str) -> dict:
    """Parse a YAML subset: nested 2-space-indented mappings of scalars
    and inline `[a, b]` lists. Sufficient for development/config.yaml.
    """
    lines = [
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    def _scalar(v: str):
        v = v.strip()
        if len(v) >= 2 and (
            (v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")
        ):
            return v[1:-1]
        if v in ("null", "~", ""):
            return None
        if v in ("true", "True"):
            return True
        if v in ("false", "False"):
            return False
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if not inner:
                return []
            return [_scalar(p) for p in inner.split(",")]
        try:
            return int(v)
        except ValueError:
            return v

    # Build a tree from indentation.
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for raw in lines:
        stripped = raw.lstrip(" ")
        indent = len(raw) - len(stripped)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.rstrip()
        if value.strip() == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _scalar(value)
    return root


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: `python3 emit.py --change <tenant>/<change-slug> [...]`."""
    p = argparse.ArgumentParser(
        prog="scientia-kanban-emit",
        description="Emit one parent + N children + 1 aggregator per spec.",
    )
    p.add_argument("--change", required=True,
                   help="Change id: '<tenant>/<change-slug>'.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be emitted without calling hermes.")
    p.add_argument("--only-spec", default=None,
                   help="Capability slug filter (default: all specs).")
    p.add_argument("--repo-root", type=Path, default=Path.cwd(),
                   help="Repo root (default: cwd).")
    p.add_argument("--processes-json", type=Path,
                   default=Path.home() / ".hermes" / "processes.json")
    p.add_argument("--handoff", type=Path,
                   default=Path(__file__).resolve().parent.parent / "references" / "HANDOFF_SCHEMA.md")
    p.add_argument("--config", type=Path, default=None,
                   help="Path to development/config.yaml (default: <repo-root>/development/config.yaml).")
    p.add_argument("--trunk", default="main",
                   help="Trunk branch name for git:spec-on-trunk (default: main).")
    args = p.parse_args(argv)

    config_path = args.config or (args.repo_root / "development" / "config.yaml")
    config = _load_config(config_path)
    if not config.get("emit", {}).get("default_pattern_by_adr_status"):
        # Default fallback matching the scientia bundle's shipped config.
        config = {
            "emit": {
                "default_pattern_by_adr_status": {
                    "accepted": "P2-pipeline",
                    "proposed": "P5-human-in-loop",
                    "deprecated": "refuse",
                    "superseded": "refuse",
                },
                "require_approval_tenants": [],
            },
            "verify": {"block_on_severity": "critical"},
            "hermes": {"max_concurrent_children": 3},
            **config,
        }
    else:
        # Ensure hermes.max_concurrent_children has a default even when the
        # rest of the config is present — older bundles' configs predate the key.
        config.setdefault("hermes", {}).setdefault("max_concurrent_children", 3)

    try:
        result = orchestrate(
            repo_root=args.repo_root.resolve(),
            change_id=args.change,
            config=config,
            processes_json_path=args.processes_json,
            handoff_path=args.handoff,
            runner=subprocess.run,
            dry_run=args.dry_run,
            only_spec=args.only_spec,
            trunk=args.trunk,
        )
    except PreflightRefused as e:
        print("PREFLIGHT REFUSED:", file=sys.stderr)
        for reason in e.reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"[dry-run] pattern={result['pattern']} tasks={result['tasks']}")
        for cmd in result["commands"]:
            print("  " + " ".join(_shquote(a) for a in cmd))
    else:
        print(f"emitted: pattern={result['pattern']} tasks={result['tasks']}")
    return 0


def _shquote(s: str) -> str:
    """Lightweight shell-quote for the dry-run output."""
    if not s or any(c in s for c in " \t\n\"'\\$`"):
        return "'" + s.replace("'", "'\\''") + "'"
    return s


if __name__ == "__main__":
    sys.exit(main())
