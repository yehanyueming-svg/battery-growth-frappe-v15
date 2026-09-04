"""Filter normalization for shared growth analytics."""

import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

from frappe import _
from frappe.utils import getdate, today

Granularity = Literal["Week", "Month"]
CustomerType = Literal["个人", "企业"]


@dataclass(frozen=True)
class GrowthFilters:
    from_date: date
    to_date: date
    granularity: Granularity = "Month"
    customer_type: CustomerType | None = None
    province: str | None = None
    city: str | None = None
    service_plan: str | None = None
    acquisition_channel: str | None = None


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    month_ends = (
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    )
    return date(year, month, min(value.day, month_ends[month - 1]))


def _default_from_date() -> date:
    current = getdate(today())
    return _add_months(current.replace(day=1), -11)


def _parse_date(value, fieldname: str, default: date) -> date:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        raise ValueError(_(f"{fieldname} 必须是有效日期"))
    try:
        return getdate(value)
    except (TypeError, ValueError):
        raise ValueError(_(f"{fieldname} 必须是有效日期")) from None


def _optional_text(raw: dict, fieldname: str) -> str | None:
    value = raw.get(fieldname)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(_(f"{fieldname} 必须是文本"))
    return value


def _parse_raw(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(_("筛选条件必须是有效 JSON")) from None
    if not isinstance(raw, dict):
        raise ValueError(_("筛选条件必须是对象"))
    return raw


def _typed_filter_values(value: GrowthFilters) -> dict:
    """Keep typed dates and literals intact while routing through shared validation."""
    return {
        "from_date": value.from_date,
        "to_date": value.to_date,
        "granularity": value.granularity,
        "customer_type": value.customer_type,
        "province": value.province,
        "city": value.city,
        "service_plan": value.service_plan,
        "acquisition_channel": value.acquisition_channel,
    }


def normalize_filters(raw=None) -> GrowthFilters:
    """Return a validated, immutable query filter value object."""
    if isinstance(raw, GrowthFilters):
        raw = _typed_filter_values(raw)
    raw = _parse_raw(raw)
    from_date = _parse_date(raw.get("from_date"), "from_date", _default_from_date())
    to_date = _parse_date(raw.get("to_date"), "to_date", getdate(today()))
    if from_date > to_date:
        raise ValueError(_("开始日期不能晚于结束日期"))
    if to_date >= _add_months(from_date, 36):
        raise ValueError(_("查询范围不能超过 36 个月"))

    granularity = raw.get("granularity") or "Month"
    if granularity not in ("Week", "Month"):
        raise ValueError(_("粒度只能是 Week 或 Month"))
    customer_type = _optional_text(raw, "customer_type")
    if customer_type not in (None, "个人", "企业"):
        raise ValueError(_("客户类型只能是个人或企业"))

    return GrowthFilters(
        from_date=from_date,
        to_date=to_date,
        granularity=granularity,
        customer_type=customer_type,
        province=_optional_text(raw, "province"),
        city=_optional_text(raw, "city"),
        service_plan=_optional_text(raw, "service_plan"),
        acquisition_channel=_optional_text(raw, "acquisition_channel"),
    )
