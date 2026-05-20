"""Tests for emit_one() — the orchestrated `hermes kanban create` driver.

emit_one(bundle, *, pattern, tenant, workspace, runner) returns
    EmitResult{
        ids_by_key: dict[str, str],  # idempotency_key -> task_id
        commands:   list[list[str]], # argv of every hermes call issued
    }

The `runner` injection is a callable that mimics subprocess.run, so tests can
assert on argv without ever shelling out.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from tests import _paths  # noqa: F401

import emit


# ---------------------------------------------------------------------------
# Fake runner — returns canned hermes-style responses
# ---------------------------------------------------------------------------


class FakeRunner:
    """Mimics subprocess.run; assigns sequential `t_NN` ids to each `create`."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self._next_id = 0
        # If a key is in `existing_ids`, the corresponding `create` "returns"
        # that existing id (modelling Hermes' idempotency-key dedup).
        self.existing_ids: dict[str, str] = {}

    def __call__(self, argv, *, capture_output=True, text=True, check=False, **_):
        self.calls.append(list(argv))
        # `create` (not `comment`, not `link`) is the one we model in JSON.
        if "create" in argv:
            key = self._extract_flag(argv, "--idempotency-key")
            if key and key in self.existing_ids:
                tid = self.existing_ids[key]
            else:
                self._next_id += 1
                tid = f"t_{self._next_id:02d}"
            stdout = json.dumps({"task_id": tid})
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    @staticmethod
    def _extract_flag(argv, flag):
        try:
            i = argv.index(flag)
            return argv[i + 1]
        except (ValueError, IndexError):
            return None


# ---------------------------------------------------------------------------
# Bundle fixture
# ---------------------------------------------------------------------------


