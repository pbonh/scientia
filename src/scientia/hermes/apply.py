"""scientia.hermes.apply — the single side-effecting writer (IMPURE).

Everything upstream of here is pure; ``apply`` is the one place that mutates the
board. It is REST-first (CLI is a fallback backend) and *ledger-idempotent*: in
topological order it creates each card only when the ledger does not already map
its key to a live id (the idempotency pre-check, AC-3/AC-15), captures the new
id, wires parent links for the cards it created, archives superseded cards
(``on_supersede: archive``, AC-4), and writes the updated ledger.

The HTTP/CLI call is funnelled through a single ``transport(method, path, body)``
seam, which the integration suite replaces with a recording stub so the whole
writer is exercised with no Hermes process.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from typing import Callable, Optional

from scientia.hermes import ledger, render
from scientia.hermes.plan import EmitPlan

__all__ = ["apply", "DEFAULT_REST_BASE", "Transport"]

DEFAULT_REST_BASE = "http://127.0.0.1:8787/api/plugins/kanban"

Transport = Callable[[str, str, Optional[dict]], dict]


# --------------------------------------------------------------------------- #
# Transports                                                                   #
# --------------------------------------------------------------------------- #
def _rest_transport(rest_base: str) -> Transport:
    base = rest_base.rstrip("/")

    def call(method: str, path: str, body: Optional[dict]) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (loopback only)
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}

    return call


def _cli_transport() -> Transport:
    def call(method: str, path: str, body: Optional[dict]) -> dict:
        body = body or {}
        if method == "POST" and path == "/tasks":
            cmd = [
                "hermes", "kanban", "task", "create", "--json",
                "--idempotency-key", body["idempotency_key"],
                "--title", body["title"], "--body", body["body"],
                "--status", body.get("status", "todo"),
            ]
            for opt in ("assignee", "tenant", "workspace", "branch"):
                if body.get(opt):
                    cmd += [f"--{opt}", body[opt]]
            for skill in body.get("skills", []):
                cmd += ["--skill", skill]
            out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
            return json.loads(out) if out.strip() else {}
        if method == "POST" and path == "/links":
            subprocess.run(
                ["hermes", "kanban", "link", "--parent", str(body["parent"]),
                 "--child", str(body["child"])],
                capture_output=True, text=True, check=True,
            )
            return {}
        if method == "PATCH":
            task_id = path.rsplit("/", 1)[-1]
            cmd = ["hermes", "kanban", "task", "update", task_id]
            if "status" in body:
                cmd += ["--status", body["status"]]
            if "assignee" in body:
                cmd += ["--assignee", body["assignee"]]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return {}
        raise ValueError(f"unsupported CLI op: {method} {path}")

    return call


# --------------------------------------------------------------------------- #
# Writer                                                                       #
# --------------------------------------------------------------------------- #
def apply(
    plan: EmitPlan,
    *,
    dry_run: bool = True,
    backend: str = "rest",
    rest_base: str = DEFAULT_REST_BASE,
    on_supersede: str = "archive",
    transport: Optional[Transport] = None,
    write_ledger: bool = True,
) -> dict[str, str]:
    """Create/skip/archive the plan against the board. Returns ``{key -> id}``.

    With ``dry_run`` (the default) nothing is sent and no ledger is written; the
    returned map shows existing ids and ``"(new)"`` for keys that would be
    created. The real path requires ``dry_run=False``.
    """
    change_id = plan.change_id
    old = ledger.load(change_id)
    cards = ([plan.epic] + list(plan.cards)) if plan.epic is not None else list(plan.cards)

    if dry_run:
        return {
            c.key: (old[c.key].hermes_id if c.key in old and old[c.key].hermes_id else "(new)")
            for c in cards
        }

    if transport is None:
        transport = _rest_transport(rest_base) if backend == "rest" else _cli_transport()

    diff = ledger.diff(old, plan)
    entries = ledger.entries_for_plan(plan)
    for key, entry in entries.items():  # carry over already-created ids/status
        if key in old and old[key].hermes_id:
            entry.hermes_id = old[key].hermes_id
            entry.last_status = old[key].last_status

    created: set[str] = set()
    for card in cards:  # topological order (epic first)
        entry = entries[card.key]
        if entry.hermes_id:  # ledger pre-check -> idempotent skip
            continue
        resp = transport("POST", "/tasks", render.task_payload(card))
        entry.hermes_id = str(resp.get("id"))
        entry.last_status = "todo"
        created.add(card.key)

    id_map = {k: e.hermes_id for k, e in entries.items() if e.hermes_id}

    # Wire a parent link whenever *either* endpoint was created this run: a fresh
    # child needs all its up-edges, and a re-keyed parent needs its existing
    # children rewired onto the new card. An unchanged re-emit creates nothing,
    # so no links are sent (AC-3). (Stale links to an archived old parent are a
    # drift signal scientia-hermes-status reports; R1 defers full re-wiring.)
    for card in cards:
        for parent_key in card.parents:
            if card.key not in created and parent_key not in created:
                continue
            parent_id = id_map.get(parent_key)
            child_id = id_map.get(card.key)
            if parent_id and child_id:
                transport("POST", "/links", {"parent": parent_id, "child": child_id})

    if on_supersede == "archive":
        superseded = list(diff.removed) + [old_key for old_key, _ in diff.changed]
        for old_key in superseded:
            hid = old[old_key].hermes_id
            if hid:
                transport("PATCH", f"/tasks/{hid}", {"status": "archived"})

    if write_ledger:
        ledger.record(change_id, entries)

    return {k: e.hermes_id for k, e in entries.items() if e.hermes_id}
