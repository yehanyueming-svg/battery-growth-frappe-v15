"""Small, validated boundary for OpenAI-compatible Chat Completions providers."""

import json
from urllib.parse import urlsplit, urlunsplit

import requests


_MAX_RESPONSE_BYTES = 100_000
_ALLOWED_LEVELS = {"info", "warning", "critical"}
_SYSTEM_PROMPT = (
	"你是运营分析助手。只能依据提供的聚合指标生成结论，不能推断客户身份或引用未提供的数据。\n"
	"仅返回 JSON 对象："
	'{"summary":"一句话总结","insights":[{"level":"info|warning|critical","title":"标题",'
	'"evidence":"可由指标验证的证据","action":"建议动作"}]}。'
)


class InsightProviderError(Exception):
	"""A safe, non-sensitive provider failure suitable for local fallback."""


def _bounded_timeout(value) -> int:
	try:
		value = int(value)
	except (TypeError, ValueError):
		raise InsightProviderError("Invalid provider timeout") from None
	if not 1 <= value <= 120:
		raise InsightProviderError("Invalid provider timeout")
	return value


def validate_base_url(value) -> str:
	"""Validate an admin endpoint; local HTTP endpoints are intentionally supported.

	The provider may be a self-hosted model such as Ollama on a private network, so
	loopback and RFC1918 hosts are allowed by policy. Credentials, fragments, query
	parameters, and non-HTTP schemes are rejected to keep endpoint construction
	predictable and prevent accidental credential or URL-target injection.
	"""
	if not isinstance(value, str) or not value.strip():
		raise InsightProviderError("Invalid provider URL")
	try:
		parsed = urlsplit(value.strip())
		hostname = parsed.hostname
		_port = parsed.port
	except ValueError:
		raise InsightProviderError("Invalid provider URL") from None
	if (
		parsed.scheme not in {"http", "https"}
		or not hostname
		or parsed.username is not None
		or parsed.password is not None
		or parsed.fragment
		or parsed.query
	):
		raise InsightProviderError("Invalid provider URL")
	return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _string(value, fieldname: str, maximum: int) -> str:
	if not isinstance(value, str) or not value.strip() or len(value) > maximum:
		raise InsightProviderError(f"Invalid {fieldname}")
	return value.strip()


def _validate_payload(payload) -> dict:
	if not isinstance(payload, dict) or set(payload) != {"summary", "insights"}:
		raise InsightProviderError("Invalid provider schema")
	summary = _string(payload.get("summary"), "summary", 200)
	insights = payload.get("insights")
	if not isinstance(insights, list) or not 1 <= len(insights) <= 3:
		raise InsightProviderError("Invalid provider schema")
	validated = []
	for item in insights:
		if not isinstance(item, dict) or set(item) != {"level", "title", "evidence", "action"}:
			raise InsightProviderError("Invalid provider schema")
		if item.get("level") not in _ALLOWED_LEVELS:
			raise InsightProviderError("Invalid provider schema")
		validated.append({
			"level": item["level"],
			"title": _string(item.get("title"), "title", 120),
			"evidence": _string(item.get("evidence"), "evidence", 240),
			"action": _string(item.get("action"), "action", 240),
		})
	return {"summary": summary, "insights": validated}


def _read_response_body(response) -> bytes:
	content_length = response.headers.get("Content-Length")
	try:
		if content_length is not None and not 0 <= int(content_length) <= _MAX_RESPONSE_BYTES:
			raise InsightProviderError("Provider response too large")
	except ValueError:
		raise InsightProviderError("Invalid provider response") from None
	body = bytearray()
	try:
		for chunk in response.iter_content(chunk_size=8192):
			if not chunk:
				continue
			body.extend(chunk)
			if len(body) > _MAX_RESPONSE_BYTES:
				raise InsightProviderError("Provider response too large")
	except requests.RequestException:
		raise InsightProviderError("Provider response read failed") from None
	return bytes(body)


def _extract_content(response) -> dict:
	try:
		body = json.loads(_read_response_body(response).decode("utf-8"))
	except (UnicodeDecodeError, ValueError):
		raise InsightProviderError("Invalid provider response") from None
	if not isinstance(body, dict):
		raise InsightProviderError("Invalid provider response")
	try:
		content = body["choices"][0]["message"]["content"]
	except (KeyError, IndexError, TypeError):
		raise InsightProviderError("Invalid provider response") from None
	if isinstance(content, str):
		if len(content.encode("utf-8")) > _MAX_RESPONSE_BYTES:
			raise InsightProviderError("Provider response too large")
		try:
			content = json.loads(content)
		except ValueError:
			raise InsightProviderError("Invalid provider response") from None
	return _validate_payload(content)


def request_insights(context: dict, settings) -> dict:
	"""Request a validated brief without exposing upstream request or response data."""
	base_url = validate_base_url(getattr(settings, "base_url", None))
	model = _string(getattr(settings, "model", None), "model", 120)
	timeout_seconds = _bounded_timeout(getattr(settings, "timeout_seconds", None))
	api_key = settings.get_password("api_key", raise_exception=False)
	if not isinstance(api_key, str) or not api_key:
		raise InsightProviderError("Provider API key is not configured")
	response = None
	try:
		response = requests.post(
			f"{base_url}/chat/completions",
			headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
			json={
				"model": model,
				"temperature": 0.2,
				"messages": [
					{"role": "system", "content": _SYSTEM_PROMPT},
					{"role": "user", "content": json.dumps(context, ensure_ascii=False, separators=(",", ":"))},
				],
			},
			timeout=timeout_seconds,
			stream=True,
		)
		response.raise_for_status()
		return _extract_content(response)
	except InsightProviderError:
		raise
	except requests.RequestException:
		raise InsightProviderError("Provider request failed") from None
	finally:
		if response is not None:
			try:
				response.close()
			except Exception:
				pass
