"""Deterministic coverage of the rubric evals (the LLM judging itself is
operator-run and dependency-free; here we check every rubric is well-formed)."""

from pathlib import Path

from tests.skills import eval_harness

EXPECTED = {
    "ingest-source",
    "seed-proposal",
    "grill-proposal",
    "record-adr",
    "pipeline-controller",
}


def test_all_five_llm_shaped_skills_have_an_eval():
    dirs = {d.name for d in eval_harness.discover_evals()}
    assert dirs == EXPECTED


def test_every_rubric_is_well_formed():
    for result in eval_harness.run_all_evals():
        assert result.structure_ok, f"{result.skill}: {result.errors}"
        assert result.ok, f"{result.skill}: {result.errors}"
