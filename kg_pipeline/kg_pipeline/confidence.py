"""kg_pipeline.confidence — per-claim quantitative confidence (ADR-0003, ADR-0004).

A single LLM rating is poorly calibrated and ignores accumulation — the central
insight of the wiki pattern. So a claim's stored ``base`` score (set once at
ingest, never edited) is layered with two cheap, pure-Python signals:

1. **Source-count multiplier.** A claim cited by ``n`` distinct Source pages is
   multiplied by ``multiplier(n) = min(cap, base + step * (n - 1))`` with the
   curve ``[base, step, cap] = [1.00, 0.04, 1.10]`` — capped at +10%.
2. **Contradiction floor.** A claim with any ``contradicts`` edge (incoming or
   outgoing) has its effective score clamped to at most ``contradiction_floor``
   (default 0.40), regardless of the multiplier.

::

    multiplied = base * multiplier(source_count)
    effective  = min(contradiction_floor, multiplied) if contradicted else multiplied

The accumulation/contradiction asymmetry is intentional: many corroborating
sources lift a claim by at most 10%, but a single contradiction caps it hard.

``effective`` is persisted in claim frontmatter yet canonically derived (ADR-0004):
:func:`recompute` is its only writer, is idempotent, and stamps an
``inputs_hash`` over ``(base, source_count, contradicted)``. Rollups verify that
hash against live inputs and **raise** :class:`StaleConfidenceError` rather than
return a stale value.

Rollups (page/edge) take ``min`` over the claims involved by default — a chain of
reasoning is no stronger than its weakest link — configurable to ``mean``/``max``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Optional

from kg_pipeline import wiki
from kg_pipeline.wiki import Link, Page, page_id, parse_links

__all__ = [
    "StaleConfidenceError",
    "EFFECTIVE_PRECISION",
    "multiplier",
    "compute",
    "recompute",
    "recompute_all",
    "rollup_page",
    "rollup_edge",
]

EFFECTIVE_PRECISION = 3


class StaleConfidenceError(Exception):
    """Raised by a rollup when a claim's stored ``effective`` no longer matches
    its live inputs (its ``inputs_hash`` is stale). Names the offending claim."""


# --------------------------------------------------------------------------- #
# Pure scalar core                                                            #
# --------------------------------------------------------------------------- #
def multiplier(source_count: int, config: dict) -> float:
    """The source-count multiplier ``min(cap, base + step * (n - 1))``.

    ``n`` is clamped to at least 1 (every real claim is registered with the
    source that introduced it), so the multiplier never drops below ``base``.
    """
    base_c, step, cap = _source_count_curve(config)
    n = max(1, int(source_count))
    return min(cap, base_c + step * (n - 1))


def _source_count_curve(config: dict) -> tuple[float, float, float]:
    curve = config.get("confidence", {}).get("source_count_curve", [1.00, 0.04, 1.10])
    base_c, step, cap = curve
    return float(base_c), float(step), float(cap)


def _contradiction_floor(config: dict) -> float:
    return float(config.get("confidence", {}).get("contradiction_floor", 0.40))


def _rollup_kind(config: dict) -> str:
    return str(config.get("confidence", {}).get("rollup", "min"))


def _inputs_hash(base: float, source_count: int, contradicted: bool) -> str:
    payload = f"{float(base):.6f}|{int(source_count)}|{int(bool(contradicted))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compute(base: float, source_count: int, contradicted: bool, config: dict) -> tuple[float, str]:
    """Return ``(effective, inputs_hash)`` for the given inputs. Pure and total."""
    multiplied = float(base) * multiplier(source_count, config)
    if contradicted:
        effective = min(_contradiction_floor(config), multiplied)
    else:
        effective = multiplied
    effective = round(effective, EFFECTIVE_PRECISION)
    return effective, _inputs_hash(base, source_count, contradicted)


# --------------------------------------------------------------------------- #
# Deriving the contradiction state from the wiki                              #
# --------------------------------------------------------------------------- #
def _contradicted_ids(pages: Iterable[Page]) -> set[str]:
    """The set of page ids touched by any ``contradicts`` edge (either end).

    Contradiction edges are appended bidirectionally by ingest (ADR-0009), but
    both endpoints are recorded here so the state is correct even if only one
    direction is present.
    """
    pages = list(pages)
    by_id: dict[str, str] = {}
    for p in pages:
        pid = page_id(p)
        by_id.setdefault(pid, pid)
        by_id.setdefault(pid.rsplit("/", 1)[-1], pid)
    touched: set[str] = set()
    for p in pages:
        pid = page_id(p)
        for link in parse_links(p.body):
            if link.kind != "contradicts":
                continue
            touched.add(pid)
            tgt = link.target_id
            touched.add(by_id.get(tgt, by_id.get(tgt.rsplit("/", 1)[-1], tgt)))
    return touched


def _claim_inputs(claim: Page, contradicted_ids: set[str]) -> tuple[float, int, bool]:
    conf = claim.frontmatter.get("confidence")
    if not isinstance(conf, dict) or "base" not in conf:
        raise ValueError(
            f"claim {page_id(claim)!r} has no confidence.base; ingest must set it"
        )
    base = float(conf["base"])
    sources = claim.frontmatter.get("sources") or []
    source_count = len({str(s) for s in sources})
    contradicted = page_id(claim) in contradicted_ids
    return base, source_count, contradicted


# --------------------------------------------------------------------------- #
# recompute (the only writer of effective)                                    #
# --------------------------------------------------------------------------- #
def recompute(claim_page: Page, wiki_dir: Path, config: dict) -> Page:
    """Recompute a claim's derived confidence fields in place and return it.

    Writes ``effective``, ``source_count``, ``contradicted`` and ``inputs_hash``;
    leaves ``base`` untouched. Deterministic, hence idempotent: a second call
    over unchanged inputs reproduces identical values.
    """
    pages = wiki.list_pages(wiki_dir) if wiki_dir is not None else []
    contradicted_ids = _contradicted_ids(pages) if pages else set()
    # Also honour an outgoing contradicts edge on the claim itself, in case the
    # claim is being recomputed before it has been listed into the wiki dir.
    if any(l.kind == "contradicts" for l in parse_links(claim_page.body)):
        contradicted_ids = contradicted_ids | {page_id(claim_page)}

    base, source_count, contradicted = _claim_inputs(claim_page, contradicted_ids)
    effective, ihash = compute(base, source_count, contradicted, config)

    conf = dict(claim_page.frontmatter.get("confidence", {}))
    conf["base"] = base
    conf["source_count"] = source_count
    conf["contradicted"] = contradicted
    conf["effective"] = effective
    conf["inputs_hash"] = ihash
    claim_page.frontmatter["confidence"] = conf
    return claim_page


def recompute_all(wiki_dir: Path, config: dict) -> int:
    """Recompute every claim page in the wiki, writing changed pages to disk.

    Returns the count of pages whose confidence block actually changed (a clean
    wiki returns 0 — idempotent at the corpus level).
    """
    pages = wiki.list_pages(wiki_dir)
    contradicted_ids = _contradicted_ids(pages)
    updated = 0
    for page in pages:
        if page.frontmatter.get("type") != "claim":
            continue
        before = dict(page.frontmatter.get("confidence", {}))
        base, source_count, contradicted = _claim_inputs(page, contradicted_ids)
        effective, ihash = compute(base, source_count, contradicted, config)
        after = {
            **before,
            "base": base,
            "source_count": source_count,
            "contradicted": contradicted,
            "effective": effective,
            "inputs_hash": ihash,
        }
        if after != before:
            page.frontmatter["confidence"] = after
            wiki.write_page(page)
            updated += 1
    return updated


# --------------------------------------------------------------------------- #
# Rollups (verify the hash; raise on stale rather than read it)               #
# --------------------------------------------------------------------------- #
def _verified_effective(claim: Page, contradicted_ids: set[str], config: dict) -> float:
    """Return a claim's stored ``effective`` only if its ``inputs_hash`` still
    matches the live inputs; otherwise raise :class:`StaleConfidenceError`."""
    conf = claim.frontmatter.get("confidence")
    if not isinstance(conf, dict) or "effective" not in conf or "inputs_hash" not in conf:
        raise StaleConfidenceError(
            f"claim {page_id(claim)!r} has no recomputed effective/inputs_hash; "
            f"run recompute first"
        )
    base, source_count, contradicted = _claim_inputs(claim, contradicted_ids)
    _, live_hash = compute(base, source_count, contradicted, config)
    if conf["inputs_hash"] != live_hash:
        raise StaleConfidenceError(
            f"stale confidence for claim {page_id(claim)!r}: stored inputs_hash "
            f"does not match live inputs; rollup refuses to return a stale value"
        )
    return float(conf["effective"])


def _apply_rollup(values: list[float], config: dict) -> float:
    if not values:
        return 0.0
    kind = _rollup_kind(config)
    if kind == "mean":
        result = sum(values) / len(values)
    elif kind == "max":
        result = max(values)
    else:  # min (default)
        result = min(values)
    return round(result, EFFECTIVE_PRECISION)


def _claim_targets_of(page: Page, pages: list[Page]) -> list[Page]:
    """The claim pages a page links to (any edge kind)."""
    by_id = {page_id(p): p for p in pages}
    base_index = {page_id(p).rsplit("/", 1)[-1]: p for p in pages}
    out: list[Page] = []
    seen: set[str] = set()
    for link in parse_links(page.body):
        target = by_id.get(link.target_id) or base_index.get(link.target_id.rsplit("/", 1)[-1])
        if target is not None and target.frontmatter.get("type") == "claim":
            pid = page_id(target)
            if pid not in seen:
                seen.add(pid)
                out.append(target)
    return out


def rollup_page(page: Page, wiki_dir: Path, config: dict) -> float:
    """Roll up a non-claim page's confidence as the (default ``min``) over the
    claims it aggregates. Raises on any stale claim."""
    pages = wiki.list_pages(wiki_dir)
    contradicted_ids = _contradicted_ids(pages)
    if page.frontmatter.get("type") == "claim":
        claims = [page]
    else:
        claims = _claim_targets_of(page, pages)
    values = [_verified_effective(c, contradicted_ids, config) for c in claims]
    return _apply_rollup(values, config)


def rollup_edge(link: Link, wiki_dir: Path, config: dict) -> float:
    """Roll up an edge's confidence as the (default ``min``) over its claim
    endpoints. A :class:`Link` names its target; when the target is itself a
    claim that is the endpoint, otherwise the claims the target links to are
    used. Raises on any stale endpoint claim."""
    pages = wiki.list_pages(wiki_dir)
    contradicted_ids = _contradicted_ids(pages)
    by_id = {page_id(p): p for p in pages}
    base_index = {page_id(p).rsplit("/", 1)[-1]: p for p in pages}
    target = by_id.get(link.target_id) or base_index.get(link.target_id.rsplit("/", 1)[-1])
    if target is None:
        return 0.0
    if target.frontmatter.get("type") == "claim":
        endpoints = [target]
    else:
        endpoints = _claim_targets_of(target, pages)
    values = [_verified_effective(c, contradicted_ids, config) for c in endpoints]
    return _apply_rollup(values, config)
