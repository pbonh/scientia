"""scientia.hermes — the Kanban execution layer (a subpackage, mirroring
:mod:`scientia.wiki`).

Turns a finished change (``tasks.md`` + ``design.md``) into a live,
dependency-ordered Hermes Kanban board of ``impl -> review -> integrate``
pipelines, then reports progress back. Its defining property is **conflict
robustness without a human in the loop**: parallel work is decomposed along C4
component boundaries so collisions are structurally *prevented*
(:mod:`.conflict`), and the residue is *resolved* automatically by the
``conflict-resolver`` profile.

scientia's determinism-in-the-package / judgment-in-the-skills split holds: the
seam is the pure, serializable :class:`~scientia.hermes.plan.EmitPlan`. Only
:mod:`.preflight` (reads the environment) and :mod:`.apply` (the single board
writer) are impure; everything that produces the plan is deterministic and
golden-file testable with no Hermes and no network.
"""

from __future__ import annotations

from scientia.hermes.board import resolve_board, slugify
from scientia.hermes.conflict import (
    ContractError,
    compute_waves,
    ratify_contracts,
    synthetic_edges,
)
from scientia.hermes.idempotency import (
    card_key,
    design_sha,
    epic_key,
    parse_card_key,
    source_sha,
)
from scientia.hermes.parse import (
    C4Diagram,
    ComponentMap,
    Contract,
    Task,
    parse_design,
    parse_tasks,
)
from scientia.hermes.plan import (
    CardSpec,
    CycleError,
    EmitPlan,
    PlanOptions,
    ProfileModel,
    Routing,
    TaskRouting,
    build_plan,
)

__all__ = [
    # board
    "resolve_board",
    "slugify",
    # parse
    "Task",
    "ComponentMap",
    "Contract",
    "C4Diagram",
    "parse_tasks",
    "parse_design",
    # idempotency
    "source_sha",
    "design_sha",
    "card_key",
    "epic_key",
    "parse_card_key",
    # conflict
    "ContractError",
    "compute_waves",
    "synthetic_edges",
    "ratify_contracts",
    # plan
    "ProfileModel",
    "Routing",
    "TaskRouting",
    "PlanOptions",
    "CardSpec",
    "EmitPlan",
    "CycleError",
    "build_plan",
]
