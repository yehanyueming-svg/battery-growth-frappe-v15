"""Read-only assertions used by the reproducible deployment verification scripts."""

import frappe
from frappe.utils import cint

_ARTIFACTS = {
    "doctype": ("DocType", "Service Subscription"),
    "report": ("Report", "User Growth Analysis"),
    "page": ("Page", "battery-growth-dashboard"),
    "workspace": ("Workspace", "Battery Growth"),
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_deployment(expected_frappe_version: str = "15.120.0", expected_mock_count: int = 240) -> dict:
    """Validate the installed demo without changing data and return aggregate facts."""
    frappe_version = str(getattr(frappe, "__version__", "")).lstrip("v")
    expected_version = str(expected_frappe_version).lstrip("v")
    _require(
        frappe_version == expected_version,
        f"Frappe version mismatch: expected {expected_version}, found {frappe_version or 'unknown'}",
    )

    installed_apps = list(frappe.get_installed_apps())
    _require("battery_growth" in installed_apps, "battery_growth is not installed on this site")

    developer_mode = cint(getattr(frappe.conf, "developer_mode", 0))
    _require(developer_mode == 1, f"developer_mode mismatch: expected 1, found {developer_mode}")

    mock_count = frappe.db.count("Service Subscription", {"is_mock": 1})
    _require(
        mock_count == expected_mock_count,
        f"Mock subscription count mismatch: expected {expected_mock_count}, found {mock_count}",
    )

    customer_types = sorted(
        {
            str(value)
            for value in frappe.get_all("Service Subscription", filters={"is_mock": 1}, pluck="customer_type")
            if value
        }
    )
    expected_customer_types = ["个人", "企业"]
    _require(
        customer_types == expected_customer_types,
        f"Mock customer types mismatch: expected {expected_customer_types}, found {customer_types}",
    )

    artifacts = []
    for label, (doctype, name) in _ARTIFACTS.items():
        _require(frappe.db.exists(doctype, name), f"Required {doctype} is missing: {name}")
        artifacts.append(label)

    return {
        "frappe_version": frappe_version,
        "installed_app": "battery_growth",
        "developer_mode": developer_mode,
        "mock_count": mock_count,
        "customer_types": customer_types,
        "artifacts": artifacts,
    }
