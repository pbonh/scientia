"""Tests for collaboration-pattern selection in scripts/emit.py.

`pattern_for(adr_status, *, tenant, config)` resolves the per-spec pattern
from the verified change's ADR status, with a tenant-level override.

config shape (from development/config.yaml):
    emit:
      default_pattern_by_adr_status:
        accepted:   P2-pipeline
        proposed:   P5-human-in-loop
        deprecated: refuse
        superseded: refuse
      require_approval_tenants: [<tenant>, ...]   # force P5 even when accepted
"""

import unittest

from tests import _paths  # noqa: F401

import emit


DEFAULT_CONFIG = {
    "emit": {
        "default_pattern_by_adr_status": {
            "accepted": "P2-pipeline",
            "proposed": "P5-human-in-loop",
            "deprecated": "refuse",
            "superseded": "refuse",
        },
        "require_approval_tenants": [],
    }
}


class PatternForTests(unittest.TestCase):
    def test_accepted_maps_to_P2_pipeline(self):
        self.assertEqual(
            emit.pattern_for("accepted", tenant="ansible", config=DEFAULT_CONFIG),
            "P2-pipeline",
        )

    def test_proposed_maps_to_P5_human_in_loop(self):
        self.assertEqual(
            emit.pattern_for("proposed", tenant="ansible", config=DEFAULT_CONFIG),
            "P5-human-in-loop",
        )

    def test_deprecated_is_refuse(self):
        self.assertEqual(
            emit.pattern_for("deprecated", tenant="ansible", config=DEFAULT_CONFIG),
            "refuse",
        )

    def test_superseded_is_refuse(self):
        self.assertEqual(
            emit.pattern_for("superseded", tenant="ansible", config=DEFAULT_CONFIG),
            "refuse",
        )

    def test_tenant_in_require_approval_forces_P5_even_when_accepted(self):
        cfg = {
            "emit": {
                "default_pattern_by_adr_status": {"accepted": "P2-pipeline"},
                "require_approval_tenants": ["billing"],
            }
        }
        self.assertEqual(
            emit.pattern_for("accepted", tenant="billing", config=cfg),
            "P5-human-in-loop",
        )

    def test_tenant_override_does_not_apply_to_other_tenants(self):
        cfg = {
            "emit": {
                "default_pattern_by_adr_status": {"accepted": "P2-pipeline"},
                "require_approval_tenants": ["billing"],
            }
        }
        self.assertEqual(
            emit.pattern_for("accepted", tenant="ansible", config=cfg),
            "P2-pipeline",
        )

    def test_unknown_status_raises(self):
        with self.assertRaises(ValueError):
            emit.pattern_for("draft", tenant="ansible", config=DEFAULT_CONFIG)

    def test_missing_emit_section_raises(self):
        with self.assertRaises(KeyError):
            emit.pattern_for("accepted", tenant="ansible", config={})


if __name__ == "__main__":
    unittest.main()
