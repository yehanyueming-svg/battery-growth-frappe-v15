"""Contract tests for the User Growth Analysis Script Report."""

import importlib
import sys
import types
import unittest
from datetime import date


try:
	from frappe.tests.utils import FrappeTestCase
except ModuleNotFoundError as error:
	if error.name != "frappe":
		raise
	FrappeTestCase = unittest.TestCase


def _load_report_without_frappe():
	"""Import the production report with only its framework boundary replaced."""
	frappe = types.ModuleType("frappe")
	frappe._ = lambda message: message
	frappe.get_list = lambda *args, **kwargs: []
	utils = types.ModuleType("frappe.utils")
	utils.getdate = lambda value: value if isinstance(value, date) else date.fromisoformat(str(value))
	utils.today = lambda: "2026-09-03"
	frappe.utils = utils
	stub_modules = {"frappe": frappe, "frappe.utils": utils}
	missing = object()
	original_modules = {name: sys.modules.get(name, missing) for name in stub_modules}
	try:
		sys.modules.update(stub_modules)
		return importlib.import_module(
			"battery_growth.battery_growth.report.user_growth_analysis.user_growth_analysis"
		)
	finally:
		for name, original_module in original_modules.items():
			if original_module is missing:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original_module


report = _load_report_without_frappe()


class TestUserGrowthAnalysis(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.original_get_growth_metrics = report.get_growth_metrics
		report.get_growth_metrics = lambda filters: {
			"periods": [
				{
					"label": "2026-01",
					"bucket_start": "2026-01-01",
					"bucket_end": "2026-01-31",
					"opening_active": 8,
					"new_users": 3,
					"churned_users": 1,
					"net_growth": 2,
					"closing_active": 10,
					"churn_rate": 12.5,
					"new_vehicles": 6,
					"new_monthly_fee": 1299.5,
				}
			],
			"summary": {
				"closing_active": 10,
				"new_users": 3,
				"churned_users": 1,
				"net_growth": 2,
				"churn_rate": 12.5,
			},
		}

	def tearDown(self):
		report.get_growth_metrics = self.original_get_growth_metrics
		super().tearDown()

	def test_execute_maps_shared_metrics_to_table_chart_and_summary(self):
		"""Removing a mapped metric or chart dataset must break the report contract."""
		columns, data, message, chart, summary = report.execute(
			{"from_date": "2026-01-01", "to_date": "2026-01-31", "granularity": "Month"}
		)
		self.assertEqual([column["fieldname"] for column in columns], [
			"period", "opening_active", "new_users", "churned_users", "net_growth",
			"closing_active", "churn_rate", "new_vehicles", "new_monthly_fee",
		])
		self.assertEqual(data, [{
			"period": "2026-01", "bucket_start": "2026-01-01", "bucket_end": "2026-01-31",
			"opening_active": 8, "new_users": 3, "churned_users": 1, "net_growth": 2,
			"closing_active": 10, "churn_rate": 12.5, "new_vehicles": 6, "new_monthly_fee": 1299.5,
		}])
		self.assertIsNone(message)
		self.assertEqual(chart["type"], "axis-mixed")
		self.assertEqual(chart["data"]["labels"], ["2026-01"])
		self.assertEqual(chart["data"]["datasets"], [
			{"name": "新增用户", "chartType": "bar", "values": [3]},
			{"name": "流失用户", "chartType": "bar", "values": [1]},
			{"name": "期末在服", "chartType": "line", "values": [10]},
		])
		self.assertEqual(summary, [
			{"label": "期末在服", "value": 10, "indicator": "Blue", "datatype": "Int"},
			{"label": "累计新增", "value": 3, "indicator": "Green", "datatype": "Int"},
			{"label": "累计流失", "value": 1, "indicator": "Red", "datatype": "Int"},
			{"label": "净增长", "value": 2, "indicator": "Green", "datatype": "Int"},
			{"label": "流失率", "value": 12.5, "indicator": "Orange", "datatype": "Percent"},
		])

	def test_execute_keeps_empty_periods_and_zero_summary_values_renderable(self):
		"""Empty analytics output must remain a valid, zero-valued report response."""
		report.get_growth_metrics = lambda filters: {
			"periods": [],
			"summary": {"closing_active": 0, "new_users": 0, "churned_users": 0, "net_growth": 0, "churn_rate": 0.0},
		}
		_columns, data, _message, chart, summary = report.execute({})
		self.assertEqual(data, [])
		self.assertEqual(chart["data"], {"labels": [], "datasets": [
			{"name": "新增用户", "chartType": "bar", "values": []},
			{"name": "流失用户", "chartType": "bar", "values": []},
			{"name": "期末在服", "chartType": "line", "values": []},
		]})
		self.assertEqual([item["value"] for item in summary], [0, 0, 0, 0, 0.0])
