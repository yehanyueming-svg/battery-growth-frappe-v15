"""Tests for the shared, permission-aware growth analytics service."""

import datetime
import importlib
import json
import sys
import types
import unittest

try:
    import frappe as _frappe
    from frappe.tests.utils import FrappeTestCase
except ModuleNotFoundError as error:
    if error.name != "frappe":
        raise
    _frappe = None
    FrappeTestCase = unittest.TestCase


def _load_analytics_without_frappe():
    """Load production code against a minimal, temporary Frappe boundary."""
    frappe = types.ModuleType("frappe")
    frappe._ = lambda message: message
    frappe.get_list = lambda *args, **kwargs: []
    utils = types.ModuleType("frappe.utils")
    utils.getdate = lambda value: (
        value if isinstance(value, datetime.date) else datetime.date.fromisoformat(str(value))
    )
    utils.today = lambda: "2026-09-03"
    frappe.utils = utils
    stub_modules = {"frappe": frappe, "frappe.utils": utils}
    missing = object()
    original_modules = {name: sys.modules.get(name, missing) for name in stub_modules}
    try:
        sys.modules.update(stub_modules)
        filters = importlib.import_module("battery_growth.analytics.filters")
        metrics = importlib.import_module("battery_growth.analytics.metrics")
        return filters, metrics
    finally:
        for name, original_module in original_modules.items():
            if original_module is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original_module


if _frappe is None:
    filters, metrics = _load_analytics_without_frappe()
else:
    from battery_growth.analytics import filters, metrics


def subscription(**overrides):
    row = {
        "activation_date": "2025-12-01",
        "churn_date": None,
        "customer_type": "个人",
        "province": "浙江省",
        "city": "杭州市",
        "service_plan": "畅换",
        "acquisition_channel": "直营网点",
        "swap_station": "杭州市城北换电站",
        "churn_reason": None,
        "vehicle_count": 1,
        "battery_count": 2,
        "monthly_fee": 399,
    }
    row.update(overrides)
    return row


