"""Deterministic, aggregate-only rules for the operations brief."""

from frappe.utils import now_datetime


_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _number(value) -> float:
	return float(value or 0)


def _insight(level: str, title: str, evidence: str, action: str) -> dict:
	return {"level": level, "title": title, "evidence": evidence, "action": action}


def generate_rule_insights(metrics: dict) -> dict:
	"""Derive no more than three reproducible insights from aggregate metrics."""
	summary = metrics.get("summary") or {}
	distributions = metrics.get("distributions") or {}
	net_growth = _number(summary.get("net_growth"))
	churn_rate = _number(summary.get("churn_rate"))
	insights = []

	if churn_rate >= 15:
		insights.append(_insight("critical", "流失率需要立即关注", f"本期流失率为 {churn_rate:g}%", "优先核查高流失区域和套餐"))
	elif churn_rate >= 8:
		insights.append(_insight("warning", "流失率偏高", f"本期流失率为 {churn_rate:g}%", "复盘流失原因并安排客户回访"))

	if net_growth < 0:
		insights.append(_insight("warning", "净增长为负", f"本期净增长 {net_growth:g} 户", "提高获客转化并减少可避免流失"))
	elif net_growth >= 10:
		insights.append(_insight("info", "净增长保持为正", f"净增长 {net_growth:g} 户", "保持当前获客节奏"))

	regions = distributions.get("regions") or []
	leading_region = regions[0] if regions else {}
	leading_share = _number(leading_region.get("share")) if isinstance(leading_region, dict) else 0
	if leading_share > 50:
		region = leading_region.get("label") or "单一区域"
		insights.append(_insight("warning", "区域集中度偏高", f"{region} 占在服用户 {leading_share:g}%", "评估其他重点区域的拓展机会"))

	insights.sort(key=lambda item: (_SEVERITY_ORDER[item["level"]], item["title"]))
	if not insights:
		insights = [_insight("info", "运营整体平稳", "当前未发现需要优先处理的聚合指标异常", "保持日常监测并按周期复盘")]

	summary_text = "本期运营整体平稳"
	if insights[0]["level"] == "critical":
		summary_text = "本期存在需立即处理的运营风险"
	elif insights[0]["level"] == "warning":
		summary_text = "本期存在需要关注的运营信号"
	elif net_growth >= 10:
		summary_text = "本期增长态势积极"
	return {
		"source": "rules",
		"generated_at": now_datetime().isoformat(),
		"summary": summary_text,
		"insights": insights[:3],
	}
