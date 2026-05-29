"""Golden-file tests for kg_pipeline.wiki (spec: kg-wiki-model, pipeline-tooling).

No mocks: the fixture wiki is the input, and the actual JSON dump is compared
against a committed expected dump.
"""

import json
import shutil
from pathlib import Path

import pytest

from kg_pipeline import wiki
from kg_pipeline.wiki import Link, Page

FIX = Path(__file__).resolve().parent.parent / "fixtures"
WIKI_BASIC = FIX / "wiki-basic"


def test_load_well_formed_page_into_dataclass():
    page = wiki.load_page(WIKI_BASIC / "entity-llm-wiki.md")
    assert isinstance(page, Page)
    assert page.frontmatter["type"] == "entity"
    assert page.frontmatter["id"] == "entity-llm-wiki"
    assert "LLM-maintained wiki pattern" in page.body


def test_reject_page_that_omits_its_node_type():
    page = Page(frontmatter={"id": "x", "title": "no type"}, body="b", path=Path("x.md"))
    errors = wiki.validate_page(page)
    assert errors and any("type" in e for e in errors)


def test_recover_edge_kind_from_alias_slot():
    links = wiki.parse_links("see [[claim-x-causes-y | supports]]")
    assert links == [Link(target_id="claim-x-causes-y", kind="supports")]


def test_unknown_alias_is_a_mentions_edge():
    links = wiki.parse_links("see [[entity-llm-wiki | seealso]]")
    assert links == [Link(target_id="entity-llm-wiki", kind="mentions")]


def test_bare_link_is_a_mentions_edge():
    assert wiki.parse_links("[[entity-foo]]") == [Link("entity-foo", "mentions")]


def test_all_canonical_edge_kinds_round_trip():
    body = "[[a | supports]] [[b | contradicts]] [[c | refines]] [[d | mentions]] [[e]]"
    kinds = [l.kind for l in wiki.parse_links(body)]
    assert kinds == ["supports", "contradicts", "refines", "mentions", "mentions"]


def test_traverse_neighborhood_to_bounded_hop_count(tmp_path):
    # claim1 -> claim2 -> claim3 ; neighbors(hops=1) yields only claim2.
    def mk(pid, body):
        wiki.write_page(Page({"type": "claim", "id": pid}, body, path=tmp_path / f"{pid}.md"))

    mk("claim1", "links [[claim2 | supports]]")
    mk("claim2", "links [[claim3 | supports]]")
    mk("claim3", "leaf")
    c1 = wiki.load_page(tmp_path / "claim1.md")
    hop1 = [wiki.page_id(p) for p in wiki.neighbors(c1, tmp_path, hops=1)]
    hop2 = sorted(wiki.page_id(p) for p in wiki.neighbors(c1, tmp_path, hops=2))
    assert hop1 == ["claim2"]
    assert hop2 == ["claim2", "claim3"]


def test_writing_an_unchanged_page_leaves_it_byte_identical(tmp_path):
    src = WIKI_BASIC / "claim-rag-rediscovers-knowledge.md"
    dst = tmp_path / src.name
    shutil.copy(src, dst)
    before = dst.read_bytes()
    wiki.write_page(wiki.load_page(dst))
    assert dst.read_bytes() == before


def test_write_is_idempotent_across_two_writes(tmp_path):
    p = Page({"type": "claim", "id": "c", "title": "t"}, "body\n", path=tmp_path / "c.md")
    wiki.write_page(p)
    first = (tmp_path / "c.md").read_bytes()
    wiki.write_page(wiki.load_page(tmp_path / "c.md"))
    assert (tmp_path / "c.md").read_bytes() == first


def test_list_pages_filters_by_type():
    claims = wiki.list_pages(WIKI_BASIC, type="claim")
    assert {wiki.page_id(p) for p in claims} == {
        "claim-rag-rediscovers-knowledge",
        "claim-llm-maintains-wiki-stateful",
    }


def test_golden_dump_matches_expected():
    pages = wiki.list_pages(WIKI_BASIC)
    actual = sorted((wiki.to_jsonable(p) for p in pages), key=lambda d: d["id"])
    expected = json.loads((FIX / "wiki-basic.expected.json").read_text())
    assert actual == expected


@pytest.mark.skipif(not wiki._networkx_available(), reason="networkx not installed")
def test_networkx_path_matches_python_path(tmp_path):
    def mk(pid, body):
        wiki.write_page(Page({"type": "claim", "id": pid}, body, path=tmp_path / f"{pid}.md"))

    mk("a", "[[b | supports]] [[c | refines]]")
    mk("b", "[[c | supports]]")
    mk("c", "leaf")
    adj = wiki._build_adjacency(wiki.list_pages(tmp_path))
    for hops in (1, 2, 3):
        assert wiki._bfs_python(adj, "a", hops) == wiki._bfs_networkx(adj, "a", hops)
