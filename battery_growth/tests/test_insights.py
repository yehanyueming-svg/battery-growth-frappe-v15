"""Tests for privacy-safe operations insights and the OpenAI-compatible boundary."""

import datetime
import importlib
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch

import requests


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
	"battery_growth.battery_growth.doctype.growth_ai_settings.growth_ai_settings",
)


class _Cache:
	def __init__(self):
		self.values = {}
		self.calls = []

	def get_value(self, key):
		self.calls.append(("get", key))
		return self.values.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.calls.append(("set", key, expires_in_sec))
		self.values[key] = value


def _load_insights_without_frappe():
	"""Import production modules with only the narrow Frappe boundary stubbed."""
	cache = _Cache()
	frappe = types.ModuleType("frappe")
	frappe._ = lambda message: message
	frappe.cache = lambda: cache
	frappe.get_single = lambda _doctype: None
	frappe.log_error = lambda *_args, **_kwargs: None
	frappe.ValidationError = type("ValidationError", (Exception,), {})
	frappe.throw = lambda message: (_ for _ in ()).throw(frappe.ValidationError(message))
	utils = types.ModuleType("frappe.utils")
	utils.getdate = lambda value: (
		value if isinstance(value, datetime.date) else datetime.date.fromisoformat(str(value))
	)
	utils.today = lambda: "2026-09-03"
	utils.now_datetime = lambda: datetime.datetime(2026, 9, 3, 10, 30, 0)
	document = types.ModuleType("frappe.model.document")
	document.Document = type("Document", (), {})
	stub_modules = {
		"frappe": frappe,
		"frappe.utils": utils,
		"frappe.model": types.ModuleType("frappe.model"),
		"frappe.model.document": document,
	}
	missing = object()
	original_modules = {
		name: sys.modules.get(name, missing) for name in (*stub_modules, *_STUB_BOUND_MODULES)
	}
	try:
		sys.modules.update(stub_modules)
		modules = {
			"rules": importlib.import_module("battery_growth.analytics.rules"),
			"provider": importlib.import_module("battery_growth.integrations.openai_compatible"),
			"insights": importlib.import_module("battery_growth.services.insights"),
			"settings": importlib.import_module(
				"battery_growth.battery_growth.doctype.growth_ai_settings.growth_ai_settings"
			),
		}
		return modules, cache
	finally:
		for name in _STUB_BOUND_MODULES:
			original_module = original_modules[name]
			if original_module is missing:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original_module
		for name in stub_modules:
			original_module = original_modules[name]
			if original_module is missing:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = original_module


if _frappe is None:
	modules, _test_cache = _load_insights_without_frappe()
	rules = modules["rules"]
	provider = modules["provider"]
	insights = modules["insights"]
	settings_controller = modules["settings"]
else:
	from battery_growth.analytics import rules
	from battery_growth.integrations import openai_compatible as provider
	from battery_growth.services import insights
	from battery_growth.battery_growth.doctype.growth_ai_settings import growth_ai_settings as settings_controller


def metrics(**summary_overrides):
	summary = {
		"opening_active": 100,
		"closing_active": 104,
		"new_users": 15,
		"churned_users": 4,
		"net_growth": 11,
		"churn_rate": 4.0,
		"active_vehicles": 130,
		"monthly_revenue": 52000.0,
	}
	summary.update(summary_overrides)
	return {
		"filters": {"from_date": "2026-08-01", "to_date": "2026-08-31", "granularity": "Month", "customer_type": "企业"},
		"summary": summary,
		"periods": [{"label": "2026-08", "opening_active": 100, "closing_active": 104, "new_users": 15, "churned_users": 4, "net_growth": 11, "churn_rate": 4.0, "new_vehicles": 24, "new_monthly_fee": 9800.0}],
		"distributions": {
			"regions": [{"label": "浙江省", "value": 70, "share": 67.31}, {"label": "上海市", "value": 34, "share": 32.69}],
			"customer_types": [{"label": "企业", "value": 104, "share": 100.0}],
			"plans": [{"label": "企业车队", "value": 104, "share": 100.0}],
			"churn_reasons": [{"label": "价格", "value": 4, "share": 100.0}],
			"stations": [{"label": "杭州站", "value": 60, "share": 57.69}],
		},
		"customer_code": "MUST-NOT-PASS",
		"raw_records": [{"customer_name": "MUST-NOT-PASS", "mobile": "13800000000"}],
	}


