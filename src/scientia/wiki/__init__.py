"""scientia.wiki — the typed-node knowledge graph (ADR-0001, ADR-0002).

The wiki *is* the knowledge graph. There is no derived graph database: queries
parse the markdown pages on demand. This module defines the two shared types
ratified by ADR-0001 — :class:`Page` and :class:`Link` — and the deterministic
operations over them: loading and listing typed pages, recovering edges from the
wiki-link alias slot, bounded-hop neighborhood traversal, and idempotent writes.

Node types (frontmatter ``type``): ``entity`` | ``claim`` | ``source`` |
``question``. Every page MUST set ``type``; an untyped page is invalid (this is
the single biggest guard against frontmatter drift). Only ``claim`` pages carry
confidence (see :mod:`scientia.confidence`).

Edges are wiki-links whose kind is encoded in the alias slot (ADR-0002)::

    [[claim-x-causes-y | supports]]      # kind = supports
    [[claim-rag-stateless | contradicts]]# kind = contradicts
    [[entity-llm-wiki]]                  # kind = mentions (default)
    [[entity-llm-wiki | seealso]]        # unknown alias -> mentions

Canonical edge kinds: ``mentions`` (default), ``supports``, ``contradicts``,
``refines``. Any unrecognized alias is treated as ``mentions``.

All write operations are non-destructive (ADR-0009) and idempotent (ADR-0002):
:func:`write_page` leaves an unchanged page byte-identical on disk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

__all__ = [
    "Page",
    "Link",
    "CANONICAL_EDGE_KINDS",
    "DEFAULT_EDGE_KIND",
    "NODE_TYPES",
    "load_page",
    "list_pages",
    "validate_page",
    "parse_links",
    "neighbors",
    "write_page",
    "page_id",
    "to_jsonable",
]

CANONICAL_EDGE_KINDS = ("mentions", "supports", "contradicts", "refines")
DEFAULT_EDGE_KIND = "mentions"
NODE_TYPES = ("entity", "claim", "source", "question")

_LINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
_FRONTMATTER_FENCE = "---"


# --------------------------------------------------------------------------- #
# Shared types (ratified by ADR-0001)                                         #
# --------------------------------------------------------------------------- #
@dataclass
class Page:
    """A single wiki page: parsed YAML ``frontmatter`` plus the markdown ``body``.

    ``path`` records where the page was loaded from (or where it should be
    written); it is not part of the page's logical identity. ``_original_text``
    holds the exact bytes read from disk so :func:`write_page` can guarantee a
    byte-identical no-op for an unchanged page.
    """

    frontmatter: dict
    body: str
    path: Optional[Path] = None
    _original_text: Optional[str] = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class Link:
    """A directed wiki-link edge: ``(target_id, kind)``."""

    target_id: str
    kind: str


# --------------------------------------------------------------------------- #
# Serialization (canonical, stable, idempotent)                               #
# --------------------------------------------------------------------------- #
def _dump_frontmatter(frontmatter: dict) -> str:
    """Serialize frontmatter to canonical YAML (insertion order preserved)."""
    return yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).rstrip("\n")


def _serialize(page: Page) -> str:
    """Render a page to its canonical on-disk text."""
    fm = _dump_frontmatter(page.frontmatter)
    return f"{_FRONTMATTER_FENCE}\n{fm}\n{_FRONTMATTER_FENCE}\n{page.body}"


def _split_frontmatter(content: str) -> tuple[Optional[str], str]:
    """Split a file into (frontmatter_text, body). Returns (None, content) when
    the file carries no frontmatter fence."""
    if not content.startswith(_FRONTMATTER_FENCE):
        return None, content
    lines = content.split("\n")
    if lines[0] != _FRONTMATTER_FENCE:
        return None, content
    for i in range(1, len(lines)):
        if lines[i] == _FRONTMATTER_FENCE:
            fm_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:])
            return fm_text, body
    return None, content


# --------------------------------------------------------------------------- #
# Loading & listing                                                           #
# --------------------------------------------------------------------------- #
def load_page(path: Path) -> Page:
    """Load a wiki page from ``path`` into a :class:`Page`.

    A page with no frontmatter loads with an empty ``frontmatter`` dict and the
    whole file as ``body`` — validation (:func:`validate_page`), not loading, is
    what reports the missing ``type``.
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    fm_text, body = _split_frontmatter(content)
    if fm_text is None:
        frontmatter: dict = {}
    else:
        parsed = yaml.safe_load(fm_text) if fm_text.strip() else {}
        frontmatter = parsed if isinstance(parsed, dict) else {}
    return Page(frontmatter=frontmatter, body=body, path=path, _original_text=content)


