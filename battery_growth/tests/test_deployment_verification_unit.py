"""Dependency-light tests for the Bench-callable deployment assertion."""

import importlib
import sys
import types
import unittest


class FakeDB:
    def __init__(self):
        self.mock_count = 240
        self.artifacts = {
            ("DocType", "Service Subscription"),
            ("Report", "User Growth Analysis"),
            ("Page", "battery-growth-dashboard"),
            ("Workspace", "Battery Growth"),
        }

    def count(self, doctype, filters=None):
        if doctype == "Service Subscription" and filters == {"is_mock": 1}:
            return self.mock_count
        return 0

    def exists(self, doctype, name):
        return (doctype, name) in self.artifacts


def load_verification_module():
    fake_db = FakeDB()
    frappe = types.ModuleType("frappe")
    frappe.__version__ = "15.120.0"
    frappe.conf = types.SimpleNamespace(developer_mode=1)
    frappe.db = fake_db
    frappe.get_installed_apps = lambda: ["frappe", "battery_growth"]
    frappe.get_all = lambda *_args, **_kwargs: ["企业", "个人", "企业"]
    utils = types.ModuleType("frappe.utils")
    utils.cint = lambda value: int(value or 0)
    missing = object()
    names = ("frappe", "frappe.utils", "battery_growth.setup.verification")
    originals = {name: sys.modules.get(name, missing) for name in names}
    try:
        sys.modules["frappe"] = frappe
        sys.modules["frappe.utils"] = utils
        sys.modules.pop("battery_growth.setup.verification", None)
        module = importlib.import_module("battery_growth.setup.verification")
        return module, frappe, fake_db
    finally:
        for name, original in originals.items():
            if original is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class TestDeploymentVerification(unittest.TestCase):
    def setUp(self):
        self.verification, self.frappe, self.db = load_verification_module()

    def test_assert_deployment_returns_non_sensitive_aggregate_facts(self):
        facts = self.verification.assert_deployment()
        self.assertEqual(facts["frappe_version"], "15.120.0")
        self.assertEqual(facts["mock_count"], 240)
        self.assertEqual(facts["customer_types"], ["个人", "企业"])
        self.assertEqual(facts["developer_mode"], 1)
        self.assertEqual(set(facts["artifacts"]), {"doctype", "report", "page", "workspace"})
        self.assertNotIn("password", repr(facts).lower())

    def test_assert_deployment_rejects_wrong_mock_count(self):
        self.db.mock_count = 239
        with self.assertRaisesRegex(AssertionError, "expected 240"):
            self.verification.assert_deployment()

    def test_assert_deployment_rejects_version_app_or_mode_mismatch(self):
        cases = (
            (lambda: setattr(self.frappe, "__version__", "15.119.0"), "Frappe version"),
            (lambda: setattr(self.frappe, "get_installed_apps", lambda: ["frappe"]), "battery_growth"),
            (lambda: setattr(self.frappe.conf, "developer_mode", 0), "developer_mode"),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                self.setUp()
                mutate()
                with self.assertRaisesRegex(AssertionError, message):
                    self.verification.assert_deployment()

    def test_assert_deployment_rejects_missing_customer_type_or_artifact(self):
        self.frappe.get_all = lambda *_args, **_kwargs: ["个人"]
        with self.assertRaisesRegex(AssertionError, "customer types"):
            self.verification.assert_deployment()

        self.setUp()
        self.db.artifacts.remove(("Report", "User Growth Analysis"))
        with self.assertRaisesRegex(AssertionError, "User Growth Analysis"):
            self.verification.assert_deployment()


if __name__ == "__main__":
    unittest.main()
