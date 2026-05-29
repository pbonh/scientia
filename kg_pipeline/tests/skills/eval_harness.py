"""Rubric-judged fixture evals for the LLM-shaped skills (spec: pipeline-tooling).

Each ``tests/skills/<skill>/`` directory carries a ``rubric.md`` (required and
forbidden mentions plus a pass criterion) and small fixtures. Actually *running*
a skill needs an Agent-Skills runtime and an LLM, so these evals are operator-run
— they are intentionally NOT part of the deterministic pipeline (the brief: "the
operator runs them when changing a SKILL.md body").

This harness is dependency-free and runs in three layers, each as available:

1. **Structure (always).** Every ``rubric.md`` must be well-formed: it must
   declare required and forbidden mention lists and a pass criterion.
2. **Deterministic mention check (when an output exists).** If the operator has
   produced the skill's output at ``<skill>/output.md``, the harness checks that
   every required mention is present and every forbidden mention is absent.
3. **LLM judge (optional).** If ``$KG_PIPELINE_EVAL_JUDGE`` names a command and
   an output exists, the harness pipes the rubric + output to it for a verdict.
   With no judge configured this layer is reported as skipped — no external
   service is ever required (ASR-1).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent


@dataclass
class Rubric:
    skill: str
    required: list[str]
    forbidden: list[str]
    pass_criterion: str


@dataclass
class EvalResult:
    skill: str
    structure_ok: bool
    errors: list[str] = field(default_factory=list)
    mention_check: str = "skipped (no output.md)"
    judge: str = "skipped (no judge configured)"

    @property
    def ok(self) -> bool:
        return self.structure_ok and not self.errors


def _bullets_under(text: str, heading: str) -> list[str]:
    """Return the bullet items under a `## <heading>` section."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL
    )
    m = pattern.search(text)
    if not m:
        return []
    return [
        line.strip()[2:].strip()
        for line in m.group(1).splitlines()
        if line.strip().startswith("- ")
    ]


def parse_rubric(path: Path) -> Rubric:
    text = Path(path).read_text(encoding="utf-8")
    skill_m = re.search(r"^skill:\s*(.+)$", text, re.MULTILINE)
    crit_m = re.search(r"^##\s+Pass criteria\s*$\n(.+)$", text, re.MULTILINE)
    return Rubric(
        skill=(skill_m.group(1).strip() if skill_m else path.parent.name),
        required=_bullets_under(text, "Required mentions (output MUST contain)"),
        forbidden=_bullets_under(text, "Forbidden mentions (output MUST NOT contain)"),
        pass_criterion=(crit_m.group(1).strip() if crit_m else ""),
    )


def _validate_structure(rubric: Rubric) -> list[str]:
    errors = []
    if not rubric.required:
        errors.append("rubric declares no required mentions")
    if not rubric.pass_criterion:
        errors.append("rubric declares no pass criterion")
    return errors


def _mention_check(rubric: Rubric, output: str) -> tuple[str, list[str]]:
    errors = []
    for need in rubric.required:
        if need.lower() not in output.lower():
            errors.append(f"missing required mention: {need!r}")
    for ban in rubric.forbidden:
        if ban.lower() in output.lower():
            errors.append(f"contains forbidden mention: {ban!r}")
    status = "passed" if not errors else "failed"
    return status, errors


def _llm_judge(rubric_path: Path, output_path: Path) -> str:
    cmd = os.environ.get("KG_PIPELINE_EVAL_JUDGE")
    if not cmd:
        return "skipped (no judge configured)"
    try:
        payload = (
            f"RUBRIC:\n{rubric_path.read_text()}\n\nOUTPUT:\n{output_path.read_text()}\n"
        )
        proc = subprocess.run(
            cmd, shell=True, input=payload, capture_output=True, text=True, timeout=120
        )
        verdict = (proc.stdout or proc.stderr).strip().splitlines()
        return verdict[-1] if verdict else "judge returned no output"
    except Exception as exc:  # pragma: no cover - defensive
        return f"judge error: {exc}"


def run_eval(eval_dir: Path) -> EvalResult:
    rubric_path = eval_dir / "rubric.md"
    rubric = parse_rubric(rubric_path)
    result = EvalResult(skill=rubric.skill, structure_ok=True)
    result.errors.extend(_validate_structure(rubric))
    if result.errors:
        result.structure_ok = False
        return result

    output_path = eval_dir / "output.md"
    if output_path.is_file():
        status, errors = _mention_check(rubric, output_path.read_text(encoding="utf-8"))
        result.mention_check = status
        result.errors.extend(errors)
        result.judge = _llm_judge(rubric_path, output_path)
    return result


def discover_evals(skills_dir: Path = SKILLS_DIR) -> list[Path]:
    return sorted(p.parent for p in Path(skills_dir).glob("*/rubric.md"))


def run_all_evals(skills_dir: Path = SKILLS_DIR) -> list[EvalResult]:
    return [run_eval(d) for d in discover_evals(skills_dir)]


if __name__ == "__main__":
    import sys

    failed = 0
    for r in run_all_evals():
        mark = "OK  " if r.ok else "FAIL"
        print(f"{mark} {r.skill:20} structure={'ok' if r.structure_ok else 'bad'} "
              f"mentions={r.mention_check} judge={r.judge}")
        for e in r.errors:
            print(f"       - {e}")
        failed += 0 if r.ok else 1
    print(f"\n{len(run_all_evals())} evals, {failed} failed")
    sys.exit(1 if failed else 0)
