"""Tests for check_browser_provider.py and apply_browser_toolset.py."""

import json
import unittest
from types import SimpleNamespace

from tests import _paths  # noqa: F401

import check_browser_provider as cbp
import apply_browser_toolset as abt


def cfg(jobhunt=None, **extra):
    out = dict(extra)
    if jobhunt is not None:
        out["jobhunt"] = jobhunt
    return out


class CheckBrowserProviderTests(unittest.TestCase):
    def test_feature_off_returns_none(self):
        self.assertIsNone(cbp.check_browser_provider(config={}))

    def test_cdp_reachable(self):
        c = cfg({"browser": {"provider": "cdp",
                             "cdp_endpoint": "http://127.0.0.1:9222"}})
        reason = cbp.check_browser_provider(
            config=c, endpoint_reachable=lambda e: True)
        self.assertIsNone(reason)

    def test_cdp_unreachable_refuses(self):
        c = cfg({"browser": {"provider": "cdp"}})
        reason = cbp.check_browser_provider(
            config=c, endpoint_reachable=lambda e: False)
        self.assertIsNotNone(reason)
        self.assertIn("cdp", reason)
        self.assertIn("remote-debugging-port", reason)

    def test_managed_key_present_in_env(self):
        c = cfg({"browser": {"provider": "browserbase"}})
        reason = cbp.check_browser_provider(
            config=c, environ={"BROWSERBASE_API_KEY": "x"})
        self.assertIsNone(reason)

    def test_managed_key_missing_refuses(self):
        c = cfg({"browser": {"provider": "browserbase"}})
        reason = cbp.check_browser_provider(config=c, environ={})
        self.assertIsNotNone(reason)
        self.assertIn("BROWSERBASE_API_KEY", reason)

    def test_unknown_provider_refuses(self):
        c = cfg({"browser": {"provider": "wat"}})
        reason = cbp.check_browser_provider(config=c, environ={})
        self.assertIn("not a known provider", reason)

    def test_default_provider_is_cdp(self):
        # No provider declared -> defaults to cdp -> uses endpoint check.
        c = cfg({"browser": {}})
        reason = cbp.check_browser_provider(
            config=c, endpoint_reachable=lambda e: False)
        self.assertIsNotNone(reason)
        self.assertIn("9222", reason)


def _runner(toolsets, set_rc=0, set_stderr=""):
    """Fake hermes runner: config show returns the given toolsets; config set
    returns set_rc."""
    def run(argv, **kw):
        if argv[3:5] == ["config", "show"]:
            return SimpleNamespace(returncode=0,
                                   stdout=json.dumps({"toolsets": toolsets}),
                                   stderr="")
        if argv[3:5] == ["config", "set"]:
            return SimpleNamespace(returncode=set_rc, stdout="", stderr=set_stderr)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


class ApplyBrowserToolsetTests(unittest.TestCase):
    def test_feature_off_skips(self):
        res = abt.ensure_browser_toolset(config={}, runner=_runner([]))
        self.assertTrue(res.get("skipped"))

    def test_already_enabled(self):
        c = cfg({"browser": {"provider": "cdp"}})
        res = abt.ensure_browser_toolset(
            config=c, runner=_runner(["files", "browser"]))
        self.assertTrue(res["already"])
        self.assertFalse(res["enabled"])
        self.assertEqual(res["profile"], "scientia-jobhunt-agent")

    def test_enables_when_absent(self):
        c = cfg({"browser": {"provider": "cdp"}})
        captured = {}

        def run(argv, **kw):
            if argv[3:5] == ["config", "show"]:
                return SimpleNamespace(returncode=0,
                                       stdout=json.dumps({"toolsets": ["files"]}),
                                       stderr="")
            if argv[3:5] == ["config", "set"]:
                captured["argv"] = argv
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        res = abt.ensure_browser_toolset(config=c, runner=run)
        self.assertTrue(res["enabled"])
        # The set call must include browser appended to the existing list.
        self.assertEqual(captured["argv"][5], "toolsets")
        self.assertEqual(json.loads(captured["argv"][6]), ["files", "browser"])

    def test_enable_failure_returns_error(self):
        c = cfg({"browser": {"provider": "cdp"}})
        res = abt.ensure_browser_toolset(
            config=c, runner=_runner(["files"], set_rc=1, set_stderr="nope"))
        self.assertIsNotNone(res["error"])
        self.assertIn("nope", res["error"])
        self.assertIn("hermes setup tools", res["error"])


if __name__ == "__main__":
    unittest.main()
