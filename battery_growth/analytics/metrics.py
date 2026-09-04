"""Permission-aware metrics shared by the report, dashboard, and insight services."""

from datetime import date, timedelta
from types import SimpleNamespace

import frappe
from frappe.utils import getdate

from battery_growth.analytics.filters import GrowthFilters, normalize_filters

_FIELDS = (
    "activation_date",
    "churn_date",
    "customer_type",
    "province",
    "city",
    "service_plan",
    "acquisition_channel",
    "swap_station",
    "churn_reason",
    "vehicle_count",
    "battery_count",
    "monthly_fee",
)
_EQUALITY_FILTERS = ("customer_type", "province", "city", "service_plan", "acquisition_channel")


def is_active_on(row, day):
    return getdate(row.activation_date) <= day and (not row.churn_date or getdate(row.churn_date) > day)


def churned_between(row, start, end):
    return bool(row.churn_date and start <= getdate(row.churn_date) <= end)


def _as_row(value):
    if isinstance(value, dict):
        return SimpleNamespace(**value)
    return value


def _number(value) -> float:
    return float(value or 0)


def _money(value) -> float:
    return round(_number(value), 2)


def _whole_number(value) -> int:
    return int(_number(value))


def _rate(churned_users: int, opening_active: int) -> float:
    return round((churned_users / opening_active * 100) if opening_active else 0.0, 2)


def _month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1) - timedelta(days=1)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _bucket_start(value: date, granularity: str) -> date:
    if granularity == "Month":
        return value.replace(day=1)
    return value - timedelta(days=value.weekday())


def _bucket_end(value: date, granularity: str) -> date:
    if granularity == "Month":
        return _month_end(value)
    return value + timedelta(days=6 - value.weekday())


def _label(value: date, granularity: str) -> str:
    if granularity == "Month":
        return value.strftime("%Y-%m")
    iso_year, iso_week, _weekday = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _periods(filters: GrowthFilters, rows: list) -> list[dict]:
    periods = []
    bucket_anchor = _bucket_start(filters.from_date, filters.granularity)
    while bucket_anchor <= filters.to_date:
        bucket_start = max(bucket_anchor, filters.from_date)
        bucket_end = min(_bucket_end(bucket_anchor, filters.granularity), filters.to_date)
        opening_active = sum(is_active_on(row, bucket_start - timedelta(days=1)) for row in rows)
        new_rows = [row for row in rows if bucket_start <= getdate(row.activation_date) <= bucket_end]
        churned_users = sum(churned_between(row, bucket_start, bucket_end) for row in rows)
        closing_active = sum(is_active_on(row, bucket_end) for row in rows)
        periods.append(
            {
                "label": _label(bucket_anchor, filters.granularity),
                "bucket_start": bucket_start.isoformat(),
                "bucket_end": bucket_end.isoformat(),
                "opening_active": opening_active,
                "new_users": len(new_rows),
                "churned_users": churned_users,
                "net_growth": len(new_rows) - churned_users,
                "closing_active": closing_active,
                "churn_rate": _rate(churned_users, opening_active),
                "new_vehicles": _whole_number(sum(_number(row.vehicle_count) for row in new_rows)),
                "new_monthly_fee": _money(sum(_number(row.monthly_fee) for row in new_rows)),
            }
        )
        bucket_anchor = _bucket_end(bucket_anchor, filters.granularity) + timedelta(days=1)
    return periods


def _distribution(rows: list, fieldname: str, limit: int | None = None) -> list[dict]:
    counts = {}
    for row in rows:
        label = getattr(row, fieldname) or "未填写"
        counts[label] = counts.get(label, 0) + 1
    total = sum(counts.values())
    entries = [
        {"label": label, "value": value, "share": round(value / total * 100, 2)}
        for label, value in counts.items()
    ]
    entries.sort(key=lambda entry: (-entry["value"], entry["label"]))
    return entries[:limit] if limit else entries


def _get_rows(filters: GrowthFilters) -> list:
    query_filters = {"activation_date": ["<=", filters.to_date.isoformat()]}
    for fieldname in _EQUALITY_FILTERS:
        value = getattr(filters, fieldname)
        if value:
            query_filters[fieldname] = value
    return [
        _as_row(row)
        for row in frappe.get_list(
            "Service Subscription", fields=list(_FIELDS), filters=query_filters, limit_page_length=0
        )
    ]


def _serialized_filters(filters: GrowthFilters) -> dict:
    return {
        "from_date": filters.from_date.isoformat(),
        "to_date": filters.to_date.isoformat(),
        "granularity": filters.granularity,
        "customer_type": filters.customer_type,
        "province": filters.province,
        "city": filters.city,
        "service_plan": filters.service_plan,
        "acquisition_channel": filters.acquisition_channel,
    }


def get_growth_metrics(filters=None) -> dict:
    """Calculate JSON-serializable aggregate metrics without reading personal data."""
    filters = normalize_filters(filters)
    rows = _get_rows(filters)
    periods = _periods(filters, rows)
    opening_active = sum(is_active_on(row, filters.from_date - timedelta(days=1)) for row in rows)
    closing_rows = [row for row in rows if is_active_on(row, filters.to_date)]
    new_rows = [row for row in rows if filters.from_date <= getdate(row.activation_date) <= filters.to_date]
    churned_rows = [row for row in rows if churned_between(row, filters.from_date, filters.to_date)]
    served_users = opening_active + len(new_rows)
    summary = {
        "opening_active": opening_active,
        "closing_active": len(closing_rows),
        "new_users": len(new_rows),
        "churned_users": len(churned_rows),
        "net_growth": len(new_rows) - len(churned_rows),
        # For a multi-period summary, include users activated during the range so
        # the cumulative rate remains interpretable and cannot exceed 100%.
        "churn_rate": _rate(len(churned_rows), served_users),
        "active_vehicles": _whole_number(sum(_number(row.vehicle_count) for row in closing_rows)),
        "monthly_revenue": _money(sum(_number(row.monthly_fee) for row in closing_rows)),
    }
    return {
        "filters": _serialized_filters(filters),
        "summary": summary,
        "periods": periods,
        "distributions": {
            "regions": _distribution(closing_rows, "province", limit=10),
            "customer_types": _distribution(closing_rows, "customer_type"),
            "plans": _distribution(closing_rows, "service_plan"),
            "churn_reasons": _distribution(churned_rows, "churn_reason"),
            "stations": _distribution(closing_rows, "swap_station", limit=10),
        },
    }
