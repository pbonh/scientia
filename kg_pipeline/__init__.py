"""kg_pipeline — the deterministic core of the KG-seeded intent-driven pipeline.

This package carries every reproducible, idempotent, golden-tested operation in
the pipeline. LLM judgment lives in the ``.agents/skills/`` ``SKILL.md`` files;
this package never makes a judgment call (ADR-0007). The dividing line is the
spine of the design: any operation whose output must be byte-stable and testable
lives here; any operation requiring an LLM's reading of a source or proposal
lives in a skill.

Modules
-------
- ``kg_pipeline.wiki``        — typed-page parsing, link/edge recovery, traversal.
- ``kg_pipeline.confidence``  — per-claim quantitative confidence + rollups.
- ``kg_pipeline.templates``   — ``str.format_map`` rendering (no external engine).
- ``kg_pipeline.validators``  — artifact validators returning error lists.
- ``kg_pipeline.advance``     — the package-owned stage-advance marker (the gate).
- ``kg_pipeline.paths``       — the single source of file-layout truth.
"""

__version__ = "1.0.0"

__all__ = [
    "advance",
    "confidence",
    "paths",
    "templates",
    "validators",
    "wiki",
]
