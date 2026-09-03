import frappe
from frappe.tests.utils import FrappeTestCase


def make_subscription(**overrides):
	values = {
		"doctype": "Service Subscription",
		"customer_code": "RIDER-TEST-001",
		"customer_name": "测试骑手",
		"customer_type": "个人",
		"service_plan": "畅换",
		"service_status": "在服",
		"activation_date": "2026-01-01",
		"acquisition_channel": "直营网点",
		"province": "浙江省",
		"city": "杭州市",
		"vehicle_count": 1,
		"battery_count": 2,
		"monthly_fee": 399,
	}
	values.update(overrides)
	return frappe.get_doc(values)


class TestServiceSubscription(FrappeTestCase):
	def test_churn_requires_date_and_reason(self):
		with self.assertRaises(frappe.ValidationError):
			make_subscription(service_status="已流失").insert()

	def test_churn_date_cannot_precede_activation(self):
		with self.assertRaises(frappe.ValidationError):
			make_subscription(
				service_status="已流失", churn_date="2025-12-31", churn_reason="价格"
			).insert()

	def test_personal_subscription_has_one_vehicle(self):
		with self.assertRaises(frappe.ValidationError):
			make_subscription(vehicle_count=2).insert()

	def test_active_subscription_rejects_churn_fields(self):
		with self.assertRaises(frappe.ValidationError):
			make_subscription(churn_date="2026-02-01", churn_reason="迁移").insert()

	def test_other_churn_reason_requires_note(self):
		with self.assertRaises(frappe.ValidationError):
			make_subscription(
				service_status="已流失", churn_date="2026-02-01", churn_reason="其他"
			).insert()

	def test_blank_monthly_fee_is_allowed(self):
		make_subscription(monthly_fee=None).insert()

	def test_negative_monthly_fee_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_subscription(monthly_fee=-1).insert()

	def test_valid_lifecycle_records_insert(self):
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
				make_subscription(**values).insert()
