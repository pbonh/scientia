#!/usr/bin/env python3
"""Verify / CI entry point (task 29).

Runs, in order, and exits non-zero if any layer fails:

1. ``validate_skill_md`` across all nine ``SKILL.md`` files, asserting each is
   under 500 lines (the progressive-disclosure budget; ASR-6).
2. The rubric-eval structure checks (the LLM judging is operator-run).
3. The golden-file module suite and the rubric pytest coverage.

Usage::

    python tests/run_all.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent
if str(BUNDLE) not in sys.path:
    sys.path.insert(0, str(BUNDLE))

from kg_pipeline import validators  # noqa: E402
from tests.skills import eval_harness  # noqa: E402

SKILLS_DIR = BUNDLE / ".agents" / "skills"
MAX_SKILL_LINES = 500


def check_skills() -> int:
    print("== SKILL.md validation (agentskills.io + <500 lines) ==")
    failures = 0
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not skill_files:
        print("  FAIL no SKILL.md files found")
        return 1
    for sk in skill_files:
        errors = validators.validate_skill_md(sk)
        lines = len(sk.read_text(encoding="utf-8").splitlines())
        if lines >= MAX_SKILL_LINES:
            errors = errors + [f"exceeds {MAX_SKILL_LINES} lines ({lines})"]
        mark = "OK  " if not errors else "FAIL"
        print(f"  {mark} {sk.parent.name:20} lines={lines:3} {errors if errors else ''}")
        failures += 0 if not errors else 1
    print(f"  -> {len(skill_files)} skills, {failures} failed\n")
    return failures


def check_evals() -> int:
    print("== Skill rubric evals (structure; LLM judge operator-run) ==")
    failures = 0
    for r in eval_harness.run_all_evals():
        mark = "OK  " if r.ok else "FAIL"
        print(f"  {mark} {r.skill:20} mentions={r.mention_check} judge={r.judge}")
        for e in r.errors:
            print(f"         - {e}")
        failures += 0 if r.ok else 1
    print(f"  -> {failures} failed\n")
    return failures


def run_pytest() -> int:
    print("== Golden-file module suite + rubric coverage (pytest) ==")
    try:
        import pytest
    except ImportError:
        print("  pytest not installed; skipping (install '.[dev]' to run)\n")
        return 0
    return pytest.main([str(BUNDLE / "tests" / "modules"),
                        str(BUNDLE / "tests" / "skills"), "-q"])


def main() -> int:
    failures = check_skills() + check_evals()
    rc = run_pytest()
    failures += 0 if rc in (0, 5) else 1  # 5 = "no tests collected"
    print("=" * 60)
    if failures:
        print(f"FAILED: {failures} layer(s) reported problems")
        return 1
    print("ALL VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