class _Settings:
	def __init__(self, **values):
		self.enabled = values.get("enabled", 1)
		self.provider = values.get("provider", "本地规则")
		self.base_url = values.get("base_url", "https://provider.example/v1")
		self.model = values.get("model", "test-model")
		self.timeout_seconds = values.get("timeout_seconds", 15)
		self.cache_minutes = values.get("cache_minutes", 15)
		self._api_key = values.get("api_key", "test-key")

	def get_password(self, fieldname, raise_exception=False):
		self.last_password_request = (fieldname, raise_exception)
		return self._api_key


class _Response:
	def __init__(self, payload, status_code=200):
		self._payload = payload
		self.status_code = status_code
		self.headers = {"Content-Length": str(len(json.dumps(payload)))}
		self.content = json.dumps(payload).encode()
		self.closed = False

	def raise_for_status(self):
		if self.status_code >= 400:
			raise requests.HTTPError("provider failed")

	def json(self):
		return self._payload

	def iter_content(self, chunk_size=8192):
		for start in range(0, len(self.content), chunk_size):
			yield self.content[start:start + chunk_size]

	def close(self):
		self.closed = True


class TestRulesAndSanitization(FrappeTestCase):
	def test_high_churn_generates_warning(self):
		result = rules.generate_rule_insights(metrics(churn_rate=12.5, net_growth=-4))
		self.assertTrue(any(item["level"] == "warning" and "流失" in item["title"] for item in result["insights"]))

	def test_positive_net_growth_generates_info(self):
		result = rules.generate_rule_insights(metrics(net_growth=27, churn_rate=1.0))
		self.assertTrue(any(item["level"] == "info" and "净增长" in item["title"] for item in result["insights"]))

	def test_region_concentration_over_half_generates_warning(self):
		result = rules.generate_rule_insights(metrics(net_growth=0, churn_rate=1.0))
		self.assertTrue(any("区域" in item["title"] and item["level"] == "warning" for item in result["insights"]))

	def test_rules_are_severity_sorted_capped_and_neutral_when_no_threshold_fires(self):
		busy = rules.generate_rule_insights(metrics(churn_rate=20.0, net_growth=-20))
		self.assertLessEqual(len(busy["insights"]), 3)
		self.assertEqual(busy["insights"], sorted(busy["insights"], key=lambda item: {"critical": 0, "warning": 1, "info": 2}[item["level"]]))
		neutral_metrics = metrics(net_growth=0, churn_rate=1.0)
		neutral_metrics["distributions"]["regions"] = [{"label": "浙江省", "value": 50, "share": 50.0}, {"label": "上海市", "value": 50, "share": 50.0}]
		neutral = rules.generate_rule_insights(neutral_metrics)
		self.assertEqual(neutral["insights"], [{"level": "info", "title": "运营整体平稳", "evidence": "当前未发现需要优先处理的聚合指标异常", "action": "保持日常监测并按周期复盘"}])

	def test_sanitizer_is_a_strict_nested_allowlist(self):
		payload = metrics()
		payload["filters"]["customer_name"] = "MUST-NOT-PASS"
		payload["summary"]["mobile"] = "MUST-NOT-PASS"
		payload["summary"]["net_growth"] = {"customer_name": "MUST-NOT-PASS"}
		payload["periods"][0]["contact_person"] = "MUST-NOT-PASS"
		payload["distributions"]["regions"][0]["customer_code"] = "MUST-NOT-PASS"
		payload["distributions"]["regions"][0]["label"] = {"mobile": "MUST-NOT-PASS"}
		sanitized = insights.sanitize_metrics(payload)
		serialized = json.dumps(sanitized, ensure_ascii=False)
		for forbidden in ("customer_code", "customer_name", "mobile", "contact_person", "raw_records", "MUST-NOT-PASS"):
			with self.subTest(forbidden=forbidden):
				self.assertNotIn(forbidden, serialized)
		self.assertEqual(set(sanitized), {"filters", "summary", "periods", "distributions"})
		self.assertEqual(set(sanitized["periods"][0]), {"label", "opening_active", "closing_active", "new_users", "churned_users", "net_growth", "churn_rate", "new_vehicles", "new_monthly_fee"})
		self.assertEqual(set(sanitized["distributions"]["regions"][0]), {"label", "value", "share"})

	def test_sanitizer_supports_personal_metrics_and_rejects_nonfinite_values(self):
		payload = metrics()
		payload["filters"]["customer_type"] = "个人"
		payload["distributions"]["customer_types"] = [{"label": "个人", "value": 1, "share": float("nan")}]
		payload["summary"]["net_growth"] = float("inf")
		sanitized = insights.sanitize_metrics(payload)
		self.assertEqual(sanitized["filters"]["customer_type"], "个人")
		self.assertEqual(sanitized["distributions"]["customer_types"], [])
		self.assertNotIn("net_growth", sanitized["summary"])


