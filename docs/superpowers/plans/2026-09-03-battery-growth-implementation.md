# Battery Growth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-shaped Frappe v15 custom App that records battery-swap service subscriptions, reports user growth and churn, presents a dark operations dashboard, and optionally generates privacy-safe AI operations briefs.

**Architecture:** A standard DocType owns subscription lifecycle data. One typed analytics service normalizes filters and calculates every metric consumed by the Script Report, dashboard API, and AI insight service, preventing metric drift. The Desk Page uses Frappe Charts and a single aggregate API; AI consumes aggregate-only context and always falls back to deterministic local rules.

**Tech Stack:** Python 3.10+, Frappe Framework `>=15.0.0,<16.0.0`, MariaDB, Node.js 18+, Yarn 1.22, JavaScript ES2021, Frappe Charts, Frappe test runner, Ruff, ESLint, Prettier.

**Spec:** `docs/superpowers/specs/2026-09-03-battery-growth-design.md`

## Global Constraints

- The App package and repository name is exactly `battery_growth`; the displayed product name is “智格用户增长中心”.
- The only required runtime dependency is Frappe Framework `>=15.0.0,<16.0.0`; ERPNext, Pulse, and Insights are not required.
- The verification site name is `battery.localhost` and developer mode must be enabled.
- Node.js must be version 18 or newer, as required by Frappe v15 asset tooling.
- The primary DocType is `Service Subscription`; the optional configuration Single DocType is `Growth AI Settings`.
- Paused subscriptions count as in-service; churn is effective on `churn_date`; reactivation creates a new subscription.
- AI requests contain aggregate metrics only and never include `customer_code`, `customer_name`, `mobile`, `contact_person`, or a row-level subscription.
- The dashboard uses the approved dark operations-screen design and must work at 1920×1080 and 1366×768 without horizontal scrolling.
- Mock generation creates 240 records using `random.Random(20260903)` and only deletes records with `is_mock = 1` when explicitly rebuilt.
- All user-facing labels and validation errors are translatable through `frappe._` or `__`.
- Each task ends with its tests passing and a focused Git commit.

---

## File Map

| Path | Responsibility |
| --- | --- |
| `pyproject.toml` | Python package metadata, Frappe v15 compatibility, Ruff configuration |
| `package.json` | Prettier and ESLint scripts used for JavaScript quality checks |
| `.eslintrc.cjs` | Browser globals and JavaScript lint policy for Frappe page scripts |
| `battery_growth/hooks.py` | App metadata, install hook, fixtures and asset registration |
| `battery_growth/battery_growth/doctype/service_subscription/*` | Subscription schema, controller, client behavior and validation tests |
| `battery_growth/battery_growth/doctype/growth_ai_settings/*` | Single settings schema and secret retrieval |
| `battery_growth/setup/demo.py` | Deterministic, idempotent Mock data generation |
| `battery_growth/analytics/filters.py` | Filter parsing and date-range validation |
| `battery_growth/analytics/metrics.py` | Shared summaries, periods and distributions |
| `battery_growth/analytics/rules.py` | Deterministic local insight rules |
| `battery_growth/integrations/openai_compatible.py` | OpenAI-compatible HTTP request and response validation |
| `battery_growth/services/insights.py` | Provider selection, privacy boundary, cache and fallback orchestration |
| `battery_growth/api/dashboard.py` | Permission-checked dashboard and insight endpoints |
| `battery_growth/battery_growth/report/user_growth_analysis/*` | Script Report definition, filters, drill-down and server output |
| `battery_growth/battery_growth/page/battery_growth_dashboard/*` | Desk Page definition, dark responsive UI and charts |
| `battery_growth/battery_growth/workspace/battery_growth/*` | Workspace navigation entry |
| `battery_growth/tests/*` | Cross-component analytics, API, AI and demo-data tests |
| `docs/screenshots/*` | Screenshots captured from the running Frappe v15 site |
| `README.md` | Installation, debug mode, usage, metric definitions, AI configuration and verification |

---

### Task 1: Scaffold the Frappe v15 App package

**Files:**
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `.eslintrc.cjs`
- Create: `yarn.lock`
- Create: `MANIFEST.in`
- Create: `license.txt`
- Create: `README.md`
- Create: `battery_growth/__init__.py`
- Create: `battery_growth/hooks.py`
- Create: `battery_growth/modules.txt`
- Create: `battery_growth/patches.txt`
- Create: `battery_growth/config/__init__.py`
- Create: `battery_growth/battery_growth/__init__.py`
- Create: `battery_growth/tests/__init__.py`

**Interfaces:**
- Consumes: Frappe v15 Bench with site `battery.localhost`.
- Produces: importable package `battery_growth`, `__version__ = "0.1.0"`, and module `Battery Growth` available to later standard DocTypes.

- [ ] **Step 1: Write the packaging smoke check**

Run before creating package files:

```powershell
bench pip install -e C:/Users/LENOVO/Documents/Codex/2026-09-03/frappe-github-frappe-frappe-1-frappe
```

Expected: FAIL because `pyproject.toml` and the package do not exist yet.

- [ ] **Step 2: Create the minimal v15 package metadata**

Create `pyproject.toml` with these effective settings:

```toml
[project]
name = "battery_growth"
authors = [{name = "Battery Growth Contributors", email = "developers@example.invalid"}]
description = "User growth analytics for battery-swap service operations"
requires-python = ">=3.10"
readme = "README.md"
license = {text = "MIT"}
dynamic = ["version"]
dependencies = []

[build-system]
requires = ["flit_core >=3.4,<4"]
build-backend = "flit_core.buildapi"

[tool.bench.frappe-dependencies]
frappe = ">=15.0.0,<16.0.0"

[tool.ruff]
line-length = 110
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Create package metadata:

```python
# battery_growth/__init__.py
__version__ = "0.1.0"


