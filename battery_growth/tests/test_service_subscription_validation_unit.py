"""Native test harness for Service Subscription validation when Bench is unavailable."""

import datetime
import importlib
import sys
import types
import unittest


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


def _install_frappe_stub():
	frappe = types.ModuleType("frappe")
	frappe.ValidationError = ValidationError
	frappe.throw = lambda message: (_ for _ in ()).throw(ValidationError(message))
	frappe._ = lambda message: message

	utils = types.ModuleType("frappe.utils")
	utils.getdate = lambda value: datetime.date.fromisoformat(str(value))
	model = types.ModuleType("frappe.model")
	document = types.ModuleType("frappe.model.document")

	class Document:
		def __init__(self, **values):
			self.__dict__.update(values)

		def validate(self):
			pass

	document.Document = Document
	return {
		"frappe": frappe,
		"frappe.utils": utils,
		"frappe.model": model,
		"frappe.model.document": document,
	}


def _load_controller_with_stub():
	stub_modules = _install_frappe_stub()
	missing = object()
	original_modules = {name: sys.modules.get(name, missing) for name in stub_modules}
	try:
		sys.modules.update(stub_modules)
		return importlib.import_module(
			"battery_growth.battery_growth.doctype.service_subscription.service_subscription"
		).ServiceSubscription
	finally:
		for name, original_module in original_modules.items():
			if original_module is missing:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original_module


ServiceSubscription = None if HAS_REAL_FRAPPE else _load_controller_with_stub()


def make_subscription(**overrides):
	values = {
		"customer_type": "个人",
		"service_status": "在服",
		"activation_date": "2026-01-01",
		"vehicle_count": 1,
		"battery_count": 2,
		"monthly_fee": 399,
		"churn_date": None,
		"churn_reason": None,
		"churn_note": None,
	}
	values.update(overrides)
	return ServiceSubscription(**values)


@unittest.skipIf(HAS_REAL_FRAPPE, "requires the no-Frappe fallback environment")
class TestServiceSubscriptionValidation(unittest.TestCase):
	def test_churn_requires_date_and_reason(self):
		with self.assertRaises(ValidationError):
			make_subscription(service_status="已流失").validate()

	def test_churn_date_cannot_precede_activation(self):
		with self.assertRaises(ValidationError):
			make_subscription(
				service_status="已流失", churn_date="2025-12-31", churn_reason="价格"
			).validate()

	def test_personal_subscription_has_one_vehicle(self):
		with self.assertRaises(ValidationError):
			make_subscription(vehicle_count=2).validate()

	def test_active_subscription_rejects_churn_fields(self):
		with self.assertRaises(ValidationError):
			make_subscription(churn_date="2026-02-01", churn_reason="迁移").validate()

	def test_other_churn_reason_requires_note(self):
		with self.assertRaises(ValidationError):
			make_subscription(
				service_status="已流失", churn_date="2026-02-01", churn_reason="其他"
			).validate()

	def test_blank_monthly_fee_is_allowed(self):
		make_subscription(monthly_fee=None).validate()

	def test_negative_monthly_fee_is_rejected(self):
		with self.assertRaises(ValidationError):
			make_subscription(monthly_fee=-1).validate()

	def test_valid_lifecycle_records_validate(self):
		valid_records = [
			{},
			{"service_status": "暂停"},
			{
				"service_status": "已流失",
				"churn_date": "2026-02-01",
				"churn_reason": "其他",
				"churn_note": "迁往外地",
			},
			{"customer_type": "企业", "vehicle_count": 2},
			{"monthly_fee": None},
			{"monthly_fee": 0},
		]
		for values in valid_records:
			with self.subTest(values=values):
				make_subscription(**values).validate()
