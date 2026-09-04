"""Frappe Script Report presentation for shared growth metrics."""

import frappe

from battery_growth.analytics.metrics import get_growth_metrics

_ = frappe._


def get_columns():
    return [
        {"label": _("周期"), "fieldname": "period", "fieldtype": "Data", "width": 100},
        {"label": _("期初在服"), "fieldname": "opening_active", "fieldtype": "Int", "width": 100},
        {"label": _("新开通"), "fieldname": "new_users", "fieldtype": "Int", "width": 90},
        {"label": _("流失"), "fieldname": "churned_users", "fieldtype": "Int", "width": 80},
        {"label": _("净增长"), "fieldname": "net_growth", "fieldtype": "Int", "width": 90},
        {"label": _("期末在服"), "fieldname": "closing_active", "fieldtype": "Int", "width": 100},
        {"label": _("流失率"), "fieldname": "churn_rate", "fieldtype": "Percent", "width": 90},
        {"label": _("新增车辆"), "fieldname": "new_vehicles", "fieldtype": "Int", "width": 100},
        {"label": _("新增月服务费"), "fieldname": "new_monthly_fee", "fieldtype": "Currency", "width": 120},
    ]


def get_chart(data):
    return {
        "type": "axis-mixed",
        "data": {
            "labels": [row["period"] for row in data],
            "datasets": [
                {"name": _("新增用户"), "chartType": "bar", "values": [row["new_users"] for row in data]},
                {"name": _("流失用户"), "chartType": "bar", "values": [row["churned_users"] for row in data]},
                {
                    "name": _("期末在服"),
                    "chartType": "line",
                    "values": [row["closing_active"] for row in data],
                },
            ],
        },
    }


def get_summary(summary):
    return [
        {"label": _("期末在服"), "value": summary["closing_active"], "indicator": "Blue", "datatype": "Int"},
        {"label": _("累计新增"), "value": summary["new_users"], "indicator": "Green", "datatype": "Int"},
        {"label": _("累计流失"), "value": summary["churned_users"], "indicator": "Red", "datatype": "Int"},
        {
            "label": _("净增长"),
            "value": summary["net_growth"],
            "indicator": "Green" if summary["net_growth"] >= 0 else "Red",
            "datatype": "Int",
        },
        {"label": _("流失率"), "value": summary["churn_rate"], "indicator": "Orange", "datatype": "Percent"},
    ]


def execute(filters=None):
    """Map the canonical analytics response to native Script Report output."""
    metrics = get_growth_metrics(filters)
    data = [
        {
            "period": row["label"],
            "bucket_start": row["bucket_start"],
            "bucket_end": row["bucket_end"],
            "opening_active": row["opening_active"],
            "new_users": row["new_users"],
            "churned_users": row["churned_users"],
            "net_growth": row["net_growth"],
            "closing_active": row["closing_active"],
            "churn_rate": row["churn_rate"],
            "new_vehicles": row["new_vehicles"],
            "new_monthly_fee": row["new_monthly_fee"],
        }
        for row in metrics["periods"]
    ]
    return get_columns(), data, None, get_chart(data), get_summary(metrics["summary"])
