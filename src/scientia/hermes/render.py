"""scientia.hermes.render — turn an :class:`~scientia.hermes.plan.EmitPlan` into
concrete backend operations (pure).

Two backends, same plan:

* :func:`to_rest` — the primary path: ``POST /tasks`` create ops (epic first,
  then cards in topological order) followed by ``POST /links`` ops wiring each
  card to its parents. Every op is a plain dict ``{method, path, json}``.
* :func:`to_cli` — the fallback: ``hermes kanban …`` argv lists with the same
  ordering.

Both take ``id_for: key -> hermes id`` and are *pure given it*: with a complete
id map (as in a golden test) they produce the exact bytes that would be sent.
:mod:`.apply` builds that id map incrementally as it creates cards.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from scientia.hermes.plan import CardSpec, EmitPlan, ProfileModel

__all__ = [
    "task_payload",
    "to_rest",
    "to_cli",
    "archive_ops",
    "archive_argv",
    "reassign_op",
    "comment_op",
]

IdFor = Callable[[str], Optional[str]]


def _model_payload(model: ProfileModel) -> dict:
    """Serialize a :class:`ProfileModel` into the JSON object sent to the backend."""
    payload: dict = {
        "provider": model.provider,
        "model": model.model,
    }
    if model.base_url is not None:
        payload["base_url"] = model.base_url
    if model.api_key_env is not None:
        payload["api_key_env"] = model.api_key_env
    if model.temperature is not None:
        payload["temperature"] = model.temperature
    if model.max_tokens is not None:
        payload["max_tokens"] = model.max_tokens
    return payload


def task_payload(card: CardSpec, board: Optional[str] = None) -> dict:
    """The ``POST /tasks`` JSON body for one card (idempotency key = card key).

    ``board`` is the plan-level board slug (:attr:`EmitPlan.board`) the card lands
    on; when set it is sent so each project's cards stay on their own board.
    """
    payload: dict = {
        "title": card.title,
        "body": card.body,
        "status": "todo",
        "idempotency_key": card.key,
    }
    if board:
        payload["board"] = board
    if card.assignee:
        payload["assignee"] = card.assignee
    if card.tenant:
        payload["tenant"] = card.tenant
    if card.workspace:
        payload["workspace"] = card.workspace
    if card.branch:
        payload["branch"] = card.branch
    if card.skills:
        payload["skills"] = list(card.skills)
    if card.priority is not None:
        payload["priority"] = card.priority
    if card.model is not None:
        payload["model"] = _model_payload(card.model)
    return payload


def _all_cards(plan: EmitPlan) -> list[CardSpec]:
    cards = list(plan.cards)
    return ([plan.epic] + cards) if plan.epic is not None else cards


def to_rest(plan: EmitPlan, id_for: IdFor) -> list[dict]:
    """REST ops: all creates (epic first, then topo-ordered cards), then links."""
    ops: list[dict] = []
    for card in _all_cards(plan):
        ops.append(
            {"method": "POST", "path": "/tasks", "json": task_payload(card, plan.board), "key": card.key}
        )
    for card in _all_cards(plan):
        for parent_key in card.parents:
            ops.append(
                {
                    "method": "POST",
                    "path": "/links",
                    "json": {"parent": id_for(parent_key), "child": id_for(card.key)},
                }
            )
    return ops


def to_cli(plan: EmitPlan, id_for: IdFor) -> list[list[str]]:
    """CLI fallback: ``hermes kanban …`` argv lists, same ordering as REST."""
    argv: list[list[str]] = []
    for card in _all_cards(plan):
        cmd = [
            "hermes", "kanban", "task", "create",
            "--title", card.title,
            "--body", card.body,
            "--idempotency-key", card.key,
            "--status", "todo",
        ]
        if plan.board:
            cmd += ["--board", plan.board]
        if card.assignee:
            cmd += ["--assignee", card.assignee]
        if card.tenant:
            cmd += ["--tenant", card.tenant]
        if card.workspace:
            cmd += ["--workspace", card.workspace]
        if card.branch:
            cmd += ["--branch", card.branch]
        if card.priority is not None:
            cmd += ["--priority", str(card.priority)]
        for skill in card.skills:
            cmd += ["--skill", skill]
        if card.model is not None:
            cmd += ["--model-provider", card.model.provider,
                    "--model-name", card.model.model]
            if card.model.base_url is not None:
                cmd += ["--model-base-url", card.model.base_url]
            if card.model.api_key_env is not None:
                cmd += ["--model-api-key-env", card.model.api_key_env]
            if card.model.temperature is not None:
                cmd += ["--model-temperature", str(card.model.temperature)]
            if card.model.max_tokens is not None:
                cmd += ["--model-max-tokens", str(card.model.max_tokens)]
        argv.append(cmd)
    for card in _all_cards(plan):
        for parent_key in card.parents:
            argv.append(
                ["hermes", "kanban", "link", "--parent", str(id_for(parent_key)),
                 "--child", str(id_for(card.key))]
            )
    return argv


def archive_ops(ids: Iterable[str]) -> list[dict]:
    """``PATCH /tasks/:id`` status=archived ops for superseded cards."""
    return [
        {"method": "PATCH", "path": f"/tasks/{i}", "json": {"status": "archived"}}
        for i in ids
    ]


def archive_argv(ids: Iterable[str]) -> list[list[str]]:
    return [["hermes", "kanban", "task", "update", str(i), "--status", "archived"] for i in ids]


def reassign_op(task_id: str, assignee: str) -> dict:
    """The integrator's conflict handoff: reassign an integrate card to the
    ``conflict-resolver`` profile — never a ``block`` to a human (§9.2, AC-14)."""
    return {"method": "PATCH", "path": f"/tasks/{task_id}", "json": {"assignee": assignee}}


def comment_op(task_id: str, text: str) -> dict:
    """A mid-flight comment (e.g. the two branch heads handed to the resolver)."""
    return {"method": "POST", "path": f"/tasks/{task_id}/comments", "json": {"body": text}}
