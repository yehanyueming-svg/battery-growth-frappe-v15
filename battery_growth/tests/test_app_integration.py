"""Installation and static contracts for Battery Growth Desk integration."""

import json
import unittest
from pathlib import Path


try:
	import frappe as _frappe
	from frappe.tests.utils import FrappeTestCase
except ModuleNotFoundError as error:
	if error.name != "frappe":
		raise
	_frappe = None
	FrappeTestCase = unittest.TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_PATH = APP_ROOT / "battery_growth" / "workspace" / "battery_growth" / "battery_growth.json"
ARTIFACT_PATHS = (
	APP_ROOT / "battery_growth" / "doctype" / "service_subscription" / "service_subscription.json",
	APP_ROOT / "battery_growth" / "doctype" / "growth_ai_settings" / "growth_ai_settings.json",
	APP_ROOT / "battery_growth" / "report" / "user_growth_analysis" / "user_growth_analysis.json",
	APP_ROOT / "battery_growth" / "page" / "battery_growth_dashboard" / "battery_growth_dashboard.json",
	WORKSPACE_PATH,
)


class TestAppIntegration(FrappeTestCase):
	def test_all_standard_artifacts_exist(self):
		if _frappe is None:
			self.skipTest("Requires a Frappe site database.")

		self.assertTrue(_frappe.db.exists("DocType", "Service Subscription"))
		self.assertTrue(_frappe.db.exists("DocType", "Growth AI Settings"))
		self.assertTrue(_frappe.db.exists("Report", "User Growth Analysis"))
		self.assertTrue(_frappe.db.exists("Page", "battery-growth-dashboard"))
		self.assertTrue(_frappe.db.exists("Workspace", "Battery Growth"))


class TestWorkspaceStaticContract(unittest.TestCase):
	def test_workspace_metadata_and_navigation_contract(self):
		self.assertTrue(WORKSPACE_PATH.is_file(), "standard Workspace JSON is missing")
		workspace = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))

		self.assertEqual(workspace["doctype"], "Workspace")
		self.assertEqual(workspace["name"], "Battery Growth")
		self.assertEqual(workspace["title"], "Battery Growth")
		self.assertEqual(workspace["label"], "智格用户增长中心")
		self.assertEqual(workspace["module"], "Battery Growth")
		self.assertEqual(workspace["public"], 1)
		self.assertEqual(workspace["icon"], "chart-line")

		shortcuts = {(item["type"], item["link_to"]): item for item in workspace["shortcuts"]}
		self.assertEqual(set(shortcuts), {("DocType", "Service Subscription")})
		self.assertEqual(len(workspace["shortcuts"]), 2)
		self.assertEqual(
			{item["doc_view"] for item in workspace["shortcuts"]}, {"List", "New"}
		)

		links = {(item["link_type"], item["link_to"]): item for item in workspace["links"] if item["type"] == "Link"}
		self.assertEqual(set(links), {("Report", "User Growth Analysis"), ("Page", "battery-growth-dashboard"), ("DocType", "Growth AI Settings")})
		self.assertEqual(links[("Report", "User Growth Analysis")]["is_query_report"], 1)
		self.assertNotIn("only_for", links[("DocType", "Growth AI Settings")])
		self.assertFalse(any(link.get("hidden") for link in links.values()))

	def test_referenced_standard_artifact_metadata_matches_workspace_routes(self):
		for path in ARTIFACT_PATHS:
			self.assertTrue(path.is_file(), f"missing standard artifact: {path.relative_to(APP_ROOT)}")

		report = json.loads(ARTIFACT_PATHS[2].read_text(encoding="utf-8"))
		page = json.loads(ARTIFACT_PATHS[3].read_text(encoding="utf-8"))
		settings = json.loads(ARTIFACT_PATHS[1].read_text(encoding="utf-8"))
		self.assertEqual((report["doctype"], report["name"]), ("Report", "User Growth Analysis"))
		self.assertEqual((page["doctype"], page["page_name"]), ("Page", "battery-growth-dashboard"))
		self.assertEqual((settings["doctype"], settings["name"]), ("DocType", "Growth AI Settings"))
		self.assertEqual(settings["permissions"], [{"read": 1, "role": "System Manager", "write": 1}])

	def test_workspace_introduces_no_custom_binary_assets(self):
		workspace_directory = WORKSPACE_PATH.parent
		binary_assets = [
			path
			for path in workspace_directory.rglob("*")
			if path.is_file() and path.suffix.lower() in {".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
		]
		self.assertEqual(binary_assets, [])
