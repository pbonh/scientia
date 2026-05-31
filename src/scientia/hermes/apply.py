"""scientia.hermes.apply — the single side-effecting writer (IMPURE).

Everything upstream of here is pure; ``apply`` is the one place that mutates the
board. It is REST-first (CLI is a fallback backend) and *ledger-idempotent*: in
topological order it creates each card only when the ledger does not already map
its key to a live id (the idempotency pre-check, AC-3/AC-15), captures the new
id, wires each card's parents **at create time** so it starts ``blocked`` and is
never momentarily dispatchable before its gate exists (friction F-1), emits an
explicit rewire link only for the rewire-on-rekey case (an existing child whose
parent was re-keyed this run), archives superseded cards (``on_supersede:
archive``, AC-4), and writes the updated ledger.

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
    """Map the abstract REST-shaped ops onto the v0.15.1 ``hermes kanban`` CLI.

    This is the board's only API on hosts whose Hermes serves no kanban REST
    plugin (the common case: plain ``hermes gateway`` is the *messaging* gateway).
    The grammar drifted from the seam's REST shape — see
    :func:`scientia.hermes.render.to_cli`: the verb is ``create`` (no ``task``
    subcommand) with a **positional** title, ``--board`` is group-level (before
    the verb), there is no ``--status`` on ``create`` (a card defaults to ready),
    ``link`` takes **positional** ids, and a superseded card is retired with
    ``archive`` (no ``task update`` verb). A card's per-task ``model`` is *not*
    settable here — it lives on the assignee profile (scientia-hermes-init).

    The command construction is delegated to :func:`render.to_cli` and
    :func:`render.archive_argv` to avoid the version-skew drift that occurred
    when this function maintained its own inline command construction
    (friction point #4 from the circuit-solver-beta analysis).
    """
    def _run(cmd: list[str]) -> str:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

    # Map (method, path) to the CLI argv that render.to_cli / archive_argv
    # would produce. This is a single-op-at-a-time adaptation of the batch
    # render functions, keeping the transport's call-at-a-time interface.
    def call(method: str, path: str, body: Optional[dict]) -> dict:
        body = body or {}
        if method == "POST" and path == "/tasks":
            # Build a single-card argv matching render.to_cli's grammar
            cmd = ["hermes", "kanban"]
            board = body.get("board")
            if board:
                cmd += ["--board", board]      # group-level, before the verb
            cmd += [
                "create",                     # no 'task' subcommand in v0.15.1
                body["title"],                 # title is positional
                "--body", body["body"],
                "--idempotency-key", body["idempotency_key"],
            ]
            for opt in ("assignee", "tenant", "workspace", "branch"):
                if body.get(opt):
                    cmd += [f"--{opt}", body[opt]]
            if body.get("priority") is not None:
                cmd += ["--priority", str(body["priority"])]
            for skill in body.get("skills", []):
                cmd += ["--skill", skill]
            for pid in body.get("parents", []):   # gate at create (friction F-1)
                cmd += ["--parent", str(pid)]
            # NOTE: no --model flags — model lives on the assignee profile.
            # base_sha and wave are metadata in the body, not CLI flags.
            cmd += ["--json"]
            out = _run(cmd)
            return json.loads(out) if out.strip() else {}
        if method == "POST" and path == "/links":
            # link takes positional parent_id child_id (v0.15.1 grammar)
            _run(["hermes", "kanban", "link", str(body["parent"]), str(body["child"])])
            return {}
        if method == "PATCH":
            task_id = path.rsplit("/", 1)[-1]
            status = body.get("status")
            if status == "archived":
                _run(["hermes", "kanban", "archive", task_id])
            elif status is not None:
                raise ValueError(
                    f"no v0.15.1 CLI mapping for status {status!r}; use a "
                    f"dedicated verb (block/complete/promote/unblock)"
                )
            if body.get("assignee"):                   # render.reassign_op handoff
                _run(["hermes", "kanban", "reassign", task_id, body["assignee"], "--reclaim"])
            return {}
        if method == "POST" and path.endswith("/comments"):
            task_id = path.rsplit("/", 2)[-2]
            text = body.get("body", "")
            _run(["hermes", "kanban", "comment", task_id, "--body", text])
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
    for card in cards:  # topological order (epic first) — parents precede children
        entry = entries[card.key]
        if entry.hermes_id:  # ledger pre-check -> idempotent skip
            continue
        # Resolve parent ids now: topological order + carried-over ids guarantee
        # every parent already has a live id. Passing them at create makes the
        # card start `blocked`, so the dispatcher cannot claim it before its
        # dependency gate exists (friction F-1).
        parent_ids = [
            entries[pk].hermes_id for pk in card.parents if entries[pk].hermes_id
        ]
        resp = transport(
            "POST", "/tasks",
            render.task_payload(card, plan.board, parent_ids=parent_ids),
        )
        entry.hermes_id = str(resp.get("id"))
        entry.last_status = "todo"
        created.add(card.key)
        # Post a comment with base_sha metadata so the worker and
        # downstream integrator/resolver can read it from kanban_show().
        # Only post when base_sha is actually set (wave is already in the body
        # via the declared-touches comment block).
        if card.base_sha:
            transport("POST", f"/tasks/{entry.hermes_id}/comments",
                       {"body": f"<!-- emit-metadata: base_sha: {card.base_sha} -->"})

    id_map = {k: e.hermes_id for k, e in entries.items() if e.hermes_id}

    # Freshly created cards already had their parents wired at create time (above),
    # so the only link op still needed is rewire-on-rekey: an *existing* child
    # (not created this run) whose parent was *re-keyed* (created this run). A
    # create-time edge cannot express that, so emit an explicit link. An unchanged
    # re-emit creates nothing and rewires nothing (AC-3). (Stale links to an
    # archived old parent are a drift signal scientia-hermes-status reports; R1
    # defers full re-wiring.)
    for card in cards:
        if card.key in created:
            continue  # parents already wired at create
        for parent_key in card.parents:
            if parent_key not in created:
                continue  # parent unchanged -> existing link still valid
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
