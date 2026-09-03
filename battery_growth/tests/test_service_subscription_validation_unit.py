"""Native test harness for Service Subscription validation when Bench is unavailable."""

import datetime
import importlib
import sys
import types
import unittest


class ValidationError(Exception):
	pass


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
	sys.modules.update(
		{
			"frappe": frappe,
			"frappe.utils": utils,
			"frappe.model": model,
			"frappe.model.document": document,
		}
	)


_install_frappe_stub()
ServiceSubscription = importlib.import_module(
	"battery_growth.battery_growth.doctype.service_subscription.service_subscription"
).ServiceSubscription


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
