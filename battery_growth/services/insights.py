"""Privacy-safe orchestration for optional AI operations briefs."""

import hashlib
import json
import math

import frappe
from frappe.utils import now_datetime

from battery_growth.analytics.metrics import get_growth_metrics
from battery_growth.analytics.rules import generate_rule_insights
from battery_growth.integrations.openai_compatible import InsightProviderError, request_insights


_FILTER_FIELDS = (
	"from_date", "to_date", "granularity", "customer_type", "province", "city", "service_plan", "acquisition_channel"
)
_SUMMARY_FIELDS = (
	"opening_active", "closing_active", "new_users", "churned_users", "net_growth", "churn_rate", "active_vehicles", "monthly_revenue"
)
_PERIOD_FIELDS = (
	"label", "opening_active", "closing_active", "new_users", "churned_users", "net_growth", "churn_rate", "new_vehicles", "new_monthly_fee"
)
_DISTRIBUTION_FIELDS = ("regions", "customer_types", "plans", "churn_reasons", "stations")


def _mapping(value) -> dict:
	return value if isinstance(value, dict) else {}


def _text(value) -> str | None:
	return value if isinstance(value, str) and len(value) <= 200 else None


def _number(value) -> int | float | None:
	if not isinstance(value, (int, float)) or isinstance(value, bool):
		return None
	return value if isinstance(value, int) or math.isfinite(value) else None


def _typed_values(source: dict, fields: tuple, validator) -> dict:
	values = {}
	for field in fields:
		value = validator(source.get(field))
		if value is not None:
			values[field] = value
	return values


def _distribution_entries(value) -> list:
	if not isinstance(value, list):
		return []
	entries = []
	for entry in value:
		if not isinstance(entry, dict):
			continue
		label = _text(entry.get("label"))
		count = _number(entry.get("value"))
		share = _number(entry.get("share"))
		if label is not None and count is not None and share is not None:
			entries.append({"label": label, "value": count, "share": share})
	return entries


def sanitize_metrics(metrics: dict) -> dict:
	"""Build a fresh, strict aggregate allowlist for an external provider context."""
	metrics = _mapping(metrics)
	distributions = _mapping(metrics.get("distributions"))
	periods = metrics.get("periods") if isinstance(metrics.get("periods"), list) else []
	clean_periods = []
	for period in periods:
		if not isinstance(period, dict):
			continue
		clean_period = _typed_values(period, _PERIOD_FIELDS[1:], _number)
		label = _text(period.get("label"))
		if label is not None:
			clean_periods.append({"label": label, **clean_period})
	return {
		"filters": _typed_values(_mapping(metrics.get("filters")), _FILTER_FIELDS, _text),
		"summary": _typed_values(_mapping(metrics.get("summary")), _SUMMARY_FIELDS, _number),
		"periods": clean_periods,
		"distributions": {
			field: _distribution_entries(distributions.get(field)) for field in _DISTRIBUTION_FIELDS
		},
	}


def _snapshot_signature(context: dict) -> str:
	canonical = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
	return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_minutes(settings) -> int:
	try:
		value = int(getattr(settings, "cache_minutes", 15))
	except (TypeError, ValueError):
		return 15
	return min(max(value, 1), 1440)


def _local_brief(metrics: dict, fallback: bool = False) -> dict:
	brief = generate_rule_insights(metrics)
	if fallback:
		brief["source"] = "rules-fallback"
	return brief


def get_operations_brief(filters=None, force: bool = False) -> dict:
	"""Return rules by default and safely fall back when the provider is unavailable."""
	metrics = get_growth_metrics(filters)
	settings = frappe.get_single("Growth AI Settings")
	if (
		not settings
		or not getattr(settings, "enabled", 0)
		or getattr(settings, "provider", "本地规则") != "OpenAI Compatible"
	):
		return _local_brief(metrics)

	context = sanitize_metrics(metrics)
	cache_key = f"battery_growth:insight:{_snapshot_signature(context)}"
	cache = frappe.cache()
	if not force:
		cached = cache.get_value(cache_key)
		if isinstance(cached, dict):
			return cached
	try:
		brief = request_insights(context, settings)
	except InsightProviderError as error:
		frappe.log_error(
			f"{error.__class__.__name__}: operations insight provider fallback", "Battery Growth Insight"
		)
		return _local_brief(metrics, fallback=True)
	brief["source"] = "openai-compatible"
	brief["generated_at"] = now_datetime().isoformat()
	cache.set_value(cache_key, brief, expires_in_sec=_cache_minutes(settings) * 60)
	return brief