def list_pages(wiki_dir: Path, type: Optional[str] = None) -> list[Page]:
    """Return every ``*.md`` page in ``wiki_dir`` (recursively), optionally
    filtered by frontmatter ``type``. Sorted by path for determinism."""
    wiki_dir = Path(wiki_dir)
    if not wiki_dir.is_dir():
        return []
    pages = [load_page(p) for p in sorted(wiki_dir.rglob("*.md"))]
    if type is not None:
        pages = [p for p in pages if p.frontmatter.get("type") == type]
    return pages


def page_id(page: Page) -> str:
    """The page's identity: frontmatter ``id`` if set, else the filename stem."""
    pid = page.frontmatter.get("id")
    if pid:
        return str(pid)
    if page.path is not None:
        return Path(page.path).stem
    return ""


# --------------------------------------------------------------------------- #
# Node-type validation (task 5)                                               #
# --------------------------------------------------------------------------- #
def validate_page(page: Page) -> list[str]:
    """Return a list of human-readable validation errors (empty == valid).

    A page lacking the mandatory ``type`` field is invalid; the error names the
    missing field explicitly.
    """
    errors: list[str] = []
    where = f" ({page.path})" if page.path is not None else ""
    node_type = page.frontmatter.get("type")
    if not node_type:
        errors.append(f"page is missing the required 'type' frontmatter field{where}")
    elif node_type not in NODE_TYPES:
        errors.append(
            f"page 'type' is '{node_type}'{where}; expected one of {list(NODE_TYPES)}"
        )
    return errors


# --------------------------------------------------------------------------- #
# Edge recovery (ADR-0002)                                                     #
# --------------------------------------------------------------------------- #
def parse_links(body: str) -> list[Link]:
    """Recover every wiki-link edge from a page ``body``.

    The edge kind is read from the alias slot (``[[target | kind]]``). A link
    with no alias, or an alias that is not a canonical edge kind, is a
    ``mentions`` edge.
    """
    links: list[Link] = []
    for raw in _LINK_RE.findall(body):
        inner = raw.strip()
        if "|" in inner:
            target_part, alias_part = inner.split("|", 1)
            target = target_part.strip()
            alias = alias_part.strip()
            kind = alias if alias in CANONICAL_EDGE_KINDS else DEFAULT_EDGE_KIND
        else:
            target = inner
            kind = DEFAULT_EDGE_KIND
        if target:
            links.append(Link(target_id=target, kind=kind))
    return links


# --------------------------------------------------------------------------- #
# Neighborhood traversal (task 7; pure-Python is canonical, networkx parity)   #
# --------------------------------------------------------------------------- #
def _resolve_target(target_id: str, by_id: dict[str, str]) -> Optional[str]:
    """Resolve a link target to a known page id (exact, then basename)."""
    if target_id in by_id:
        return by_id[target_id]
    base = target_id.rsplit("/", 1)[-1]
    if base in by_id:
        return by_id[base]
    return None