def get_version():
	return __version__
```

```python
# battery_growth/hooks.py
app_name = "battery_growth"
app_title = "智格用户增长中心"
app_publisher = "Battery Growth Contributors"
app_description = "换电服务用户增长、流失与运营洞察"
app_email = "developers@example.invalid"
app_license = "MIT"
```

Set `battery_growth/modules.txt` to one line: `Battery Growth`. Set `MANIFEST.in` to include recursive JSON, JS, CSS, CSV, HTML, and Markdown assets under `battery_growth`.

Create `package.json` with `private: true`, scripts `format:check` set to `prettier --check "battery_growth/**/*.{js,css,json}"` and `lint` set to `eslint "battery_growth/**/*.js"`, and development dependencies `prettier@3.3.3` and `eslint@8.57.1`.

Create `.eslintrc.cjs` with browser and ES2021 environments, `ecmaVersion: "latest"`, `eslint:recommended`, and read-only globals `frappe`, `__`, and `$`. Run `yarn install` to produce `yarn.lock`.

- [ ] **Step 3: Install the editable package and verify import**

Run:

```powershell
bench pip install -e C:/Users/LENOVO/Documents/Codex/2026-09-03/frappe-github-frappe-frappe-1-frappe
bench --site battery.localhost list-apps
bench --site battery.localhost install-app battery_growth
bench --site battery.localhost execute battery_growth.get_version
```

Expected: install succeeds; `list-apps` includes `battery_growth`; the execute command prints `0.1.0`.

- [ ] **Step 4: Run packaging checks**

Run:

```powershell
bench pip install ruff
ruff check battery_growth
ruff format --check battery_growth
git status --short
```

Expected: Ruff passes and Git shows only the new scaffold files.

- [ ] **Step 5: Commit the scaffold**

```powershell
git add pyproject.toml package.json yarn.lock .eslintrc.cjs MANIFEST.in license.txt README.md battery_growth
git commit -m "chore: scaffold Frappe v15 battery growth app"
```

---

### Task 2: Add the Service Subscription DocType and server validation

**Files:**
- Create: `battery_growth/battery_growth/doctype/__init__.py`
- Create: `battery_growth/battery_growth/doctype/service_subscription/__init__.py`
- Create: `battery_growth/battery_growth/doctype/service_subscription/service_subscription.json`
- Create: `battery_growth/battery_growth/doctype/service_subscription/service_subscription.py`
- Create: `battery_growth/battery_growth/doctype/service_subscription/service_subscription.js`
- Create: `battery_growth/battery_growth/doctype/service_subscription/test_service_subscription.py`

**Interfaces:**
- Consumes: module `Battery Growth` from Task 1.
- Produces: DocType `Service Subscription` and controller method `ServiceSubscription.validate()` used by Mock generation and all analytics.

- [ ] **Step 1: Write failing lifecycle validation tests**

Create `test_service_subscription.py` with focused cases using this factory:

```python
import frappe
from frappe.tests.utils import FrappeTestCase


def make_subscription(**overrides):
	values = {
		"doctype": "Service Subscription",
		"customer_code": "RIDER-TEST-001",
		"customer_name": "测试骑手",
		"customer_type": "个人",
		"service_plan": "畅换",
		"service_status": "在服",
		"activation_date": "2026-01-01",
		"acquisition_channel": "直营网点",
		"province": "浙江省",
		"city": "杭州市",
		"vehicle_count": 1,
		"battery_count": 2,
		"monthly_fee": 399,
	}
	values.update(overrides)
	return frappe.get_doc(values)


