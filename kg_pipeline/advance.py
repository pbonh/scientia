"""kg_pipeline.advance — the package-owned stage-advance gate (ADR-0006).

``pipeline-controller`` is an LLM ``SKILL.md`` and could, in principle, skip a
validator call and "decide" to advance. This module removes that possibility:
the only way to record that a stage may be advanced past is :func:`advance`,
which **itself runs the stage's validator** and writes the
``proposals/<change-id>/.advance/<stage>.ok`` marker *only* when the validator
returns an empty error list. A failing stage leaves no marker (and any stale
marker is removed), so the controller cannot fabricate an advance (ASR-5).

State transfer is on-disk only (ADR-0006): the marker is a file, not an
in-memory flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kg_pipeline import paths, validators

__all__ = ["AdvanceResult", "STAGE_VALIDATORS", "advance", "is_advanced", "stages"]


@dataclass
class AdvanceResult:
    """Outcome of an :func:`advance` attempt."""

    stage: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    marker: Path | None = None


def _validate_proposal(change_id: str) -> list[str]:
    return validators.validate_proposal(paths.proposal_path(change_id))


def _validate_grill(change_id: str) -> list[str]:
    return validators.validate_grill(paths.grill_path(change_id))


def _validate_specs(change_id: str) -> list[str]:
    return validators.validate_specs(paths.specs_dir(change_id))


def _validate_design(change_id: str) -> list[str]:
    return validators.validate_design(paths.design_path(change_id))


def _validate_adrs(change_id: str) -> list[str]:
    return validators.validate_adrs(paths.adrs_dir(change_id))


def _validate_tasks(change_id: str) -> list[str]:
    return validators.validate_tasks(paths.tasks_path(change_id))


# Stage name -> the validator that gates advancement past it. Order is the
# pipeline's authoring order (ingest/audit produce wiki pages, not change
# artifacts, so they are gated by wiki validation, not a change-stage marker).
STAGE_VALIDATORS = {
    "proposal": _validate_proposal,
    "grill": _validate_grill,
    "specs": _validate_specs,
    "design": _validate_design,
    "adrs": _validate_adrs,
    "tasks": _validate_tasks,
}


def stages() -> list[str]:
    """The ordered list of gated change stages."""
    return list(STAGE_VALIDATORS)


def advance(change_id: str, stage: str) -> AdvanceResult:
    """Validate ``stage``'s produced artifact and, only if it is clean, stamp the
    advance marker. Returns an :class:`AdvanceResult` carrying any errors.

    This is the single chokepoint that enforces the validation gate. A stage
    with errors never gets a marker; a previously-written marker for a
    now-failing stage is removed.
    """
    if stage not in STAGE_VALIDATORS:
        raise ValueError(
            f"unknown stage {stage!r}; expected one of {list(STAGE_VALIDATORS)}"
        )
    errors = STAGE_VALIDATORS[stage](change_id)
    marker = paths.advance_marker_path(change_id, stage)
    if errors:
        if marker.exists():
            marker.unlink()
        return AdvanceResult(stage=stage, ok=False, errors=errors, marker=None)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"stage {stage} validated\n", encoding="utf-8")
    return AdvanceResult(stage=stage, ok=True, errors=[], marker=marker)


def is_advanced(change_id: str, stage: str) -> bool:
    """Whether ``stage`` has a current advance marker on disk."""
    return paths.advance_marker_path(change_id, stage).exists()