def _build_adjacency(pages: list[Page]) -> dict[str, set[str]]:
    """Build the UNDIRECTED adjacency of the wiki link graph, keyed by page id.

    Edges are symmetric so that an entity's neighborhood includes the claims
    that mention it (scientia-seed-proposal / grill traverse an entity neighborhood).
    """
    ids = [page_id(p) for p in pages]
    by_id: dict[str, str] = {}
    for pid in ids:
        by_id.setdefault(pid, pid)
        by_id.setdefault(pid.rsplit("/", 1)[-1], pid)
    adj: dict[str, set[str]] = {pid: set() for pid in ids}
    for page, pid in zip(pages, ids):
        for link in parse_links(page.body):
            tgt = _resolve_target(link.target_id, by_id)
            if tgt is not None and tgt != pid:
                adj[pid].add(tgt)
                adj.setdefault(tgt, set()).add(pid)
    return adj


def _bfs_python(adj: dict[str, set[str]], start: str, hops: int) -> set[str]:
    """Pure-Python bounded BFS. Returns ids reachable within ``hops`` edges,
    excluding ``start``. This is the canonical implementation."""
    seen = {start}
    frontier = {start}
    for _ in range(max(0, hops)):
        nxt: set[str] = set()
        for node in frontier:
            nxt |= adj.get(node, set())
        nxt -= seen
        if not nxt:
            break
        seen |= nxt
        frontier = nxt
    return seen - {start}


def _bfs_networkx(adj: dict[str, set[str]], start: str, hops: int) -> set[str]:
    """networkx-backed bounded traversal. MUST return a set identical to
    :func:`_bfs_python` for the same inputs (ADR-0001)."""
    import networkx as nx  # imported lazily; optional dependency

    graph = nx.Graph()
    graph.add_nodes_from(adj)
    for node, neigh in adj.items():
        for other in neigh:
            graph.add_edge(node, other)
    if start not in graph:
        return set()
    lengths = nx.single_source_shortest_path_length(graph, start, cutoff=max(0, hops))
    return {node for node, dist in lengths.items() if 1 <= dist <= hops}


def _networkx_available() -> bool:
    try:
        import networkx  # noqa: F401

        return True
    except Exception:
        return False


def neighbors(page: Page, wiki_dir: Path, hops: int = 1) -> list[Page]:
    """Return the pages within ``hops`` edges of ``page`` (excluding itself).

    The pure-Python BFS is canonical; when networkx is installed it is used as an
    alternative path that is guaranteed to return the identical set. The result
    is sorted by page id for determinism.
    """
    pages = list_pages(wiki_dir)
    adj = _build_adjacency(pages)
    start = page_id(page)
    if _networkx_available():
        reachable = _bfs_networkx(adj, start, hops)
    else:
        reachable = _bfs_python(adj, start, hops)
    by_id = {page_id(p): p for p in pages}
    result = [by_id[pid] for pid in sorted(reachable) if pid in by_id]
    return result


# --------------------------------------------------------------------------- #
# Idempotent, non-destructive write (ADR-0009)                                 #
# --------------------------------------------------------------------------- #
def write_page(page: Page) -> None:
    """Write ``page`` to ``page.path`` using the canonical serialization.

    Idempotent: if the rendered text equals what is already on disk the file is
    left untouched (byte-identical, same mtime). ``page.path`` must be set.
    """
    if page.path is None:
        raise ValueError("write_page requires page.path to be set")
    path = Path(page.path)
    new_text = _serialize(page)
    if path.exists() and path.read_text(encoding="utf-8") == new_text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    page._original_text = new_text


# --------------------------------------------------------------------------- #
# Test/golden-file helper                                                      #
# --------------------------------------------------------------------------- #
def to_jsonable(page: Page) -> dict:
    """A stable, JSON-friendly projection of a page for golden-file tests."""
    return {
        "id": page_id(page),
        "type": page.frontmatter.get("type"),
        "frontmatter": json.loads(json.dumps(page.frontmatter, default=str, sort_keys=True)),
        "links": [
            {"target_id": link.target_id, "kind": link.kind}
            for link in parse_links(page.body)
        ],
    }