class TestGrowthMetrics(FrappeTestCase):
    def setUp(self):
        super().setUp()
        self.rows = [
            subscription(),
            subscription(
                activation_date="2026-01-10",
                customer_type="企业",
                province="上海市",
                city="上海市",
                service_plan="企业车队",
                acquisition_channel="企业合作",
                swap_station="上海市嘉定换电站",
                vehicle_count=4,
                battery_count=12,
                monthly_fee=2400,
            ),
            subscription(
                activation_date="2025-12-15",
                churn_date="2026-01-20",
                churn_reason="价格",
                service_plan="基础换电",
                swap_station="杭州市滨江换电站",
                monthly_fee=299,
            ),
        ]
        self.calls = []
        self.original_get_list = metrics.frappe.get_list
        metrics.frappe.get_list = self.fake_get_list

    def tearDown(self):
        metrics.frappe.get_list = self.original_get_list
        super().tearDown()

    def fake_get_list(self, doctype, fields, filters, **kwargs):
        self.calls.append({"doctype": doctype, "fields": fields, "filters": filters, **kwargs})
        return [
            row.copy()
            for row in self.rows
            if all(
                (key == "activation_date" and value[0] == "<=" and row[key] <= value[1])
                or (key != "activation_date" and row.get(key) == value)
                for key, value in filters.items()
            )
        ]

    def get_metrics(self, **overrides):
        values = {"from_date": "2026-01-01", "to_date": "2026-01-31", "granularity": "Month"}
        values.update(overrides)
        return metrics.get_growth_metrics(values)

    def test_monthly_lifecycle_metrics_and_projection(self):
        period = self.get_metrics()["periods"][0]
        self.assertEqual(period["opening_active"], 2)
        self.assertEqual(period["new_users"], 1)
        self.assertEqual(period["churned_users"], 1)
        self.assertEqual(period["net_growth"], 0)
        self.assertEqual(period["closing_active"], 2)
        self.assertEqual(period["churn_rate"], 50.0)
        self.assertEqual(self.calls[0]["doctype"], "Service Subscription")
        self.assertEqual(self.calls[0]["limit_page_length"], 0)
        self.assertEqual(
            self.calls[0]["fields"],
            [
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
            ],
        )
        self.assertEqual(self.calls[0]["filters"], {"activation_date": ["<=", "2026-01-31"]})

    def test_summary_counts_closing_scale_and_revenue(self):
        result = self.get_metrics()
        summary = result["summary"]
        self.assertEqual(
            summary,
            {
                "opening_active": 2,
                "closing_active": 2,
                "new_users": 1,
                "churned_users": 1,
                "net_growth": 0,
                "churn_rate": 50.0,
                "active_vehicles": 5,
                "monthly_revenue": 2799.0,
            },
        )
        self.assertIsInstance(summary["active_vehicles"], int)
        self.assertEqual(result["periods"][0]["new_vehicles"], 4)
        self.assertIsInstance(result["periods"][0]["new_vehicles"], int)

    def test_exact_equality_filters_apply_to_query_and_metrics(self):
        self.rows.append(
            subscription(
                activation_date="2026-01-12",
                province="江苏省",
                city="苏州市",
                service_plan="基础换电",
                acquisition_channel="渠道代理",
            )
        )
        metrics_by_type = self.get_metrics(customer_type="企业")
        self.assertEqual(metrics_by_type["summary"]["new_users"], 1)
        self.assertEqual(metrics_by_type["summary"]["closing_active"], 1)
        self.assertEqual(self.calls[-1]["filters"]["customer_type"], "企业")
        metrics_by_location = self.get_metrics(
            province="江苏省", city="苏州市", service_plan="基础换电", acquisition_channel="渠道代理"
        )
        self.assertEqual(metrics_by_location["summary"]["new_users"], 1)
        self.assertEqual(metrics_by_location["summary"]["closing_active"], 1)
        self.assertEqual(
            self.calls[-1]["filters"],
            {
                "activation_date": ["<=", "2026-01-31"],
                "province": "江苏省",
                "city": "苏州市",
                "service_plan": "基础换电",
                "acquisition_channel": "渠道代理",
            },
        )

    def test_zero_opening_active_has_zero_churn_rate(self):
        self.rows = [subscription(activation_date="2026-01-05", churn_date="2026-01-15", churn_reason="竞品")]
        period = self.get_metrics()["periods"][0]
        self.assertEqual(period["opening_active"], 0)
        self.assertEqual(period["churn_rate"], 0.0)

    def test_calendar_month_buckets_are_clipped_to_range(self):
        result = self.get_metrics(from_date="2026-01-15", to_date="2026-02-10")
        self.assertEqual(
            [(row["label"], row["bucket_start"], row["bucket_end"]) for row in result["periods"]],
            [("2026-01", "2026-01-15", "2026-01-31"), ("2026-02", "2026-02-01", "2026-02-10")],
        )

    def test_calendar_week_buckets_are_clipped_to_range(self):
        result = self.get_metrics(from_date="2026-01-01", to_date="2026-01-11", granularity="Week")
        self.assertEqual(
            [(row["label"], row["bucket_start"], row["bucket_end"]) for row in result["periods"]],
            [("2026-W01", "2026-01-01", "2026-01-04"), ("2026-W02", "2026-01-05", "2026-01-11")],
        )

    def test_distributions_have_shares_top_ten_and_stable_ties(self):
        self.rows.extend(
            [
                subscription(
                    activation_date="2025-12-01",
                    province="江苏省",
                    city="苏州市",
                    service_plan="基础换电",
                    swap_station="A站",
                ),
                subscription(
                    activation_date="2025-12-01",
                    province="江苏省",
                    city="南京市",
                    service_plan="基础换电",
                    swap_station="B站",
                ),
            ]
        )
        for index in range(11):
            self.rows.append(subscription(activation_date="2025-12-01", swap_station=f"TOP-{index:02d}"))
        result = self.get_metrics()
        self.assertEqual(
            result["distributions"]["regions"][0], {"label": "浙江省", "value": 12, "share": 80.0}
        )
        self.assertEqual(
            result["distributions"]["plans"],
            [
                {"label": "畅换", "value": 12, "share": 80.0},
                {"label": "基础换电", "value": 2, "share": 13.33},
                {"label": "企业车队", "value": 1, "share": 6.67},
            ],
        )
        self.assertEqual(
            result["distributions"]["churn_reasons"], [{"label": "价格", "value": 1, "share": 100.0}]
        )
        stations = result["distributions"]["stations"]
        self.assertEqual(len(stations), 10)
        self.assertEqual(
            [entry["label"] for entry in stations[1:]], sorted(entry["label"] for entry in stations[1:])
        )
        self.assertEqual(sum(entry["share"] for entry in stations), 66.7)

    def test_empty_data_has_a_json_serializable_fixed_shape(self):
        self.rows = []
        result = self.get_metrics()
        self.assertEqual(
            result["summary"],
            {
                "opening_active": 0,
                "closing_active": 0,
                "new_users": 0,
                "churned_users": 0,
                "net_growth": 0,
                "churn_rate": 0.0,
                "active_vehicles": 0,
                "monthly_revenue": 0.0,
            },
        )
        self.assertTrue(all(value == [] for value in result["distributions"].values()))
        json.dumps(result)