class TestOpenAICompatibleProvider(FrappeTestCase):
	def test_valid_structured_json_is_parsed_with_bounded_request(self):
		response = _Response({"choices": [{"message": {"content": json.dumps({"summary": "企业客户稳定增长", "insights": [{"level": "info", "title": "增长稳定", "evidence": "净增长 11 户", "action": "保持企业合作节奏"}]})}}]})
		with patch("battery_growth.integrations.openai_compatible.requests.post", return_value=response) as post:
			result = provider.request_insights(insights.sanitize_metrics(metrics()), _Settings())
		self.assertEqual(result["summary"], "企业客户稳定增长")
		self.assertEqual(result["insights"][0]["level"], "info")
		url = post.call_args.kwargs.get("url", post.call_args.args[0])
		self.assertEqual(url, "https://provider.example/v1/chat/completions")
		self.assertEqual(post.call_args.kwargs["timeout"], 15)
		self.assertTrue(post.call_args.kwargs["stream"])
		self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer test-key", "Content-Type": "application/json"})

	def test_invalid_json_raises_sanitized_provider_error(self):
		response = _Response({"choices": [{"message": {"content": "not-json"}}]})
		with patch("battery_growth.integrations.openai_compatible.requests.post", return_value=response):
			with self.assertRaises(provider.InsightProviderError) as captured:
				provider.request_insights(insights.sanitize_metrics(metrics()), _Settings(api_key="super-secret"))
		self.assertNotIn("super-secret", str(captured.exception))
		self.assertNotIn("not-json", str(captured.exception))

	def test_huge_integer_json_in_either_parse_layer_falls_back_to_rules(self):
		huge_integer = "1" * 5_000
		for layer in ("outer", "content"):
			with self.subTest(layer=layer):
				if layer == "outer":
					response = _Response({})
					response.content = f'{{"value":{huge_integer}}}'.encode()
				else:
					response = _Response({"choices": [{"message": {"content": huge_integer}}]})
				response.headers = {"Content-Length": str(len(response.content))}
				with patch("battery_growth.integrations.openai_compatible.requests.post", return_value=response):
					with self.assertRaises(provider.InsightProviderError):
						provider.request_insights(insights.sanitize_metrics(metrics()), _Settings())

	def test_provider_rejects_unsafe_urls_and_oversized_response(self):
		for base_url in ("ftp://provider.example", "https://user:pass@provider.example", "https://provider.example/#fragment"):
			with self.subTest(base_url=base_url), self.assertRaises(provider.InsightProviderError):
				provider.request_insights(insights.sanitize_metrics(metrics()), _Settings(base_url=base_url))
		overse = _Response({"choices": [{"message": {"content": "x" * 100_001}}]})
		with patch("battery_growth.integrations.openai_compatible.requests.post", return_value=overse):
			with self.assertRaises(provider.InsightProviderError):
				provider.request_insights(insights.sanitize_metrics(metrics()), _Settings())

	def test_provider_rejects_oversized_chunked_response_without_content_length(self):
		valid_payload = {"choices": [{"message": {"content": {"summary": "增长稳定", "insights": [{"level": "info", "title": "保持节奏", "evidence": "净增长 11 户", "action": "持续跟进"}]}}}]}
		response = _Response(valid_payload)
		response.headers = {}
		response.content = b"x" * 100_001
		with patch("battery_growth.integrations.openai_compatible.requests.post", return_value=response):
			with self.assertRaises(provider.InsightProviderError):
				provider.request_insights(insights.sanitize_metrics(metrics()), _Settings())

	def test_provider_rejects_oversized_body_when_server_lies_about_content_length(self):
		response = _Response({"choices": [{"message": {"content": {"summary": "增长稳定", "insights": [{"level": "info", "title": "保持节奏", "evidence": "净增长 11 户", "action": "持续跟进"}]}}}]})
		response.headers = {"Content-Length": "1"}
		response.content = b"x" * 100_001
		with patch("battery_growth.integrations.openai_compatible.requests.post", return_value=response):
			with self.assertRaises(provider.InsightProviderError):
				provider.request_insights(insights.sanitize_metrics(metrics()), _Settings())

	def test_malformed_ipv6_url_is_a_safe_provider_error(self):
		with self.assertRaises(provider.InsightProviderError):
			provider.request_insights(insights.sanitize_metrics(metrics()), _Settings(base_url="https://[invalid"))

	def test_http_error_response_is_closed_even_when_close_raises(self):
		response = _Response({}, status_code=500)
		response.close = Mock(side_effect=RuntimeError("do not expose body"))
		with patch("battery_growth.integrations.openai_compatible.requests.post", return_value=response):
			with self.assertRaises(provider.InsightProviderError) as captured:
				provider.request_insights(insights.sanitize_metrics(metrics()), _Settings(api_key="secret-key"))
		self.assertNotIn("secret-key", str(captured.exception))
		self.assertNotIn("do not expose body", str(captured.exception))
		response.close.assert_called_once_with()


