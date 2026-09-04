"""Permission-checked aggregate APIs consumed by the operations dashboard."""

from copy import deepcopy

import frappe
from frappe.utils import cint, now_datetime

from battery_growth.analytics.filters import normalize_filters
from battery_growth.analytics.metrics import get_growth_metrics
from battery_growth.services.insights import get_operations_brief


def _require_read_permission():
    """Require read access before parsing filters or invoking any service."""
    if not frappe.has_permission("Service Subscription", ptype="read"):
        raise frappe.PermissionError


def _normalize_api_filters(filters):
    """Use the shared parser while presenting validation feedback safely to API users."""
    try:
        return normalize_filters(filters)
    except ValueError as error:
        frappe.throw(str(error), exc=frappe.ValidationError)


@frappe.whitelist()
def get_dashboard_data(filters=None) -> dict:
    """Return a fresh, fixed aggregate dashboard shape without row-level data."""
    _require_read_permission()
    metrics = get_growth_metrics(_normalize_api_filters(filters))
    return {
        "filters": deepcopy(metrics.get("filters", {})),
        "summary": deepcopy(metrics.get("summary", {})),
        "periods": deepcopy(metrics.get("periods", [])),
        "distributions": deepcopy(metrics.get("distributions", {})),
        "generated_at": now_datetime().isoformat(),
    }


@frappe.whitelist(methods=["POST"])
def generate_operations_brief(filters=None, force=False) -> dict:
    """Generate an insight brief only after permission and filter validation succeed."""
    _require_read_permission()
    return get_operations_brief(_normalize_api_filters(filters), force=bool(cint(force)))
