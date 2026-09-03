"""Dependency-light tests for the production demo generator when Bench is unavailable."""

import datetime
import importlib
import sys
import types
import unittest
from collections import Counter


class ValidationError(Exception):
	pass


try:
	import frappe as _frappe  # noqa: F401
except ModuleNotFoundError as error:
	if error.name != "frappe":
		raise
	HAS_REAL_FRAPPE = False
else:
	HAS_REAL_FRAPPE = True


class FakeDB:
	def __init__(self):
		self.rows = []
		self.commit_calls = 0

	def delete(self, doctype, filters):
		self.rows[:] = [
			row for row in self.rows if not all(row.get(key) == value for key, value in filters.items())
		]

	def exists(self, doctype, filters):
		return any(all(row.get(key) == value for key, value in filters.items()) for row in self.rows)

	def count(self, doctype, filters):
		return sum(all(row.get(key) == value for key, value in filters.items()) for row in self.rows)

	def commit(self):
		self.commit_calls += 1


def _install_frappe_stub():
	db = FakeDB()
	frappe = types.ModuleType("frappe")
	frappe.ValidationError = ValidationError
	frappe.throw = lambda message: (_ for _ in ()).throw(ValidationError(message))
	frappe._ = lambda message: message
	frappe.whitelist = lambda: lambda function: function
	frappe.db = db
	utils = types.ModuleType("frappe.utils")
	utils.cint = lambda value: int(value)
	utils.getdate = lambda value: datetime.date.fromisoformat(str(value))
	utils.today = lambda: "2026-09-03"
	frappe.utils = utils
	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class Document:
		def __init__(self, **values):
			self.__dict__.update(values)

	document.Document = Document
	return db, {
		"frappe": frappe,
		"frappe.utils": utils,
		"frappe.model": model,
		"frappe.model.document": document,
	}


def _load_generator_with_stub():
	db, stub_modules = _install_frappe_stub()
	missing = object()
	original_modules = {name: sys.modules.get(name, missing) for name in stub_modules}
	try:
		sys.modules.update(stub_modules)
		controller = importlib.import_module(
			"battery_growth.battery_growth.doctype.service_subscription.service_subscription"
		).ServiceSubscription

		class FakeDocument:
			def __init__(self, values):
				self.values = values

			def insert(self, ignore_permissions=False):
				controller(**self.values).validate()
				db.rows.append(self.values.copy())
				return self

		stub_modules["frappe"].get_doc = lambda values: FakeDocument(values)
		generator = importlib.import_module("battery_growth.setup.demo")
		return db, generator
	finally:
		for name, original_module in original_modules.items():
			if original_module is missing:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original_module


if not HAS_REAL_FRAPPE:
	DB, demo = _load_generator_with_stub()


@unittest.skipIf(HAS_REAL_FRAPPE, "requires the no-Frappe fallback environment")
class TestDemoGenerator(unittest.TestCase):
	def setUp(self):
		DB.rows.clear()
		DB.commit_calls = 0

	def test_seed_creates_exact_count_of_valid_rows_with_reactivations(self):
		result = demo.seed_demo_data(rebuild=True, count=240)
		self.assertEqual(result, {"created": 240, "skipped": 0})
		self.assertEqual(len(DB.rows), 240)
		self.assertEqual(DB.commit_calls, 1)
		self.assertTrue(all(row["is_mock"] == 1 for row in DB.rows))
		self.assertTrue(all(row["customer_type"] in {"个人", "企业"} for row in DB.rows))
		self.assertTrue(any(row["customer_type"] == "个人" for row in DB.rows))
		self.assertTrue(any(row["customer_type"] == "企业" for row in DB.rows))
		self.assertTrue(any(row["service_status"] == "已流失" for row in DB.rows))
		by_code = {}
		for row in DB.rows:
			by_code.setdefault(row["customer_code"], []).append(row)
		reactivated = [rows for rows in by_code.values() if len(rows) == 2]
		self.assertEqual(len(reactivated), 28)
		for rows in reactivated:
			self.assertEqual(rows[0]["service_status"], "已流失")
			self.assertEqual(rows[1]["service_status"], "在服")
			self.assertLess(rows[0]["churn_date"], rows[1]["activation_date"])

	def test_default_seed_has_zhejiang_majority_and_other_regions(self):
		demo.seed_demo_data(rebuild=True)
		province_counts = Counter(row["province"] for row in DB.rows)
		self.assertGreater(province_counts["浙江省"], len(DB.rows) // 2)
		self.assertGreater(sum(count for province, count in province_counts.items() if province != "浙江省"), 0)
		self.assertTrue(
			all(row["city"] in row["swap_station"] for row in DB.rows),
			"station labels must remain coherent with their city",
		)

	def test_seed_is_deterministic_idempotent_and_preserves_non_mock_rows(self):
		non_mock = {"customer_code": "REAL-001", "is_mock": 0}
		DB.rows.append(non_mock)
		first = demo.seed_demo_data(rebuild=True, count=24)
		first_rows = [row.copy() for row in DB.rows if row["is_mock"] == 1]
		second = demo.seed_demo_data(count=24)
		self.assertEqual(first, {"created": 24, "skipped": 0})
		self.assertEqual(second, {"created": 0, "skipped": 24})
		self.assertEqual(DB.rows[0], non_mock)
		self.assertEqual(DB.commit_calls, 1)
		demo.seed_demo_data(rebuild=True, count=24)
		second_rows = [row.copy() for row in DB.rows if row["is_mock"] == 1]
		self.assertEqual(first_rows, second_rows)
		self.assertEqual(DB.rows[0], non_mock)
		self.assertEqual(DB.commit_calls, 2)

	def test_seed_rejects_counts_outside_the_supported_range(self):
		for count in (0, 1001):
			with self.subTest(count=count), self.assertRaisesRegex(ValidationError, "count 必须在 1 到 1000 之间"):
				demo.seed_demo_data(count=count)

	def test_after_install_uses_the_default_seed_without_rebuilding(self):
		demo.after_install()
		self.assertEqual(len(DB.rows), 240)
		self.assertEqual(DB.commit_calls, 1)