class TestGrowthFilters(FrappeTestCase):
    def setUp(self):
        super().setUp()
        self.original_today = filters.today
        filters.today = lambda: "2026-09-03"

    def tearDown(self):
        filters.today = self.original_today
        super().tearDown()

    def test_dict_and_json_input_are_normalized(self):
        values = {
            "from_date": "2026-01-01",
            "to_date": "2026-01-31",
            "granularity": "Week",
            "customer_type": "个人",
            "province": "浙江省",
        }
        for raw in (values, json.dumps(values)):
            with self.subTest(raw_type=type(raw).__name__):
                result = filters.normalize_filters(raw)
                self.assertEqual(result.from_date, datetime.date(2026, 1, 1))
                self.assertEqual(result.to_date, datetime.date(2026, 1, 31))
                self.assertEqual(result.granularity, "Week")
                self.assertEqual(result.customer_type, "个人")
                with self.assertRaises(AttributeError):
                    result.city = "宁波市"

    def test_default_is_inclusive_last_twelve_calendar_months(self):
        result = filters.normalize_filters({})
        self.assertEqual(result.from_date, datetime.date(2025, 10, 1))
        self.assertEqual(result.to_date, datetime.date(2026, 9, 3))
        self.assertEqual(result.granularity, "Month")

    def test_rejects_invalid_raw_dates_options_and_types(self):
        invalid_cases = (
            {"from_date": "2026-02-01", "to_date": "2026-01-01"},
            {"from_date": "not-a-date", "to_date": "2026-01-01"},
            {"from_date": "2026-01-01", "to_date": "2026-01-31", "granularity": "Day"},
            {"from_date": "2026-01-01", "to_date": "2026-01-31", "customer_type": "未知"},
            [],
            "[]",
            "{not json}",
        )
        for raw in invalid_cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                filters.normalize_filters(raw)

    def test_allows_exactly_thirty_six_calendar_months(self):
        accepted = filters.normalize_filters({"from_date": "2023-01-01", "to_date": "2025-12-31"})
        self.assertEqual(accepted.to_date, datetime.date(2025, 12, 31))
        with self.assertRaises(ValueError):
            filters.normalize_filters({"from_date": "2023-01-01", "to_date": "2026-01-01"})

    def test_revalidates_typed_filters_against_the_shared_rules(self):
        invalid_filters = (
            filters.GrowthFilters(datetime.date(2026, 2, 1), datetime.date(2026, 1, 1)),
            filters.GrowthFilters(datetime.date(2023, 1, 1), datetime.date(2026, 1, 1)),
            filters.GrowthFilters(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), "Day"),
        )
        for value in invalid_filters:
            with self.subTest(value=value), self.assertRaises(ValueError):
                filters.normalize_filters(value)

    def test_accepts_a_valid_typed_filter_without_mutating_it(self):
        value = filters.GrowthFilters(
            from_date=datetime.date(2026, 1, 1),
            to_date=datetime.date(2026, 1, 31),
            granularity="Week",
            customer_type="企业",
            province="浙江省",
            city="杭州市",
            service_plan="企业车队",
            acquisition_channel="企业合作",
        )
        self.assertEqual(filters.normalize_filters(value), value)