def _bundle_with(n_children: int) -> emit.BodyBundle:
    parent = emit.TaskBody(
        title="[cap] cap — spec",
        body_markdown="parent body",
        idempotency_key="cap:ADR-0001:PARENTHASH",
        assignee="scientia-implementer",
    )
    aggregator = emit.TaskBody(
        title="[cap] aggregator",
        body_markdown="agg body",
        idempotency_key="cap:ADR-0001:PARENTHASH:aggregator",
        assignee="scientia-aggregator",
    )
    children = [
        emit.TaskBody(
            title=f"[cap] scenario {i+1}",
            body_markdown=f"child {i+1} body",
            idempotency_key=f"cap:ADR-0001:scenario-{i+1}:HASH{i+1}",
            assignee="scientia-implementer",
            scenario_slug=f"scenario-{i+1}",
        )
        for i in range(n_children)
    ]
    return emit.BodyBundle(parent=parent, aggregator=aggregator, children=children)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class EmitOneP2PipelineTests(unittest.TestCase):
    def setUp(self):
        self.bundle = _bundle_with(n_children=2)
        self.runner = FakeRunner()
        with TemporaryDirectory() as td:
            self.workspace = f"dir:{Path(td).resolve()}"
            self.result = emit.emit_one(
                bundle=self.bundle,
                pattern="P2-pipeline",
                tenant="ansible",
                workspace=self.workspace,
                runner=self.runner,
            )

    def test_emits_parent_then_three_stages_per_child_then_aggregator(self):
        # 1 parent + 3 stages * 2 children + 1 aggregator = 8 create calls
        create_calls = [c for c in self.runner.calls if "create" in c]
        self.assertEqual(len(create_calls), 1 + 3 * 2 + 1)

    def test_parent_create_uses_correct_flags(self):
        first = self.runner.calls[0]
        self.assertIn("hermes", first)
        self.assertIn("kanban", first)
        self.assertIn("create", first)
        self.assertIn("--idempotency-key", first)
        self.assertIn(self.bundle.parent.idempotency_key, first)
        self.assertIn("--tenant", first)
        self.assertIn("ansible", first)
        self.assertIn("--assignee", first)
        self.assertIn(self.bundle.parent.assignee, first)
        self.assertIn("--body", first)
        # Title is positional, last
        self.assertEqual(first[-1], self.bundle.parent.title)

    def test_pipeline_stages_chain_via_parent_flag(self):
        # Stages 2 and 3 of each scenario should --parent the previous stage id.
        create_calls = [c for c in self.runner.calls if "create" in c]
        # calls[0] = parent
        # calls[1..3] = scenario 1: impl, review, integrate
        # calls[4..6] = scenario 2: impl, review, integrate
        # calls[7] = aggregator

        # scenario 1 review --parent should equal scenario 1 impl's returned id (t_02)
        review = create_calls[2]
        review_parents = [review[i + 1] for i, x in enumerate(review) if x == "--parent"]
        self.assertIn("t_02", review_parents)

        # scenario 1 integrate --parent should be the review id (t_03)
        integrate = create_calls[3]
        integrate_parents = [integrate[i + 1] for i, x in enumerate(integrate) if x == "--parent"]
        self.assertIn("t_03", integrate_parents)

    def test_first_stage_of_each_scenario_depends_on_parent_task(self):
        create_calls = [c for c in self.runner.calls if "create" in c]
        # parent = t_01
        scenario1_impl = create_calls[1]
        scenario2_impl = create_calls[4]
        for c in (scenario1_impl, scenario2_impl):
            parents = [c[i + 1] for i, x in enumerate(c) if x == "--parent"]
            self.assertIn("t_01", parents)

    def test_aggregator_depends_on_every_terminal_stage(self):
        create_calls = [c for c in self.runner.calls if "create" in c]
        aggregator = create_calls[-1]
        agg_parents = [aggregator[i + 1] for i, x in enumerate(aggregator) if x == "--parent"]
        # terminal stages are scenario1 integrate (t_04) and scenario2 integrate (t_07)
        self.assertIn("t_04", agg_parents)
        self.assertIn("t_07", agg_parents)

    def test_stage_assignees_rotate_implementer_reviewer_integrator(self):
        create_calls = [c for c in self.runner.calls if "create" in c]
        # scenario 1 stages
        impl = create_calls[1]
        review = create_calls[2]
        integrate = create_calls[3]
        self.assertEqual(impl[impl.index("--assignee") + 1], "scientia-implementer")
        self.assertEqual(review[review.index("--assignee") + 1], "scientia-reviewer")
        self.assertEqual(integrate[integrate.index("--assignee") + 1], "scientia-integrator")

    def test_stage_idempotency_keys_suffix_stage_name(self):
        create_calls = [c for c in self.runner.calls if "create" in c]
        impl = create_calls[1]
        review = create_calls[2]
        integrate = create_calls[3]
        impl_key = impl[impl.index("--idempotency-key") + 1]
        review_key = review[review.index("--idempotency-key") + 1]
        integrate_key = integrate[integrate.index("--idempotency-key") + 1]
        base = self.bundle.children[0].idempotency_key
        self.assertEqual(impl_key, f"{base}:impl")
        self.assertEqual(review_key, f"{base}:review")
        self.assertEqual(integrate_key, f"{base}:integrate")

    def test_result_maps_every_emitted_key_to_a_task_id(self):
        # Parent + 6 stage keys + aggregator = 8 entries
        self.assertEqual(len(self.result.ids_by_key), 8)
        # Every emitted task id is a hermes-style t_NN string
        for tid in self.result.ids_by_key.values():
            self.assertRegex(tid, r"^t_\d+$")

    def test_no_workspace_flag_means_absolute_path_check_irrelevant(self):
        # All create calls should carry --workspace and it must be the value
        # we passed in (we passed an absolute dir:path so no rejection risk).
        for c in [x for x in self.runner.calls if "create" in x]:
            self.assertIn("--workspace", c)
            self.assertEqual(c[c.index("--workspace") + 1], self.workspace)


class EmitOneP5HumanInLoopTests(unittest.TestCase):
    def setUp(self):
        self.bundle = _bundle_with(n_children=1)
        self.runner = FakeRunner()
        self.result = emit.emit_one(
            bundle=self.bundle,
            pattern="P5-human-in-loop",
            tenant="billing",
            workspace="scratch",
            runner=self.runner,
        )

    def test_first_create_is_a_triage_approval_task(self):
        first = self.runner.calls[0]
        self.assertIn("create", first)
        self.assertIn("--triage", first)
        # An approval task is unassigned (no --assignee, or assignee == "none")
        if "--assignee" in first:
            self.assertEqual(first[first.index("--assignee") + 1], "none")

    def test_parent_task_depends_on_the_approval_task(self):
        create_calls = [c for c in self.runner.calls if "create" in c]
        # approval = t_01, parent = t_02
        parent_create = create_calls[1]
        parents = [parent_create[i + 1] for i, x in enumerate(parent_create) if x == "--parent"]
        self.assertIn("t_01", parents)


class EmitOneRefuseTests(unittest.TestCase):
    def test_pattern_refuse_raises_without_calling_hermes(self):
        bundle = _bundle_with(n_children=1)
        runner = FakeRunner()
        with self.assertRaises(ValueError):
            emit.emit_one(
                bundle=bundle,
                pattern="refuse",
                tenant="anything",
                workspace="scratch",
                runner=runner,
            )
        self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
