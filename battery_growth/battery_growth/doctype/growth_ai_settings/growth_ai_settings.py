"""Configuration guardrails for the optional AI provider."""

import frappe
from frappe import _
from frappe.model.document import Document

from battery_growth.integrations.openai_compatible import InsightProviderError, validate_base_url


class GrowthAISettings(Document):
	def validate(self):
		self._validate_integer("timeout_seconds", 1, 120, "超时秒数必须在 1 到 120 之间")
		self._validate_integer("cache_minutes", 1, 1440, "缓存分钟数必须在 1 到 1440 之间")
		if self.provider == "OpenAI Compatible":
			try:
				validate_base_url(self.base_url)
			except InsightProviderError:
				frappe.throw(_("Base URL 必须为不含凭据、查询参数或片段的 HTTP/HTTPS 地址"))

	def _validate_integer(self, fieldname: str, minimum: int, maximum: int, message: str):
		try:
			value = int(getattr(self, fieldname))
		except (TypeError, ValueError):
			frappe.throw(_(message))
		if not minimum <= value <= maximum:
			frappe.throw(_(message))
		setattr(self, fieldname, value)
