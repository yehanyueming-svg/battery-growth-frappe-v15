"""Focused tests for the permission-checked dashboard API boundary."""

import datetime
import importlib
import json
import sys
import types
import unittest


try:
	import frappe as _frappe
	from frappe.tests.utils import FrappeTestCase
except ModuleNotFoundError as error:
	if error.name != "frappe":
		raise
	_frappe = None
	FrappeTestCase = unittest.TestCase


_STUB_BOUND_MODULES = (
	"battery_growth.analytics",
	"battery_growth.analytics.filters",
	"battery_growth.analytics.metrics",
	"battery_growth.analytics.rules",
	"battery_growth.integrations",
	"battery_growth.integrations.openai_compatible",
	"battery_growth.services",
	"battery_growth.services.insights",
	"battery_growth.api",
	"battery_growth.api.dashboard",
)


def _load_dashboard_without_frappe():
	"""Load the production API against just the framework boundary it consumes."""
	frappe = types.ModuleType("frappe")
	frappe._ = lambda message: message
	frappe.PermissionError = type("PermissionError", (Exception,), {})
	frappe.ValidationError = type("ValidationError", (Exception,), {})
	frappe.has_permission = lambda *_args, **_kwargs: True
	frappe.get_list = lambda *_args, **_kwargs: []
	frappe.get_single = lambda _doctype: None
	frappe.cache = lambda: None
	frappe.log_error = lambda *_args, **_kwargs: None

	def whitelist(methods=None):
		def decorate(method):
			method.whitelisted = True
			if methods is not None:
				method.allowed_http_methods = methods
			return method
		return decorate

	frappe.whitelist = whitelist
	utils = types.ModuleType("frappe.utils")
	utils.getdate = lambda value: value if isinstance(value, datetime.date) else datetime.date.fromisoformat(str(value))
	utils.today = lambda: "2026-09-03"
	utils.now_datetime = lambda: datetime.datetime(2026, 9, 3, 10, 30, 0)
	utils.cint = lambda value: int(value) if str(value).strip() not in ("", "None") else 0
	frappe.utils = utils
	stub_modules = {"frappe": frappe, "frappe.utils": utils}
	missing = object()
	original_modules = {name: sys.modules.get(name, missing) for name in (*stub_modules, *_STUB_BOUND_MODULES)}
	try:
		sys.modules.update(stub_modules)
		return importlib.import_module("battery_growth.api.dashboard")
	finally:
		for name in _STUB_BOUND_MODULES:
			original = original_modules[name]
			if original is missing:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original
		for name in stub_modules:
			original = original_modules[name]
			if original is missing:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original


if _frappe is None:
	dashboard = _load_dashboard_without_frappe()
else:
	from battery_growth.api import dashboard


def metrics_payload(**extra):
	payload = {
		"filters": {"from_date": "2026-01-01", "to_date": "2026-01-31", "granularity": "Month"},
		"summary": {"closing_active": 9},
		"periods": [{"label": "2026-01", "closing_active": 9}],
		"distributions": {"regions": [{"label": "浙江省", "value": 9, "share": 100.0}]},
		"customer_name": "must-not-pass",
		"raw_records": [{"mobile": "must-not-pass"}],
	}
	payload.update(extra)
	return payload


class TestDashboardAPI(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.original_permission = dashboard.frappe.has_permission
		self.original_normalize = dashboard.normalize_filters
		self.original_metrics = dashboard.get_growth_metrics
		self.original_brief = dashboard.get_operations_brief
		dashboard.frappe.has_permission = lambda *_args, **_kwargs: True
		dashboard.normalize_filters = lambda filters: {"normalized": filters}
		self.metric_calls = []
		dashboard.get_growth_metrics = lambda filters: self.metric_calls.append(filters) or metrics_payload()

	def tearDown(self):
		dashboard.frappe.has_permission = self.original_permission
		dashboard.normalize_filters = self.original_normalize
		dashboard.get_growth_metrics = self.original_metrics
		dashboard.get_operations_brief = self.original_brief
		super().tearDown()

	def test_dashboard_denies_before_filter_or_metric_work(self):
		dashboard.frappe.has_permission = lambda *_args, **_kwargs: False
		dashboard.normalize_filters = lambda _filters: self.fail("normalization must not run")
		dashboard.get_growth_metrics = lambda _filters: self.fail("metrics must not run")
		with self.assertRaises(dashboard.frappe.PermissionError):
			dashboard.get_dashboard_data({"from_date": "not-a-date"})

	def test_dashboard_returns_a_fresh_fixed_private_schema_from_one_metric_call(self):
		result = dashboard.get_dashboard_data({"province": "浙江省"})
		self.assertEqual(set(result), {"filters", "summary", "periods", "distributions", "generated_at"})
		self.assertEqual(self.metric_calls, [{"normalized": {"province": "浙江省"}}])
		self.assertNotIn("must-not-pass", json.dumps(result, ensure_ascii=False))
		self.assertIsNot(result["summary"], metrics_payload()["summary"])

	def test_invalid_filters_are_actionable_frappe_validation_errors(self):
		dashboard.normalize_filters = lambda _filters: (_ for _ in ()).throw(ValueError("开始日期不能晚于结束日期"))
		with self.assertRaises(dashboard.frappe.ValidationError) as captured:
			dashboard.get_dashboard_data({"from_date": "2026-02-01", "to_date": "2026-01-01"})
		self.assertIn("开始日期不能晚于结束日期", str(captured.exception))

	def test_operations_brief_is_post_whitelisted_and_denies_before_service_work(self):
		self.assertTrue(dashboard.generate_operations_brief.whitelisted)
		self.assertEqual(dashboard.generate_operations_brief.allowed_http_methods, ["POST"])
		dashboard.frappe.has_permission = lambda *_args, **_kwargs: False
		dashboard.normalize_filters = lambda _filters: self.fail("normalization must not run")
		dashboard.get_operations_brief = lambda *_args, **_kwargs: self.fail("brief service must not run")
		with self.assertRaises(dashboard.frappe.PermissionError):
			dashboard.generate_operations_brief({"from_date": "bad"}, force="1")

	def test_operations_brief_normalizes_once_and_parses_force_with_cint(self):
		brief_calls = []
		dashboard.get_operations_brief = lambda filters, force=False: brief_calls.append((filters, force)) or {"source": "rules"}
		self.assertEqual(dashboard.generate_operations_brief({"city": "杭州市"}, force="0"), {"source": "rules"})
		self.assertEqual(dashboard.generate_operations_brief({"city": "杭州市"}, force="1"), {"source": "rules"})
		self.assertEqual(brief_calls, [({"normalized": {"city": "杭州市"}}, False), ({"normalized": {"city": "杭州市"}}, True)])

	def test_dashboard_read_endpoint_is_whitelisted(self):
		self.assertTrue(dashboard.get_dashboard_data.whitelisted)


class TestNoFrappeIsolation(FrappeTestCase):
	@unittest.skipIf(_frappe is not None, "Only the no-Frappe fallback creates temporary modules.")
	def test_no_frappe_loader_does_not_cache_stub_bound_modules(self):
		missing = object()
		original_modules = {name: sys.modules.pop(name, missing) for name in _STUB_BOUND_MODULES}
		try:
			_load_dashboard_without_frappe()
			self.assertEqual({name for name in _STUB_BOUND_MODULES if name in sys.modules}, set())
		finally:
			for name in _STUB_BOUND_MODULES:
				sys.modules.pop(name, None)
			for name, original in original_modules.items():
				if original is not missing:
					sys.modules[name] = original
