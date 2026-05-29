"""Golden-file tests for kg_pipeline.confidence (spec: kg-confidence).

Determinism + idempotency, source-count multiplier (incl. the +10% cap), the
contradiction floor, the min rollup, and the raise-on-stale guarantee. These
tests assert the exact golden values from the spec and run with networkx absent.
"""

import shutil
from pathlib import Path

import pytest

from kg_pipeline import confidence, wiki

FIX = Path(__file__).resolve().parent.parent / "fixtures"
WIKI_CONF = FIX / "wiki-confidence"

CONFIG = {
    "confidence": {
        "source_count_curve": [1.00, 0.04, 1.10],
        "contradiction_floor": 0.40,
        "rollup": "min",
    }
}


@pytest.fixture
def conf_wiki(tmp_path):
    """A writable copy of the confidence fixture wiki."""
    dst = tmp_path / "wiki"
    shutil.copytree(WIKI_CONF, dst)
    return dst


def _claim(wiki_dir, cid):
    return wiki.load_page(wiki_dir / f"{cid}.md")


def test_accumulation_raises_effective_via_multiplier():
    eff, _ = confidence.compute(0.80, 2, False, CONFIG)
    assert eff == 0.832


def test_source_count_multiplier_caps_at_plus_ten_percent():
    eff, _ = confidence.compute(0.80, 10, False, CONFIG)
    assert eff == 0.88


def test_contradiction_clamps_effective_to_floor():
    eff, _ = confidence.compute(0.90, 1, True, CONFIG)
    assert eff == 0.40


def test_spec_frontmatter_example_value():
    # Brief's frontmatter example: base 0.78, n=3 -> 0.842.
    eff, _ = confidence.compute(0.78, 3, False, CONFIG)
    assert eff == 0.842


def test_recompute_writes_derived_and_preserves_base(conf_wiki):
    claim = _claim(conf_wiki, "claim-accumulation")
    confidence.recompute(claim, conf_wiki, CONFIG)
    conf = claim.frontmatter["confidence"]
    assert conf["base"] == 0.80          # preserved
    assert conf["source_count"] == 2
    assert conf["contradicted"] is False
    assert conf["effective"] == 0.832
    assert "inputs_hash" in conf


def test_recompute_is_idempotent_over_unchanged_inputs(conf_wiki):
    claim = _claim(conf_wiki, "claim-accumulation")
    confidence.recompute(claim, conf_wiki, CONFIG)
    first = dict(claim.frontmatter["confidence"])
    confidence.recompute(claim, conf_wiki, CONFIG)
    assert claim.frontmatter["confidence"] == first


def test_recompute_all_marks_contradicted_and_returns_count(conf_wiki):
    confidence.recompute_all(conf_wiki, CONFIG)
    contradicted = _claim(conf_wiki, "claim-contradicted")
    assert contradicted.frontmatter["confidence"]["contradicted"] is True
    assert contradicted.frontmatter["confidence"]["effective"] == 0.40
    # A second pass changes nothing (corpus-level idempotency).
    assert confidence.recompute_all(conf_wiki, CONFIG) == 0


def test_page_confidence_rolls_up_as_the_weakest_claim(conf_wiki):
    confidence.recompute_all(conf_wiki, CONFIG)
    agg = _claim(conf_wiki, "entity-aggregate")
    # min(0.832, 0.88) == 0.832
    assert confidence.rollup_page(agg, conf_wiki, CONFIG) == 0.832


def test_rollup_raises_rather_than_return_a_stale_effective(conf_wiki):
    confidence.recompute_all(conf_wiki, CONFIG)
    # Mutate inputs (add a source) WITHOUT recomputing -> inputs_hash goes stale.
    claim = _claim(conf_wiki, "claim-accumulation")
    claim.frontmatter["sources"].append("source-new")
    wiki.write_page(claim)
    agg = _claim(conf_wiki, "entity-aggregate")
    with pytest.raises(confidence.StaleConfidenceError) as exc:
        confidence.rollup_page(agg, conf_wiki, CONFIG)
    assert "claim-accumulation" in str(exc.value)


def test_suite_runs_with_networkx_absent():
    # The deterministic core must not require the optional dependency.
    if wiki._networkx_available():
        pytest.skip("networkx is installed in this environment")
    eff, _ = confidence.compute(0.80, 2, False, CONFIG)
    assert eff == 0.832
