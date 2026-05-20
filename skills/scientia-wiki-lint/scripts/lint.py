#!/usr/bin/env python3
"""lint.py — validate a scientia wiki.

Read-only. Reports findings classified by severity (CRITICAL / WARNING /
SUGGESTION). Used by `scientia-wiki-lint` and by the orchestrator's
verify_all.py.

Usage:
    lint.py [--repo <path>] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

SEVERITIES = ["suggestion", "warning", "critical"]

REQUIRED_FRONTMATTER_KEYS = {"title", "type", "updated"}

TYPE_BY_DIR = {
    "concepts":     "concept",
    "entities":     "entity",
    "summaries":    "summary",
    "syntheses":    "synthesis",
    "contexts":     "context",
    "context-maps": "context-map",
    "decisions":    "decision",
    "specs":        "spec",
}

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
FENCED_CODE_RE = re.compile(r"^(```|~~~).*?^\1", re.DOTALL | re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def strip_code_spans(text: str) -> str:
    """Remove fenced and inline code so wikilinks inside snippets are ignored."""
    text = FENCED_CODE_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def is_real_wikilink_target(target: str) -> bool:
    """Real wiki targets are slug-like — reject anything with whitespace or angle brackets."""
    return bool(target) and not any(c in target for c in " \t<>")


@dataclass
class Finding:
    check: str
    severity: str
    path: str
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, check: str, severity: str, path: str, message: str) -> None:
        self.findings.append(Finding(check, severity, path, message))

    def worst(self) -> str:
        idx = -1
        for f in self.findings:
            idx = max(idx, SEVERITIES.index(f.severity))
        return SEVERITIES[idx] if idx >= 0 else "clean"

    def to_markdown(self) -> str:
        if not self.findings:
            return "# scientia-wiki-lint\n\nAll checks clean.\n"
        lines = ["# scientia-wiki-lint report", ""]
        for sev in reversed(SEVERITIES):
            bucket = [f for f in self.findings if f.severity == sev]
            if not bucket:
                continue
            lines.append(f"## {sev.upper()} ({len(bucket)})")
            for f in bucket:
                lines.append(f"- **{f.check}** — `{f.path}` — {f.message}")
            lines.append("")
        return "\n".join(lines)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def find_wiki_md(wiki_dir: Path) -> list[Path]:
    return [p for p in wiki_dir.rglob("*.md") if p.is_file()]


def check_page(path: Path, wiki_dir: Path, all_pages: set[Path], report: Report) -> None:
    rel = str(path.relative_to(wiki_dir.parent))
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        report.add("read-error", "critical", rel, f"could not read: {exc}")
        return

    if path.name in ("index.md", "log.md"):
        # Special files; checked elsewhere.
        return

    fm = parse_frontmatter(text)
    if fm is None:
        report.add("frontmatter-missing", "critical", rel,
                   "no YAML frontmatter at top of file")
        return

    missing = REQUIRED_FRONTMATTER_KEYS - set(fm)
    if missing:
        report.add("frontmatter-required-fields", "critical", rel,
                   f"missing keys: {', '.join(sorted(missing))}")

    # type vs. directory check
    parts = path.relative_to(wiki_dir).parts
    if len(parts) >= 2 and parts[0] in TYPE_BY_DIR:
        expected = TYPE_BY_DIR[parts[0]]
        if fm.get("type") and fm["type"] != expected:
            report.add("frontmatter-type-mismatch", "warning", rel,
                       f"type={fm['type']!r} but directory implies {expected!r}")

    if "confidence" not in fm:
        report.add("confidence-missing", "suggestion", rel, "no confidence field")
    if "sources" not in fm:
        report.add("sources-missing", "suggestion", rel, "no sources field")

    # Wikilink resolution. Strip code spans first so vim keybindings,
    # shell snippets, etc. that happen to contain `[[...]]` aren't
    # treated as wikilinks.
    prose = strip_code_spans(text)
    for m in WIKILINK_RE.finditer(prose):
        target = m.group(1).strip()
        # Strip section anchors.
        target = target.split("#", 1)[0]
        if not is_real_wikilink_target(target):
            continue
        # Resolve as relative to wiki_dir.
        target_path = wiki_dir / (target + ".md")
        if target_path.resolve() not in all_pages and (wiki_dir / target).resolve() not in all_pages:
            report.add("wikilink-unresolved", "critical", rel,
                       f"[[{target}]] does not resolve to a wiki page")


def check_index(wiki_dir: Path, report: Report) -> None:
    index = wiki_dir / "index.md"
    if not index.exists():
        report.add("index-missing-row", "critical", "wiki/index.md",
                   "wiki/index.md is missing")
        return
    text = index.read_text(encoding="utf-8", errors="ignore")
    listed = set(WIKILINK_RE.findall(text))
    listed = {l.split("|", 1)[0].split("#", 1)[0].strip() for l in listed}

    expected = set()
    for path in find_wiki_md(wiki_dir):
        if path.name in ("index.md", "log.md"):
            continue
        rel = path.relative_to(wiki_dir).with_suffix("")
        expected.add(str(rel))

    for page in expected - listed:
        report.add("index-missing-row", "warning", f"wiki/{page}.md",
                   "page exists on disk but is not listed in wiki/index.md")
    for page in listed - expected:
        if "/" not in page:
            continue
        report.add("index-stale-row", "warning", f"wiki/{page}.md",
                   "wiki/index.md references a page that does not exist on disk")


def check_log_monotonic(wiki_dir: Path, report: Report) -> None:
    log = wiki_dir / "log.md"
    if not log.exists():
        return
    timestamps: list[str] = []
    for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"-\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", line)
        if m:
            timestamps.append(m.group(1))
    for i in range(1, len(timestamps)):
        if timestamps[i] < timestamps[i - 1]:
            report.add("log-not-monotonic", "warning", "wiki/log.md",
                       f"non-monotonic timestamps near entry #{i+1}")
            break


def check_orphans(wiki_dir: Path, report: Report) -> None:
    contexts_dir = wiki_dir / "contexts"
    if not contexts_dir.is_dir():
        return
    referenced: set[str] = set()
    for ctx in contexts_dir.glob("*.md"):
        text = ctx.read_text(encoding="utf-8", errors="ignore")
        prose = strip_code_spans(text)
        for m in WIKILINK_RE.finditer(prose):
            target = m.group(1).split("#", 1)[0].strip()
            if is_real_wikilink_target(target):
                referenced.add(target)

    for kind in ("concepts", "entities"):
        d = wiki_dir / kind
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            key = f"{kind}/{p.stem}"
            if key not in referenced:
                report.add("orphan-page", "suggestion", str(p.relative_to(wiki_dir.parent)),
                           "not referenced by any wiki/contexts/ page")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    wiki_dir = repo / "wiki"
    report = Report()

    if not wiki_dir.is_dir():
        report.add("wiki-missing", "critical", "wiki/", "wiki/ directory does not exist")
    else:
        all_pages = {p.resolve() for p in find_wiki_md(wiki_dir)}
        for p in sorted(find_wiki_md(wiki_dir)):
            check_page(p, wiki_dir, all_pages, report)
        check_index(wiki_dir, report)
        check_log_monotonic(wiki_dir, report)
        check_orphans(wiki_dir, report)

    if args.json:
        print(json.dumps({
            "findings": [asdict(f) for f in report.findings],
            "worst": report.worst(),
        }, indent=2))
    else:
        print(report.to_markdown())

    worst = report.worst()
    if worst == "critical":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
