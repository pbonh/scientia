"""scientia.hermes.render — turn an :class:`~scientia.hermes.plan.EmitPlan` into
concrete backend operations (pure).

Two backends, same plan:

* :func:`to_rest` — the primary path: ``POST /tasks`` create ops (epic first,
  then cards in topological order) followed by ``POST /links`` ops wiring each
  card to its parents. Every op is a plain dict ``{method, path, json}``.
* :func:`to_cli` — the fallback (and, on hosts with no kanban REST plugin, the
  *only* backend): ``hermes kanban …`` argv lists with the same ordering,
  targeting the v0.15.1 CLI grammar (``create`` with a positional title, no
  ``--status``, group-level ``--board``, positional ``link``).

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


def task_payload(
    card: CardSpec,
    board: Optional[str] = None,
    parent_ids: Optional[Iterable[str]] = None,
) -> dict:
    """The ``POST /tasks`` JSON body for one card (idempotency key = card key).

    ``board`` is the plan-level board slug (:attr:`EmitPlan.board`) the card lands
    on; when set it is sent so each project's cards stay on their own board.

    ``parent_ids`` are the live hermes ids of the card's parents, resolved by the
    caller. When given, they are sent at **create** time so the card is created
    already ``blocked`` behind its dependencies — the dispatcher cannot claim it
    before its gate exists (friction F-1). Omitting them (or passing an empty
    iterable) keeps the field off the payload.
    """
    payload: dict = {
        "title": card.title,
        "body": card.body,
        "status": "todo",
        "idempotency_key": card.key,
    }
    if board:
        payload["board"] = board
    if parent_ids is not None:
        ids = [str(p) for p in parent_ids if p]
        if ids:
            payload["parents"] = ids
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
    if card.base_sha is not None:
        payload["base_sha"] = card.base_sha
    if card.wave is not None:
        payload["wave"] = card.wave
    return payload


def _all_cards(plan: EmitPlan) -> list[CardSpec]:
    cards = list(plan.cards)
    return ([plan.epic] + cards) if plan.epic is not None else cards


def to_rest(plan: EmitPlan, id_for: IdFor) -> list[dict]:
    """REST ops: one create per card (epic first, then topo-ordered), each
    carrying its resolved parent ids so the card is created already gated.

    Parents are wired **at create** rather than in a trailing ``/links`` pass so
    a child is never momentarily dispatchable before its dependency edge exists
    (friction F-1). The only edge a create-time link cannot express — rewiring an
    *already-existing* child onto a *newly re-keyed* parent — is handled by the
    live writer :func:`scientia.hermes.apply.apply`, which is the only place that
    knows which cards pre-existed this run.
    """
    ops: list[dict] = []
    for card in _all_cards(plan):
        parent_ids = [id_for(pk) for pk in card.parents]
        ops.append(
            {
                "method": "POST",
                "path": "/tasks",
                "json": task_payload(card, plan.board, parent_ids=parent_ids),
                "key": card.key,
            }
        )
    return ops


def to_cli(plan: EmitPlan, id_for: IdFor) -> list[list[str]]:
    """CLI ops for the v0.15.1 ``hermes kanban`` grammar, same ordering as REST.

    The v0.15.1 surface differs from the abstract REST seam in four ways:

    * the verb is ``hermes kanban create`` (there is no ``task`` subcommand) and
      the title is a **positional** argument, not ``--title``;
    * the board is selected on the **group**, before the verb —
      ``hermes kanban --board <slug> create …`` — there is no ``create --board``;
    * there is no ``--status`` flag (a fresh card defaults to ready); and
    * ``create`` carries **no per-task model flags**. A profile's model is
      configured on the profile itself (``hermes profile`` / its ``config.yaml``),
      so ``card.model`` is *not* expressible on the CLI backend — it rides on the
      assignee profile that scientia-hermes-init provisions. preflight still
      validates the model's ``api_key_env`` independently of the backend.

    Parents are passed with ``--parent <id>`` **at create time** (v0.15.x) so the
    card is created already ``blocked`` behind its dependencies and the dispatcher
    cannot claim it before its gate exists (friction F-1). There is no trailing
    ``link`` pass here: the one edge a create-time link cannot express — rewiring
    an *already-existing* child onto a *newly re-keyed* parent (rewire-on-rekey) —
    is emitted by the live writer :func:`scientia.hermes.apply.apply`, which alone
    knows which cards pre-existed this run.
    """
    argv: list[list[str]] = []
    for card in _all_cards(plan):
        cmd = ["hermes", "kanban"]
        if plan.board:
            cmd += ["--board", plan.board]   # group-level, before the verb
        cmd += [
            "create", card.title,            # title is positional in v0.15.1
            "--body", card.body,
            "--idempotency-key", card.key,
        ]
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
        for parent_key in card.parents:     # gate at create (friction F-1)
            pid = id_for(parent_key)
            if pid:
                cmd += ["--parent", str(pid)]
        cmd += ["--json"]
        argv.append(cmd)
    return argv


def archive_ops(ids: Iterable[str]) -> list[dict]:
    """``PATCH /tasks/:id`` status=archived ops for superseded cards."""
    return [
        {"method": "PATCH", "path": f"/tasks/{i}", "json": {"status": "archived"}}
        for i in ids
    ]


def archive_argv(ids: Iterable[str]) -> list[list[str]]:
    """v0.15.1 archive: ``hermes kanban archive <id>`` (no ``task update`` verb)."""
    return [["hermes", "kanban", "archive", str(i)] for i in ids]


def reassign_op(task_id: str, assignee: str) -> dict:
    """The integrator's conflict handoff: reassign an integrate card to the
    ``conflict-resolver`` profile — never a ``block`` to a human (§9.2, AC-14)."""
    return {"method": "PATCH", "path": f"/tasks/{task_id}", "json": {"assignee": assignee}}


def comment_op(task_id: str, text: str) -> dict:
    """A mid-flight comment (e.g. the two branch heads handed to the resolver)."""
    return {"method": "POST", "path": f"/tasks/{task_id}/comments", "json": {"body": text}}
