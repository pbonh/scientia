"""Tests for re-emit drift handling.

`hermes kanban create --idempotency-key <key>` returns the existing task id
when a task with that key is already on the board. Hermes has no `update
body` verb, so emit.py refreshes drifted task bodies by posting a
`hermes kanban comment <id>` with the freshly-computed body.

The caller passes `existing_keys: dict[idempotency_key, task_id]`
(populated from a pre-emit `hermes kanban list --tenant <T> --json`),
which emit_one uses to decide which keys triggered the dedup path and
need a refresh comment.
"""

import json
import unittest
from types import SimpleNamespace

from tests import _paths  # noqa: F401

import emit


class FakeRunner:
    def __init__(self, existing_ids=None):
        self.calls: list[list[str]] = []
        self._next_id = 0
        self.existing_ids = dict(existing_ids or {})

    def __call__(self, argv, *, capture_output=True, text=True, check=False, **_):
        self.calls.append(list(argv))
        if "create" in argv:
            try:
                key = argv[argv.index("--idempotency-key") + 1]
            except (ValueError, IndexError):
                key = None
            if key and key in self.existing_ids:
                tid = self.existing_ids[key]
            else:
                self._next_id += 1
                tid = f"t_{self._next_id:02d}"
            return SimpleNamespace(returncode=0, stdout=json.dumps({"task_id": tid}), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def _bundle():
    parent = emit.TaskBody(
        title="[cap] cap — spec",
        body_markdown="PARENT_BODY_v2",
        idempotency_key="cap:ADR-0001:PHASH",
        assignee="scientia-implementer",
    )
    aggregator = emit.TaskBody(
        title="[cap] aggregator",
        body_markdown="AGG_BODY_v2",
        idempotency_key="cap:ADR-0001:PHASH:aggregator",
        assignee="scientia-aggregator",
    )
    children = [
        emit.TaskBody(
            title="[cap] scenario A",
            body_markdown="CHILD_A_BODY_v2",
            idempotency_key="cap:ADR-0001:scenario-a:HA",
            assignee="scientia-implementer",
            scenario_slug="scenario-a",
        ),
    ]
    return emit.BodyBundle(parent=parent, aggregator=aggregator, children=children)


class ReEmitCommentTests(unittest.TestCase):
    def test_no_comments_when_existing_keys_empty(self):
        runner = FakeRunner()
        emit.emit_one(
            bundle=_bundle(),
            pattern="P2-pipeline",
            tenant="ansible",
            workspace="scratch",
            runner=runner,
            existing_keys={},
        )
        comment_calls = [c for c in runner.calls if "comment" in c]
        self.assertEqual(comment_calls, [])

    def test_posts_comment_for_each_existing_key(self):
        bundle = _bundle()
        existing = {
            bundle.parent.idempotency_key: "t_old_parent",
            bundle.aggregator.idempotency_key: "t_old_agg",
        }
        runner = FakeRunner(existing_ids=existing)
        emit.emit_one(
            bundle=bundle,
            pattern="P2-pipeline",
            tenant="ansible",
            workspace="scratch",
            runner=runner,
            existing_keys=existing,
        )
        comment_calls = [c for c in runner.calls if "comment" in c]
        self.assertEqual(len(comment_calls), 2)

    def test_comment_targets_the_pre_existing_task_id(self):
        bundle = _bundle()
        existing = {bundle.parent.idempotency_key: "t_old_parent"}
        runner = FakeRunner(existing_ids=existing)
        emit.emit_one(
            bundle=bundle,
            pattern="P2-pipeline",
            tenant="ansible",
            workspace="scratch",
            runner=runner,
            existing_keys=existing,
        )
        comment_call = next(c for c in runner.calls if "comment" in c)
        # `hermes kanban comment <task_id> ...`
        self.assertIn("t_old_parent", comment_call)

    def test_comment_body_contains_refreshed_body_and_timestamp(self):
        bundle = _bundle()
        existing = {bundle.parent.idempotency_key: "t_old_parent"}
        runner = FakeRunner(existing_ids=existing)
        emit.emit_one(
            bundle=bundle,
            pattern="P2-pipeline",
            tenant="ansible",
            workspace="scratch",
            runner=runner,
            existing_keys=existing,
        )
        comment_call = next(c for c in runner.calls if "comment" in c)
        body = comment_call[comment_call.index("--body") + 1]
        self.assertIn("PARENT_BODY_v2", body)
        self.assertIn("refreshed-at", body.lower())

    def test_create_still_called_for_pre_existing_key(self):
        # The dedup happens on Hermes' side; emit.py still calls create
        # so it gets the canonical task_id back.
        bundle = _bundle()
        existing = {bundle.parent.idempotency_key: "t_old_parent"}
        runner = FakeRunner(existing_ids=existing)
        emit.emit_one(
            bundle=bundle,
            pattern="P2-pipeline",
            tenant="ansible",
            workspace="scratch",
            runner=runner,
            existing_keys=existing,
        )
        create_for_parent = next(
            c for c in runner.calls
            if "create" in c and bundle.parent.idempotency_key in c
        )
        self.assertIsNotNone(create_for_parent)


if __name__ == "__main__":
    unittest.main()
