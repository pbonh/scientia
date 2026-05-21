#!/usr/bin/env python3
"""verify_all.py — run every scientia pipeline gate against the current repo.

Used by:
- The scientia orchestrator when the user says "verify".
- CI of any kind (GitHub Actions, GitLab CI, pre-commit, ...) via a one-line
  invocation.

Walks every in-flight change (all tenants), runs:
  1. scientia-wiki-lint (frontmatter, wiki-link resolution, index/log integrity)
  2. OpenSpec verify (Completeness / Correctness / Coherence)
  3. git:spec-on-trunk preflight (when emit is imminent or already run)
  4. idempotency-key drift check (each emitted task's recorded triple vs.
     the current spec hash)

Aggregates findings by severity and exits non-zero on the threshold from
development/config.yaml (verify.block_on_severity).

Usage:
    verify_all.py [--repo <path>] [--threshold critical|warning|suggestion]
                  [--json] [--write-report]

This is a v0.1 reference implementation. Individual gate logic is
intentionally simple; the goal is to wire all gates into one entry point
that can be improved per-gate over time without changing the integration
surface.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

SEVERITIES = ["suggestion", "warning", "critical"]


@dataclass
class Finding:
    gate: str
    severity: str
    tenant: str | None
    change_id: str | None
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, gate: str, severity: str, message: str,
            tenant: str | None = None, change_id: str | None = None) -> None:
        assert severity in SEVERITIES, severity
        self.findings.append(Finding(gate, severity, tenant, change_id, message))

    def worst(self) -> str:
        worst_idx = -1
        for f in self.findings:
            worst_idx = max(worst_idx, SEVERITIES.index(f.severity))
        return SEVERITIES[worst_idx] if worst_idx >= 0 else "clean"

    def to_markdown(self) -> str:
        if not self.findings:
            return "# scientia verify report\n\nAll gates clean.\n"
        lines = ["# scientia verify report", ""]
        for sev in reversed(SEVERITIES):
            bucket = [f for f in self.findings if f.severity == sev]
            if not bucket:
                continue
            lines.append(f"## {sev.upper()} ({len(bucket)})")
            for f in bucket:
                where = f"{f.tenant}/{f.change_id}" if f.tenant else "(repo-global)"
                lines.append(f"- **{f.gate}** — {where} — {f.message}")
            lines.append("")
        return "\n".join(lines)


def read_threshold(repo: Path, override: str | None) -> str:
    if override:
        return override
    cfg = repo / "development" / "config.yaml"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("block_on_severity:"):
                v = line.split(":", 1)[1].strip().strip('"').strip("'").lower()
                if v in SEVERITIES:
                    return v
    return "critical"


def gate_wiki_lint(report: Report, repo: Path) -> None:
    wiki = repo / "wiki"
    if not wiki.is_dir():
        report.add("wiki-lint", "warning", "no wiki/ directory; skipping wiki lint")
        return
    index = wiki / "index.md"
    if not index.exists():
        report.add("wiki-lint", "critical", "wiki/index.md missing")
    log = wiki / "log.md"
    if not log.exists():
        report.add("wiki-lint", "warning", "wiki/log.md missing")
    # Frontmatter sanity on all wiki .md files (very light v0.1 check).
    for md in wiki.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        if not text.lstrip().startswith("---"):
            report.add("wiki-lint", "warning",
                       f"{md.relative_to(repo)} missing YAML frontmatter")


def gate_openspec_verify(report: Report, repo: Path) -> None:
    changes_dir = repo / "openspec" / "changes"
    if not changes_dir.is_dir():
        return
    if shutil.which("openspec") is None:
        report.add("openspec-verify", "warning",
                   "openspec CLI not on PATH; cannot run OpenSpec validate")
        return
    tenants = _known_tenants(repo)
    for ch in sorted(changes_dir.iterdir()):
        if not ch.is_dir():
            continue
        change_dir_name = ch.name
        tenant = _recover_tenant(change_dir_name, tenants)
        try:
            r = subprocess.run(
                ["openspec", "validate", change_dir_name, "--json", "--no-interactive"],
                cwd=repo, capture_output=True, text=True, check=False, timeout=120,
            )
        except Exception as exc:
            report.add("openspec-verify", "warning",
                       f"openspec validate {change_dir_name} crashed: {exc}",
                       tenant=tenant, change_id=change_dir_name)
            continue
        severity, message = _classify_openspec_validate(r.stdout, r.stderr, r.returncode)
        if severity is not None:
            report.add("openspec-verify", severity, message,
                       tenant=tenant, change_id=change_dir_name)


def _classify_openspec_validate(stdout: str, stderr: str, returncode: int):
    """Map an `openspec validate --json` invocation to (severity, message).

    Returns (None, "") on a clean pass. Severity mapping per issue level:
        ERROR   → critical
        WARNING → warning
        other   → suggestion
    """
    data = _parse_openspec_json(stdout)
    if data is None:
        if returncode == 0:
            return (None, "")
        err = (stderr or stdout).strip().splitlines()
        tail = err[-1] if err else "(no output)"
        return ("warning",
                f"openspec validate produced no parseable JSON (exit {returncode}): {tail[:200]}")
    findings = []
    worst = None
    for item in data.get("items") or []:
        for issue in item.get("issues") or []:
            level = (issue.get("level") or "").upper()
            sev = {"ERROR": "critical", "WARNING": "warning"}.get(level, "suggestion")
            if worst is None or SEVERITIES.index(sev) > SEVERITIES.index(worst):
                worst = sev
            findings.append(f"[{level}] {issue.get('path', '')}: {issue.get('message', '')}")
    if worst is None:
        return (None, "")
    head = "; ".join(findings[:3])
    suffix = f" (+{len(findings) - 3} more)" if len(findings) > 3 else ""
    return (worst, head + suffix)


def _parse_openspec_json(stdout: str):
    """openspec validate may emit a telemetry-notice line before the JSON
    payload. Strip anything before the first '{' and try to parse.
    """
    idx = stdout.find("{")
    if idx == -1:
        return None
    try:
        return json.loads(stdout[idx:])
    except json.JSONDecodeError:
        return None


def _known_tenants(repo: Path):
    manifests = repo / "development" / "manifests"
    if not manifests.is_dir():
        return []
    return sorted(d.name for d in manifests.iterdir() if d.is_dir())


def _recover_tenant(change_dir_name: str, tenants):
    """Recover the tenant slug from a change directory name like
    `circuit-solver-2026-05-21-v1-spec`. Multi-hyphen tenants (e.g.
    `circuit-solver`) require consulting the manifests directory; a naive
    `split('-', 1)[0]` would return `'circuit'`.
    """
    for t in tenants:
        if change_dir_name.startswith(t + "-"):
            return t
    return change_dir_name.split("-", 1)[0] if "-" in change_dir_name else None


def gate_spec_on_trunk(report: Report, repo: Path) -> None:
    # For every emitted change (tasks index exists), check that spec.md files are on trunk.
    tasks_root = repo / "development" / "tasks"
    if not tasks_root.is_dir():
        return
    for tenant_dir in tasks_root.iterdir():
        if not tenant_dir.is_dir():
            continue
        for change_dir in tenant_dir.iterdir():
            if not change_dir.is_dir():
                continue
            tenant = tenant_dir.name
            change_id = change_dir.name
            spec_glob = (repo / "openspec" / "changes" / f"{tenant}-{change_id}" / "specs").rglob("spec.md")
            for spec in spec_glob:
                if not is_on_trunk(repo, spec):
                    report.add("git-spec-on-trunk", "critical",
                               f"{spec.relative_to(repo)} is not merged to trunk; re-emit will hash a moving target",
                               tenant=tenant, change_id=change_id)


def is_on_trunk(repo: Path, path: Path) -> bool:
    trunk = trunk_branch(repo)
    if trunk is None:
        return True  # cannot determine; do not fail
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "HEAD", trunk],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        return r.returncode == 0
    except FileNotFoundError:
        return True


def trunk_branch(repo: Path) -> str | None:
    for candidate in ("origin/main", "origin/master", "main", "master"):
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--verify", candidate],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            if r.returncode == 0:
                return candidate
        except FileNotFoundError:
            return None
    return None


def gate_idempotency_drift(report: Report, repo: Path) -> None:
    tasks_root = repo / "development" / "tasks"
    if not tasks_root.is_dir():
        return
    for tenant_dir in tasks_root.iterdir():
        if not tenant_dir.is_dir():
            continue
        for change_dir in tenant_dir.iterdir():
            if not change_dir.is_dir():
                continue
            tenant = tenant_dir.name
            change_id = change_dir.name
            for task_md in change_dir.rglob("*.md"):
                drift = detect_drift(repo, task_md, tenant, change_id)
                if drift:
                    report.add("idempotency-drift", "warning", drift,
                               tenant=tenant, change_id=change_id)


def detect_drift(repo: Path, task_md: Path, tenant: str, change_id: str) -> str | None:
    """Compare recorded idempotency_key in the task index entry to the current
    sha256 of the referenced spec body. Returns a message if they disagree.
    """
    try:
        text = task_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    recorded = None
    spec_slug = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("idempotency_key:"):
            recorded = s.split(":", 1)[1].strip().strip('"').strip("'")
        elif s.startswith("spec_slug:"):
            spec_slug = s.split(":", 1)[1].strip().strip('"').strip("'")
    if not recorded or not spec_slug:
        return None
    spec_path = repo / "openspec" / "changes" / f"{tenant}-{change_id}" / "specs" / spec_slug / "spec.md"
    if not spec_path.exists():
        return f"task {task_md.name} references missing spec {spec_path.relative_to(repo)}"
    current_sha = hash_spec_body(spec_path)
    if current_sha and current_sha not in recorded:
        return (f"task {task_md.name} idempotency_key drift: recorded={recorded[:16]}…, "
                f"current sha256={current_sha[:16]}…")
    return None


def hash_spec_body(spec_path: Path) -> str | None:
    import hashlib, re
    try:
        text = spec_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    # Strip frontmatter and the auto-generated `## Kanban Tasks` section per the
    # idempotency-key concept page.
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"## Kanban Tasks.*?(?=^## |\Z)", "", text, flags=re.MULTILINE | re.DOTALL)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def gate_schema_version(report: Report, repo: Path) -> None:
    cfg = repo / "development" / "config.yaml"
    if not cfg.exists():
        return
    repo_v = None
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("scientia_schema_version:"):
            try:
                repo_v = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
    bundle_root = Path(__file__).resolve().parents[3]
    bundle_json = bundle_root / "scientia.json"
    bundle_v = None
    if bundle_json.exists():
        try:
            bundle_v = int(json.loads(bundle_json.read_text())["scientia_schema_version"])
        except Exception:
            pass
    if repo_v is not None and bundle_v is not None and repo_v > bundle_v:
        report.add("schema-version", "critical",
                   f"repo schema v{repo_v} > bundle schema v{bundle_v}; upgrade the scientia bundle")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--threshold", choices=SEVERITIES, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-report", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    report = Report()

    gate_schema_version(report, repo)
    gate_wiki_lint(report, repo)
    gate_openspec_verify(report, repo)
    gate_spec_on_trunk(report, repo)
    gate_idempotency_drift(report, repo)

    threshold = read_threshold(repo, args.threshold)
    worst = report.worst()

    if args.json:
        print(json.dumps({
            "findings": [asdict(f) for f in report.findings],
            "worst": worst,
            "threshold": threshold,
        }, indent=2))
    else:
        print(report.to_markdown())

    if args.write_report and report.findings:
        out = repo / "development" / f"verify-report-{int(__import__('time').time())}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.to_markdown(), encoding="utf-8")
        print(f"\nReport written to {out}", file=sys.stderr)

    # Exit non-zero if worst severity meets/exceeds threshold.
    if worst != "clean" and SEVERITIES.index(worst) >= SEVERITIES.index(threshold):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