class TestOperationsBrief(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.original_get_metrics = insights.get_growth_metrics
		self.original_get_single = insights.frappe.get_single
		self.original_cache = insights.frappe.cache
		self.original_log_error = insights.frappe.log_error
		self.cache = _Cache()
		self.logs = []
		insights.get_growth_metrics = lambda _filters: metrics()
		insights.frappe.cache = lambda: self.cache
		insights.frappe.log_error = lambda message, title=None: self.logs.append((message, title))

	def tearDown(self):
		insights.get_growth_metrics = self.original_get_metrics
		insights.frappe.get_single = self.original_get_single
		insights.frappe.cache = self.original_cache
		insights.frappe.log_error = self.original_log_error
		super().tearDown()

	def test_disabled_and_local_mode_use_rules_without_a_provider_request(self):
		for settings in (_Settings(enabled=0, provider="OpenAI Compatible"), _Settings(provider="本地规则")):
			with self.subTest(settings=settings.provider):
				insights.frappe.get_single = lambda _doctype: settings
				with patch("battery_growth.integrations.openai_compatible.requests.post") as post:
					result = insights.get_operations_brief({"customer_type": "企业"})
				self.assertEqual(result["source"], "rules")
				post.assert_not_called()

	@patch("battery_growth.integrations.openai_compatible.requests.post")
	def test_timeout_falls_back_to_rules_without_secret_or_payload_logging(self, post):
		post.side_effect = requests.Timeout()
		insights.frappe.get_single = lambda _doctype: _Settings(provider="OpenAI Compatible", api_key="secret-key")
		result = insights.get_operations_brief({"customer_type": "企业"}, force=True)
		self.assertEqual(result["source"], "rules-fallback")
		self.assertGreater(len(result["insights"]), 0)
		self.assertTrue(self.logs)
		self.assertNotIn("secret-key", json.dumps(self.logs, ensure_ascii=False))
		self.assertNotIn("MUST-NOT-PASS", json.dumps(self.logs, ensure_ascii=False))

	@patch("battery_growth.integrations.openai_compatible.requests.post")
	def test_invalid_provider_json_falls_back_to_rules(self, post):
		post.return_value = _Response({"choices": [{"message": {"content": "not-json"}}]})
		insights.frappe.get_single = lambda _doctype: _Settings(provider="OpenAI Compatible")
		result = insights.get_operations_brief({"customer_type": "企业"}, force=True)
		self.assertEqual(result["source"], "rules-fallback")
		self.assertGreater(len(result["insights"]), 0)

	@patch("battery_growth.integrations.openai_compatible.requests.post")
	def test_huge_integer_provider_json_falls_back_to_rules(self, post):
		response = _Response({})
		response.content = f'{{"value":{"1" * 5_000}}}'.encode()
		response.headers = {"Content-Length": str(len(response.content))}
		post.return_value = response
		insights.frappe.get_single = lambda _doctype: _Settings(provider="OpenAI Compatible")
		result = insights.get_operations_brief({"customer_type": "企业"}, force=True)
		self.assertEqual(result["source"], "rules-fallback")

	@patch("battery_growth.integrations.openai_compatible.requests.post")
	def test_openai_mode_caches_canonical_sanitized_snapshot_and_force_bypasses_it(self, post):
		post.return_value = _Response({"choices": [{"message": {"content": {"summary": "增长稳定", "insights": [{"level": "info", "title": "保持节奏", "evidence": "净增长 11 户", "action": "持续跟进"}]}}}]})
		insights.frappe.get_single = lambda _doctype: _Settings(provider="OpenAI Compatible", cache_minutes=2)
		first = insights.get_operations_brief({"customer_type": "企业"})
		second = insights.get_operations_brief({"customer_type": "企业"})
		forced = insights.get_operations_brief({"customer_type": "企业"}, force=True)
		self.assertEqual((first["source"], second["source"], forced["source"]), ("openai-compatible", "openai-compatible", "openai-compatible"))
		self.assertEqual(post.call_count, 2)
		set_calls = [call for call in self.cache.calls if call[0] == "set"]
		self.assertTrue(set_calls[0][1].startswith("battery_growth:insight:"))
		self.assertEqual(set_calls[0][2], 120)


class TestSettingsValidation(FrappeTestCase):
	def test_settings_bound_timeout_cache_and_provider_url(self):
		settings = settings_controller.GrowthAISettings()
		for timeout, cache_minutes in ((0, 15), (121, 15), (15, 0), (15, 1441)):
			settings.timeout_seconds = timeout
			settings.cache_minutes = cache_minutes
			settings.provider = "本地规则"
			with self.subTest(timeout=timeout, cache_minutes=cache_minutes), self.assertRaises(
				settings_controller.frappe.ValidationError
			):
				settings.validate()
		settings.timeout_seconds = 15
		settings.cache_minutes = 15
		settings.provider = "OpenAI Compatible"
		for base_url in ("http://127.0.0.1:11434/v1", "https://provider.example/v1"):
			settings.base_url = base_url
			settings.validate()
		for base_url in ("ftp://provider.example", "https://user@provider.example", "https://provider.example/#x"):
			settings.base_url = base_url
			with self.subTest(base_url=base_url), self.assertRaises(settings_controller.frappe.ValidationError):
				settings.validate()


class TestNoFrappeIsolation(FrappeTestCase):
	@unittest.skipIf(_frappe is not None, "Only the no-Frappe fallback creates temporary modules.")
	def test_no_frappe_loader_does_not_cache_stub_bound_modules(self):
		missing = object()
		original_modules = {name: sys.modules.pop(name, missing) for name in _STUB_BOUND_MODULES}
		try:
			_load_insights_without_frappe()
			self.assertEqual({name for name in _STUB_BOUND_MODULES if name in sys.modules}, set())
		finally:
			for name in _STUB_BOUND_MODULES:
				sys.modules.pop(name, None)
			for name, original_module in original_modules.items():
				if original_module is not missing:
					sys.modules[name] = original_module
