import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ServiceSubscription(Document):
	def validate(self):
		self._validate_status_dates()
		self._validate_customer_scale()
		self._validate_non_negative_values()

	def _validate_status_dates(self):
		if self.service_status == "已流失":
			if not self.churn_date or not self.churn_reason:
				frappe.throw(_("已流失的订阅必须填写流失日期和流失原因"))
			if getdate(self.churn_date) < getdate(self.activation_date):
				frappe.throw(_("流失日期不能早于开通日期"))
			if self.churn_reason == "其他" and not self.churn_note:
				frappe.throw(_("流失原因为其他时必须填写流失说明"))
		elif self.churn_date or self.churn_reason or self.churn_note:
			frappe.throw(_("在服或暂停的订阅不能填写流失信息"))

	def _validate_customer_scale(self):
		if self.customer_type == "个人" and self.vehicle_count != 1:
			frappe.throw(_("个人客户的车辆数量必须为 1"))

	def _validate_non_negative_values(self):
		if self.vehicle_count < 1 or self.battery_count < 1:
			frappe.throw(_("车辆数量和电池数量必须大于 0"))
		if self.monthly_fee < 0:
			frappe.throw(_("月服务费不能小于 0"))
