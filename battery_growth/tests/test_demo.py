import frappe
from frappe.tests.utils import FrappeTestCase

from battery_growth.setup.demo import seed_demo_data


class TestDemoData(FrappeTestCase):
	def tearDown(self):
		frappe.db.delete("Service Subscription", {"is_mock": 1})
		frappe.db.commit()

	def test_seed_is_idempotent(self):
		first = seed_demo_data(rebuild=True, count=24)
		second = seed_demo_data(count=24)
		self.assertEqual(first["created"], 24)
		self.assertEqual(second["created"], 0)
		self.assertEqual(frappe.db.count("Service Subscription", {"is_mock": 1}), 24)

	def test_seed_contains_both_customer_types_and_churn(self):
		seed_demo_data(rebuild=True, count=24)
		self.assertGreater(frappe.db.count("Service Subscription", {"is_mock": 1, "customer_type": "个人"}), 0)
		self.assertGreater(frappe.db.count("Service Subscription", {"is_mock": 1, "customer_type": "企业"}), 0)
		self.assertGreater(frappe.db.count("Service Subscription", {"is_mock": 1, "service_status": "已流失"}), 0)

	def test_seed_rejects_out_of_range_counts(self):
		with self.assertRaises(frappe.ValidationError):
			seed_demo_data(count=0)
		with self.assertRaises(frappe.ValidationError):
			seed_demo_data(count=1001)

	def test_rebuild_preserves_non_mock_data(self):
		doc = frappe.get_doc(
			{
				"doctype": "Service Subscription",
				"customer_code": "REAL-001",
				"customer_name": "真实客户",
				"customer_type": "个人",
				"service_plan": "畅换",
				"service_status": "在服",
				"activation_date": "2026-01-01",
				"province": "浙江省",
				"city": "杭州市",
				"vehicle_count": 1,
				"battery_count": 2,
				"monthly_fee": 399,
			}
		).insert(ignore_permissions=True)
		seed_demo_data(rebuild=True, count=24)
		self.assertTrue(frappe.db.exists("Service Subscription", doc.name))