class TestServiceSubscription(FrappeTestCase):
	def test_churn_requires_date_and_reason(self):
		doc = make_subscription(service_status="已流失")
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_churn_date_cannot_precede_activation(self):
		doc = make_subscription(
			service_status="已流失", churn_date="2025-12-31", churn_reason="价格"
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_personal_subscription_has_one_vehicle(self):
		doc = make_subscription(vehicle_count=2)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_active_subscription_rejects_churn_fields(self):
		doc = make_subscription(churn_date="2026-02-01", churn_reason="迁移")
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_other_churn_reason_requires_note(self):
		doc = make_subscription(
			service_status="已流失", churn_date="2026-02-01", churn_reason="其他"
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()
```

- [ ] **Step 2: Add the standard DocType schema and verify tests fail**

Create a standard, tracked DocType with `autoname = "ZGS-.YYYY.-.#####"`, `module = "Battery Growth"`, `engine = "InnoDB"`, `track_changes = 1`, `allow_import = 1`, and the exact fields from design section 5. Add list/filter flags to `customer_name`, `customer_type`, `service_status`, `activation_date`, `province`, and `city`; add `search_index = 1` to `activation_date`, `churn_date`, `province`, and `city`. Give System Manager create/read/write/delete/export/report permissions. Add an initial controller so the DocType imports before validation is implemented:

```python
from frappe.model.document import Document


class ServiceSubscription(Document):
	pass
```

Run:

```powershell
bench --site battery.localhost migrate
bench --site battery.localhost run-tests --doctype "Service Subscription"
```

Expected: FAIL because invalid documents are still accepted by the empty controller.

- [ ] **Step 3: Implement server-side validation**

Create the controller with these methods and messages:

```python
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ServiceSubscription(Document):
	def validate(self):
		self._validate_status_dates()
		self._validate_customer_scale()
		self._validate_non_negative_values()

	def _validate_status_dates(self):
		if self.service_status == "已流失":
			if not self.churn_date or not self.churn_reason:
				frappe.throw(_("已流失的订阅必须填写流失日期和流失原因"))
			if getdate(self.churn_date) < getdate(self.activation_date):
				frappe.throw(_("流失日期不能早于开通日期"))
			if self.churn_reason == "其他" and not self.churn_note:
				frappe.throw(_("流失原因为其他时必须填写流失说明"))
		elif self.churn_date or self.churn_reason or self.churn_note:
			frappe.throw(_("在服或暂停的订阅不能填写流失信息"))

	def _validate_customer_scale(self):
		if self.customer_type == "个人" and self.vehicle_count != 1:
			frappe.throw(_("个人客户的车辆数量必须为 1"))

	def _validate_non_negative_values(self):
		if self.vehicle_count < 1 or self.battery_count < 1:
			frappe.throw(_("车辆数量和电池数量必须大于 0"))
		if self.monthly_fee < 0:
			frappe.throw(_("月服务费不能小于 0"))
```

Add client-side field visibility in `service_subscription.js`: show `churn_date`, `churn_reason`, and `churn_note` only for 已流失; show `churn_note` only when reason is 其他; set `vehicle_count` to 1 when customer type changes to 个人. Keep all authoritative rules on the server.

- [ ] **Step 4: Run lifecycle tests**

```powershell
bench --site battery.localhost run-tests --doctype "Service Subscription"
```

Expected: all five validation cases pass.

- [ ] **Step 5: Commit the business record**

```powershell
git add battery_growth/battery_growth/doctype
git commit -m "feat: add service subscription lifecycle record"
```

---

### Task 3: Generate deterministic and idempotent Mock data

**Files:**
- Create: `battery_growth/setup/__init__.py`
- Create: `battery_growth/setup/demo.py`
- Create: `battery_growth/tests/test_demo.py`
- Modify: `battery_growth/hooks.py`

**Interfaces:**
- Consumes: `Service Subscription` from Task 2.
- Produces: `seed_demo_data(rebuild: bool = False, count: int = 240) -> dict[str, int]` and `after_install() -> None`.

- [ ] **Step 1: Write failing demo-data tests**

```python
import frappe
from frappe.tests.utils import FrappeTestCase

from battery_growth.setup.demo import seed_demo_data


class TestDemoData(FrappeTestCase):
	def tearDown(self):
		frappe.db.delete("Service Subscription", {"is_mock": 1})
		frappe.db.commit()

	def test_seed_is_idempotent(self):
		first = seed_demo_data(rebuild=True, count=24)
		second = seed_demo_data(count=24)
		self.assertEqual(first["created"], 24)
		self.assertEqual(second["created"], 0)
		self.assertEqual(frappe.db.count("Service Subscription", {"is_mock": 1}), 24)

	def test_seed_contains_both_customer_types_and_churn(self):
		seed_demo_data(rebuild=True, count=24)
		self.assertGreater(frappe.db.count("Service Subscription", {"is_mock": 1, "customer_type": "个人"}), 0)
		self.assertGreater(frappe.db.count("Service Subscription", {"is_mock": 1, "customer_type": "企业"}), 0)
		self.assertGreater(frappe.db.count("Service Subscription", {"is_mock": 1, "service_status": "已流失"}), 0)
```

- [ ] **Step 2: Run the tests to verify missing generator failure**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_demo
```

Expected: FAIL with import error for `battery_growth.setup.demo`.

- [ ] **Step 3: Implement seeded generation and install hook**

Use `random.Random(20260903)`, the first day of the current month as the anchor, and weighted choices over explicit tuples for Zhejiang cities, plans, channels, stations, battery models, statuses, and churn reasons. Build each `record` dictionary through `frappe.get_doc(record).insert(ignore_permissions=True)` so controller validation still executes. Commit once after all inserts.

The public function must begin with these guards:

```python
@frappe.whitelist()
def seed_demo_data(rebuild: bool = False, count: int = 240) -> dict[str, int]:
	rebuild = frappe.utils.cint(rebuild)
	count = frappe.utils.cint(count)
	if count < 1 or count > 1000:
		frappe.throw("count 必须在 1 到 1000 之间")
	if rebuild:
		frappe.db.delete("Service Subscription", {"is_mock": 1})
	elif frappe.db.exists("Service Subscription", {"is_mock": 1}):
		return {"created": 0, "skipped": count}
```

Assign codes `MOCK-RIDER-0001` and `MOCK-CORP-0001` by customer type. For approximately 12% of customer codes, create an earlier churned subscription and a later active reactivation while keeping the total record count exactly equal to `count`. Set `is_mock = 1` on every generated row.

Add to `hooks.py`:

```python
after_install = "battery_growth.setup.demo.after_install"
```

Implement `after_install()` as `seed_demo_data()` without rebuild.

- [ ] **Step 4: Run generator tests and inspect distributions**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_demo
bench --site battery.localhost execute battery_growth.setup.demo.seed_demo_data --kwargs "{'rebuild': 1, 'count': 240}"
bench --site battery.localhost execute frappe.client.get_count --kwargs "{'doctype': 'Service Subscription', 'filters': {'is_mock': 1}}"
```

Expected: tests pass; command reports 240 created; count command returns 240.

- [ ] **Step 5: Commit Mock generation**

```powershell
git add battery_growth/hooks.py battery_growth/setup battery_growth/tests/test_demo.py
git commit -m "feat: seed deterministic subscription demo data"
```

---

### Task 4: Build the shared analytics service

**Files:**
- Create: `battery_growth/analytics/__init__.py`
- Create: `battery_growth/analytics/filters.py`
- Create: `battery_growth/analytics/metrics.py`
- Create: `battery_growth/tests/test_metrics.py`

**Interfaces:**
- Consumes: subscription fields from Task 2.
- Produces: `GrowthFilters`, `normalize_filters(raw) -> GrowthFilters`, and `get_growth_metrics(filters) -> dict` with keys `filters`, `summary`, `periods`, and `distributions`.

- [ ] **Step 1: Write failing filter and metric tests**

Create test fixtures with three subscriptions: one active before the range, one activated inside the range, and one churned inside the range. Assert:

```python
metrics = get_growth_metrics({"from_date": "2026-01-01", "to_date": "2026-01-31", "granularity": "Month"})
period = metrics["periods"][0]
self.assertEqual(period["opening_active"], 2)
self.assertEqual(period["new_users"], 1)
self.assertEqual(period["churned_users"], 1)
self.assertEqual(period["net_growth"], 0)
self.assertEqual(period["closing_active"], 2)
self.assertEqual(period["churn_rate"], 50.0)
```

Add separate assertions for customer type filtering, a zero opening denominator, invalid date order, a range over 36 months, weekly buckets, region distribution, plan distribution, churn reasons, and station ranking.

- [ ] **Step 2: Run the analytics tests and verify import failure**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_metrics
```

Expected: FAIL because `battery_growth.analytics.metrics` does not exist.

- [ ] **Step 3: Implement normalized filters**

Define an immutable dataclass:

```python
@dataclass(frozen=True)
class GrowthFilters:
	from_date: date
	to_date: date
	granularity: Literal["Week", "Month"] = "Month"
	customer_type: str | None = None
	province: str | None = None
	city: str | None = None
	service_plan: str | None = None
	acquisition_channel: str | None = None
```

`normalize_filters` must parse JSON strings and dictionaries, default to the inclusive last 12 calendar months, permit only listed granularity and customer type values, reject `from_date > to_date`, and reject ranges longer than 36 months.

- [ ] **Step 4: Implement shared metric calculation**

Use `frappe.get_list` to retrieve only `activation_date`, `churn_date`, `customer_type`, `province`, `city`, `service_plan`, `acquisition_channel`, `swap_station`, `churn_reason`, `vehicle_count`, `battery_count`, and `monthly_fee` for records activated on or before `to_date`, plus exact equality filters. This preserves Frappe read and user-permission filtering. Compute inclusive week/month buckets in Python from this narrow projection.

Use these predicates exactly:

```python
def is_active_on(row, day):
	return getdate(row.activation_date) <= day and (
		not row.churn_date or getdate(row.churn_date) > day
	)


def churned_between(row, start, end):
	return bool(row.churn_date and start <= getdate(row.churn_date) <= end)
```

Return summary keys `opening_active`, `closing_active`, `new_users`, `churned_users`, `net_growth`, `churn_rate`, `active_vehicles`, and `monthly_revenue`. Each period contains `label`, `bucket_start`, `bucket_end`, `opening_active`, `new_users`, `churned_users`, `net_growth`, `closing_active`, `churn_rate`, `new_vehicles`, and `new_monthly_fee`. Return top-ten distributions with `{label, value, share}` entries for regions and stations, and full distributions for customer types, plans, and churn reasons.

- [ ] **Step 5: Run metrics tests**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_metrics
```

Expected: all filter, period, formula and distribution tests pass.

- [ ] **Step 6: Commit the analytics core**

```powershell
git add battery_growth/analytics battery_growth/tests/test_metrics.py
git commit -m "feat: add shared growth analytics service"
```

---

### Task 5: Implement the User Growth Analysis Script Report

**Files:**
- Create: `battery_growth/battery_growth/report/__init__.py`
- Create: `battery_growth/battery_growth/report/user_growth_analysis/__init__.py`
- Create: `battery_growth/battery_growth/report/user_growth_analysis/user_growth_analysis.json`
- Create: `battery_growth/battery_growth/report/user_growth_analysis/user_growth_analysis.py`
- Create: `battery_growth/battery_growth/report/user_growth_analysis/user_growth_analysis.js`
- Create: `battery_growth/battery_growth/report/user_growth_analysis/test_user_growth_analysis.py`

**Interfaces:**
- Consumes: `get_growth_metrics(filters)` from Task 4.
- Produces: Frappe report entry point `execute(filters=None)` returning `(columns, data, message, chart, report_summary)`.

- [ ] **Step 1: Write the failing report contract test**

```python
from frappe.tests.utils import FrappeTestCase

from battery_growth.battery_growth.report.user_growth_analysis.user_growth_analysis import execute


class TestUserGrowthAnalysis(FrappeTestCase):
	def test_execute_returns_table_chart_and_summary(self):
		columns, data, message, chart, summary = execute(
			{"from_date": "2026-01-01", "to_date": "2026-03-31", "granularity": "Month"}
		)
		self.assertEqual([column["fieldname"] for column in columns][0], "period")
		self.assertEqual(chart["type"], "axis-mixed")
		self.assertEqual(len(chart["data"]["datasets"]), 3)
		self.assertEqual({item["label"] for item in summary}, {"期末在服", "累计新增", "累计流失", "净增长", "流失率"})
```

- [ ] **Step 2: Add report metadata and run the failing test**

Create a standard Script Report JSON with `report_name = "User Growth Analysis"`, `ref_doctype = "Service Subscription"`, `report_type = "Script Report"`, `is_standard = "Yes"`, module `Battery Growth`, and System Manager role.

Run:

```powershell
bench --site battery.localhost migrate
bench --site battery.localhost run-tests --module battery_growth.battery_growth.report.user_growth_analysis.test_user_growth_analysis
```

Expected: FAIL because `execute` has not been implemented.

- [ ] **Step 3: Implement report output using the shared service**

Map periods without recomputing formulas:

```python
def execute(filters=None):
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
```

Use Int, Percent and Currency field types, translated labels and explicit widths. Configure `axis-mixed` datasets as bars for 新增 and 流失 and line for 期末在服.

- [ ] **Step 4: Add report filters and drill-down**

In JavaScript define default dates using `frappe.datetime.add_months(frappe.datetime.month_start(), -11)` through today, a Week/Month selector, customer type, province, city, service plan, and acquisition channel.

The formatter must add `data-date-field`, `data-from`, and `data-to` to nonzero `new_users` and `churned_users` cells. Bind one delegated click handler that calls:

```javascript
frappe.set_route("List", "Service Subscription", {
  [dateField]: ["between", [fromDate, toDate]],
});
```

For churn cells also add `service_status: "已流失"`. Preserve the standard formatter output inside the link.

- [ ] **Step 5: Run report tests and manually open the report**

```powershell
bench --site battery.localhost run-tests --module battery_growth.battery_growth.report.user_growth_analysis.test_user_growth_analysis
bench --site battery.localhost clear-cache
```

Open `/app/query-report/User%20Growth%20Analysis`; verify filters refresh table, chart and Summary, and both drill-down links open the correctly filtered subscription list.

- [ ] **Step 6: Commit the report**

```powershell
git add battery_growth/battery_growth/report
git commit -m "feat: add user growth analysis report"
```

---

### Task 6: Implement privacy-safe AI settings and insight services

**Files:**
- Create: `battery_growth/battery_growth/doctype/growth_ai_settings/__init__.py`
- Create: `battery_growth/battery_growth/doctype/growth_ai_settings/growth_ai_settings.json`
- Create: `battery_growth/battery_growth/doctype/growth_ai_settings/growth_ai_settings.py`
- Create: `battery_growth/analytics/rules.py`
- Create: `battery_growth/integrations/__init__.py`
- Create: `battery_growth/integrations/openai_compatible.py`
- Create: `battery_growth/services/__init__.py`
- Create: `battery_growth/services/insights.py`
- Create: `battery_growth/tests/test_insights.py`

**Interfaces:**
- Consumes: the aggregate dictionary returned by `get_growth_metrics`.
- Produces: `generate_rule_insights(metrics) -> dict`, `request_insights(context, settings) -> dict`, `sanitize_metrics(metrics) -> dict`, and `get_operations_brief(filters, force=False) -> dict`.

- [ ] **Step 1: Write failing rules, privacy and fallback tests**

Test a high churn rate produces a warning, strong positive net growth produces an info insight, and region concentration over 50% produces a concentration warning. Test `sanitize_metrics` output serialized to JSON contains none of these keys: `customer_code`, `customer_name`, `mobile`, `contact_person`.

Mock `requests.post` for three provider cases:

```python
@patch("battery_growth.integrations.openai_compatible.requests.post")
def test_timeout_falls_back_to_rules(self, post):
	post.side_effect = requests.Timeout()
	result = get_operations_brief(self.filters, force=True)
	self.assertEqual(result["source"], "rules-fallback")
	self.assertGreater(len(result["insights"]), 0)
```

Add separate cases for valid structured JSON and invalid JSON fallback.

- [ ] **Step 2: Add Growth AI Settings metadata and verify tests fail**

Create a Single DocType with fields `enabled` (Check, default 1), `provider` (Select: 本地规则/OpenAI Compatible, default 本地规则), `base_url` (Data), `model` (Data), `api_key` (Password), `timeout_seconds` (Int, default 15), and `cache_minutes` (Int, default 15). Only System Manager has read/write permission.

Run:

```powershell
bench --site battery.localhost migrate
bench --site battery.localhost run-tests --module battery_growth.tests.test_insights
```

Expected: FAIL because rule and service functions do not exist.

- [ ] **Step 3: Implement deterministic local rules**

Return the fixed shape:

```python
{
	"source": "rules",
	"generated_at": frappe.utils.now_datetime().isoformat(),
	"summary": "本期运营整体平稳",
	"insights": [
		{"level": "info", "title": "净增长保持为正", "evidence": "净增长 27 户", "action": "保持当前获客节奏"}
	],
}
```

Rules use only summary and distribution values. Sort by severity `critical`, `warning`, `info`, cap at three, and return a neutral info item when no threshold fires.

- [ ] **Step 4: Implement OpenAI-compatible Provider validation**

Call the endpoint with an explicit request and no ambient authentication:

```python
response = requests.post(
	f"{base_url.rstrip('/')}/chat/completions",
	headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
	json={
		"model": model,
		"temperature": 0.2,
		"messages": [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": json.dumps(context, ensure_ascii=False)},
		],
	},
	timeout=timeout_seconds,
)
```

The system prompt states that evidence must be derived only from supplied metrics and instructs the exact JSON schema in the design. Parse either `message.content` JSON text or a dictionary, then validate:

- `summary` is a nonempty string of at most 200 characters;
- `insights` is a list of one to three objects;
- `level` is `info`, `warning`, or `critical`;
- title, evidence and action are nonempty strings capped at 120, 240 and 240 characters.

Raise `InsightProviderError` for network, HTTP, JSON and schema errors. Never include the API key or response body in the exception message.

- [ ] **Step 5: Implement orchestration, privacy filter and cache**

`sanitize_metrics` must construct a new dictionary containing only `filters` with dates and aggregate dimensions, `summary`, `periods`, and `distributions`; it must never recursively pass through unknown keys.

`get_operations_brief` selects local rules when disabled or configured for local rules. In OpenAI mode it reads `settings.get_password("api_key", raise_exception=False)`, hashes the canonical JSON returned by `sanitize_metrics` as the metric-snapshot signature, checks cache key `battery_growth:insight:{snapshot_signature}`, and calls the provider. `force=True` bypasses that cache. Catch `InsightProviderError`, log only exception class plus a fixed message, and return rule output with `source = "rules-fallback"`. Store valid LLM results with `source = "openai-compatible"` for `cache_minutes * 60` seconds.

- [ ] **Step 6: Run insight tests**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_insights
```

Expected: local rules, privacy, provider parsing, timeout and invalid-response fallback tests all pass.

- [ ] **Step 7: Commit AI services**

```powershell
git add battery_growth/battery_growth/doctype/growth_ai_settings battery_growth/analytics/rules.py battery_growth/integrations battery_growth/services battery_growth/tests/test_insights.py
git commit -m "feat: add privacy-safe AI operations brief"
```

---

### Task 7: Add permission-checked dashboard APIs

**Files:**
- Create: `battery_growth/api/__init__.py`
- Create: `battery_growth/api/dashboard.py`
- Create: `battery_growth/tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: `normalize_filters`, `get_growth_metrics`, and `get_operations_brief`.
- Produces: whitelisted `get_dashboard_data(filters=None) -> dict` and POST-only `generate_operations_brief(filters=None, force=False) -> dict`.

- [ ] **Step 1: Write failing API permission and schema tests**

```python
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from battery_growth.api.dashboard import generate_operations_brief, get_dashboard_data


class TestDashboardAPI(FrappeTestCase):
	@patch("frappe.has_permission", return_value=False)
	def test_dashboard_requires_subscription_read_permission(self, has_permission):
		with self.assertRaises(frappe.PermissionError):
			get_dashboard_data({"from_date": "2026-01-01", "to_date": "2026-12-31"})

	def test_dashboard_contract_contains_no_row_level_data(self):
		result = get_dashboard_data({"from_date": "2026-01-01", "to_date": "2026-12-31"})
		self.assertEqual(set(result), {"filters", "summary", "periods", "distributions", "generated_at"})
		self.assertNotIn("customer_name", frappe.as_json(result))
```

Assert `generate_operations_brief` is registered as a whitelisted POST-only method using Frappe's whitelisted-method metadata.

- [ ] **Step 2: Run API tests to verify failure**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_dashboard_api
```

Expected: FAIL because the API module does not exist.

- [ ] **Step 3: Implement the endpoints**

Use one guard shared by both endpoints:

```python
def _require_read_permission():
	if not frappe.has_permission("Service Subscription", ptype="read"):
		raise frappe.PermissionError
```

Decorate `get_dashboard_data` with `@frappe.whitelist()` and `generate_operations_brief` with `@frappe.whitelist(methods=["POST"])`. `get_dashboard_data` returns a newly constructed response with the five tested keys; `generate_operations_brief` calls the insight service after the shared permission guard. Do not use `ignore_permissions=True` in either endpoint.

- [ ] **Step 4: Run API tests and inspect one real response**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_dashboard_api
bench --site battery.localhost execute battery_growth.api.dashboard.get_dashboard_data --kwargs "{'filters': {'from_date': '2025-10-01', 'to_date': '2026-09-30', 'granularity': 'Month'}}"
```

Expected: tests pass and output contains summary, twelve periods, and distributions without personal fields.

- [ ] **Step 5: Commit dashboard APIs**

```powershell
git add battery_growth/api battery_growth/tests/test_dashboard_api.py
git commit -m "feat: expose secure dashboard analytics APIs"
```

---

### Task 8: Build the dark Battery Growth Dashboard Desk Page

**Files:**
- Create: `battery_growth/battery_growth/page/__init__.py`
- Create: `battery_growth/battery_growth/page/battery_growth_dashboard/__init__.py`
- Create: `battery_growth/battery_growth/page/battery_growth_dashboard/battery_growth_dashboard.json`
- Create: `battery_growth/battery_growth/page/battery_growth_dashboard/battery_growth_dashboard.js`
- Create: `battery_growth/battery_growth/page/battery_growth_dashboard/battery_growth_dashboard.css`

**Interfaces:**
- Consumes: endpoints from Task 7 and global `frappe.Chart` shipped with Frappe v15.
- Produces: Desk route `/app/battery-growth-dashboard`, filterable dashboard, five-minute optional refresh, fullscreen mode and AI brief panel.

- [ ] **Step 1: Add Page metadata and a failing browser smoke assertion**

Create standard Page JSON named `battery-growth-dashboard`, title `智格换电运营态势`, module `Battery Growth`, `standard = "Yes"`, and System Manager role.

Before implementing the page body, migrate and open the route:

```powershell
bench --site battery.localhost migrate
bench --site battery.localhost clear-cache
```

Expected: the route opens but contains no KPI elements; browser console assertion `document.querySelectorAll("[data-kpi]").length === 6` evaluates to `false`.

- [ ] **Step 2: Create the Page controller and state model**

Register:

```javascript
frappe.pages["battery-growth-dashboard"].on_page_load = (wrapper) => {
  wrapper.batteryGrowthDashboard = new BatteryGrowthDashboard(wrapper);
};

frappe.pages["battery-growth-dashboard"].on_page_show = (wrapper) => {
  wrapper.batteryGrowthDashboard.show();
};
```

`BatteryGrowthDashboard` owns `filters`, `charts`, `refreshTimer`, `requestSerial`, and methods `makePage`, `makeFilters`, `show`, `refresh`, `renderSummary`, `renderCharts`, `renderEmpty`, `renderError`, `toggleAutoRefresh`, `toggleFullscreen`, `loadBrief`, and `destroy`. Increment `requestSerial` for each refresh and ignore stale responses.

- [ ] **Step 3: Build semantic dashboard markup and filter controls**

Use `frappe.ui.make_app_page` with one column. Add date, customer type, province, city, plan and granularity fields through `page.add_field`. Add visible buttons for refresh, automatic refresh and fullscreen. The body must contain:

```html
<section class="bg-dashboard" aria-label="智格换电运营态势">
  <div class="bg-status" role="status" aria-live="polite"></div>
  <div class="bg-kpis" aria-label="核心指标"></div>
  <div class="bg-chart-grid"></div>
  <section class="bg-ai-brief" aria-labelledby="bg-ai-title">
    <header><h2 id="bg-ai-title">AI 运营简报</h2><button type="button" class="btn btn-xs btn-default bg-generate-brief">重新生成</button></header>
    <div class="bg-ai-content"></div>
  </section>
</section>
```

Render all text with escaped values or text nodes. Never inject API text as trusted HTML.

- [ ] **Step 4: Render KPIs and Frappe Charts**

Render six `[data-kpi]` elements for in-service users, active vehicles, new users, churned users, net growth and churn rate. Instantiate one axis-mixed trend chart, one customer-type donut, and horizontal percentage/list visualizations for regions, plans, churn reasons and stations. Destroy existing chart instances before replacement.

Chart datasets map directly from `periods` and `distributions`; no formula is recomputed in JavaScript. Use textual legends and values beside every distribution so information remains understandable without color.

- [ ] **Step 5: Implement interaction, refresh and failure states**

`refresh()` calls `battery_growth.api.dashboard.get_dashboard_data` once and disables the refresh control while pending. If `periods` is empty, display a Chinese empty state. On failure, keep filters visible and show a retry button.

Automatic refresh uses `window.setInterval` at 300000 ms and skips requests when `document.hidden`. Fullscreen calls `element.requestFullscreen()` and listens for `fullscreenchange`. Clear the interval and event listeners in `destroy`.

The brief button uses a POST `frappe.call` to `generate_operations_brief`; show source as `规则分析`, `AI 生成`, or `规则回退` and render generated time.

- [ ] **Step 6: Apply the approved dark responsive design**

Scope every CSS selector under `.bg-dashboard`. Use Frappe CSS variables with dark fallbacks, 16:9-friendly grid geometry, minimum 16px primary labels, tabular numbers, strong focus states, and these breakpoints:

- `min-width: 1440px`: six KPIs, trend span 8 columns, distribution panel span 4;
- `992px–1439px`: three KPIs per row, two chart columns;
- below `992px`: one chart column and no fixed height.

Do not set fixed viewport height or horizontal overflow. Use red only for churn/critical, green for positive growth, blue for active totals, and pair every color with a label.

- [ ] **Step 7: Build assets and perform browser checks**

```powershell
bench build --app battery_growth
bench --site battery.localhost clear-cache
```

Verify in browser:

1. exactly six KPI elements render;
2. changing customer type alters KPI and chart values;
3. rapid filter changes do not let stale responses overwrite the newest state;
4. auto-refresh stops when the tab is hidden;
5. fullscreen enters and exits without layout clipping;
6. AI brief labels its source and falls back when model settings are invalid;
7. 1920×1080 and 1366×768 have no overlap or horizontal scroll;
8. keyboard focus reaches every control in logical order.

- [ ] **Step 8: Commit the Desk Page**

```powershell
git add battery_growth/battery_growth/page
git commit -m "feat: add dark battery growth operations dashboard"
```

---

### Task 9: Add Workspace navigation and complete App integration

**Files:**
- Create: `battery_growth/battery_growth/workspace/battery_growth/battery_growth.json`
- Create: `battery_growth/battery_growth/workspace/battery_growth/__init__.py`
- Create: `battery_growth/tests/test_app_integration.py`

**Interfaces:**
- Consumes: DocType, Report, Page and Settings from Tasks 2–8.
- Produces: one Desk Workspace with discoverable links and an installation-level integration test.

- [ ] **Step 1: Write failing integration test**

```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestAppIntegration(FrappeTestCase):
	def test_all_standard_artifacts_exist(self):
		self.assertTrue(frappe.db.exists("DocType", "Service Subscription"))
		self.assertTrue(frappe.db.exists("DocType", "Growth AI Settings"))
		self.assertTrue(frappe.db.exists("Report", "User Growth Analysis"))
		self.assertTrue(frappe.db.exists("Page", "battery-growth-dashboard"))
		self.assertTrue(frappe.db.exists("Workspace", "Battery Growth"))
```

- [ ] **Step 2: Run integration test to verify missing Workspace**

```powershell
bench --site battery.localhost run-tests --module battery_growth.tests.test_app_integration
```

Expected: FAIL on the Workspace assertion.

- [ ] **Step 3: Create the standard Workspace**

Create a public standard Workspace titled `Battery Growth`, label `智格用户增长中心`, module `Battery Growth`, with:

- shortcut to Service Subscription list;
- shortcut to new Service Subscription;
- link to User Growth Analysis;
- link to battery-growth-dashboard;
- link to Growth AI Settings visible to System Manager.

Set the app icon to a Frappe-supported chart icon and avoid custom binary assets.

- [ ] **Step 4: Migrate and run integration tests**

Run:

```powershell
bench --site battery.localhost migrate
bench --site battery.localhost run-tests --module battery_growth.tests.test_app_integration
```

Expected: all standard artifact assertions pass and the Workspace opens from Desk.

- [ ] **Step 5: Commit integration metadata**

```powershell
git add battery_growth/battery_growth/workspace battery_growth/tests/test_app_integration.py
git commit -m "feat: add battery growth workspace navigation"
```

---

### Task 10: Complete documentation, full verification and screenshots

**Files:**
- Modify: `README.md`
- Create: `docs/screenshots/subscriptions.png`
- Create: `docs/screenshots/user-growth-report.png`
- Create: `docs/screenshots/operations-dashboard.png`
- Create: `.github/workflows/quality.yml`

**Interfaces:**
- Consumes: the complete App from Tasks 1–9.
- Produces: reproducible evaluator workflow, evidence screenshots and a clean verified repository.

- [ ] **Step 1: Write README as an executable evaluator guide**

Document these exact sections: project overview, feature list, architecture, prerequisites, standard Bench install, Docker-based verification notes, enabling developer mode, Mock data behavior, routes, report formulas, dashboard controls, local-rule AI, OpenAI-compatible settings, privacy boundary, tests, screenshots, troubleshooting, license and GitHub references.

Include these commands with `battery.localhost` consistently:

```powershell
bench --site battery.localhost install-app battery_growth
bench --site battery.localhost set-config developer_mode 1
bench --site battery.localhost migrate
bench build --app battery_growth
bench --site battery.localhost clear-cache
bench --site battery.localhost execute battery_growth.setup.demo.seed_demo_data --kwargs "{'rebuild': 1, 'count': 240}"
bench --site battery.localhost run-tests --app battery_growth
```

- [ ] **Step 2: Add CI quality checks**

Create a GitHub Actions workflow triggered by pull request and push. Use Python 3.10 to install Ruff, run `ruff check battery_growth`, run `ruff format --check battery_growth`, and validate all JSON files with Python’s standard JSON tool. Do not claim this lightweight job replaces the Frappe integration run; document the Bench command as the authoritative test.

- [ ] **Step 3: Run the complete local verification**

Run in this order:

```powershell
bench --site battery.localhost migrate
bench build --app battery_growth
bench --site battery.localhost clear-cache
bench --site battery.localhost run-tests --app battery_growth
ruff check battery_growth
ruff format --check battery_growth
yarn format:check
yarn lint
git diff --check
git status --short
```

Expected: migration and asset build succeed; every App test passes; Ruff and whitespace checks pass; only intended documentation and screenshot changes remain.

- [ ] **Step 4: Capture actual Frappe UI screenshots**

With the Frappe v15 site running and browser viewport set to 1920×1080, capture:

1. Service Subscription list with Mock rows and visible filters;
2. User Growth Analysis with Summary, mixed chart and table;
3. Battery Growth Dashboard in fullscreen dark mode with AI source label.

Save PNG files at the exact paths listed in this task. Verify each image shows actual Frappe chrome or route state and contains no real personal data.

- [ ] **Step 5: Perform a fresh-install acceptance test**

Create a disposable site named `battery-acceptance.localhost`, install the App, and verify exactly 240 Mock rows are created:

```powershell
$env:BATTERY_DB_ROOT_PASSWORD = Read-Host "MariaDB root password"
bench new-site battery-acceptance.localhost --admin-password admin --db-root-password $env:BATTERY_DB_ROOT_PASSWORD
bench --site battery-acceptance.localhost install-app battery_growth
bench --site battery-acceptance.localhost execute frappe.client.get_count --kwargs "{'doctype': 'Service Subscription', 'filters': {'is_mock': 1}}"
bench --site battery-acceptance.localhost run-tests --app battery_growth
```

Expected: count is 240 and all tests pass. Keep the disposable site until the final verification is reported; removing it is a separate destructive action requiring explicit approval.

- [ ] **Step 6: Commit documentation and verification assets**

```powershell
git add README.md docs/screenshots .github/workflows/quality.yml
git commit -m "docs: add setup guide and verified product screenshots"
git status --short --branch
git log --oneline --decorate -10
```

Expected: clean working tree and a focused commit history for all ten tasks.

---

## Final Review Checklist

- [ ] A clean Frappe v15 site installs the App without ERPNext.
- [ ] Developer mode, migration, build and test commands in README are reproducible.
- [ ] Exactly 240 deterministic Mock records exist after first installation.
- [ ] DocType validation rejects every invalid state specified in the design.
- [ ] Report and dashboard share `get_growth_metrics` and show identical totals.
- [ ] Date, customer type, province, city, plan and channel filters work.
- [ ] Dashboard is readable at 1920×1080 and 1366×768 and can enter fullscreen.
- [ ] AI local rules work without a model; provider failures fall back safely.
- [ ] Aggregated AI context contains no row-level or personal fields.
- [ ] Tests, Ruff, JSON validation, asset build and `git diff --check` pass.
- [ ] README contains only screenshots captured from the running implementation.
