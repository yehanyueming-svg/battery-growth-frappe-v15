"""Deterministic demo subscriptions for local evaluation and fresh installs."""

import random
from datetime import timedelta

import frappe


_SEED = 20260903
_CITIES = (("杭州市", 34), ("宁波市", 22), ("温州市", 18), ("嘉兴市", 12), ("绍兴市", 9), ("湖州市", 5))
_CHANNELS = (("直营网点", 40), ("企业合作", 25), ("渠道代理", 20), ("线上推广", 15))
_STATIONS = (
	("杭州城北换电站", 20),
	("杭州滨江换电站", 18),
	("宁波鄞州换电站", 17),
	("温州龙湾换电站", 15),
	("嘉兴南湖换电站", 15),
	("绍兴柯桥换电站", 15),
)
_BATTERY_MODELS = (("ZGS-LFP-48", 45), ("ZGS-LFP-60", 35), ("ZGS-LFP-72", 20))
_STATUSES = (("在服", 72), ("暂停", 12), ("已流失", 16))
_CHURN_REASONS = (("价格", 24), ("服务覆盖", 22), ("迁移", 18), ("业务停止", 16), ("竞品", 16), ("其他", 4))


def _weighted_choice(randomizer, choices):
	values, weights = zip(*choices)
	return randomizer.choices(values, weights=weights, k=1)[0]


def _month_anchor():
	return frappe.utils.getdate(frappe.utils.today()).replace(day=1)


def _customer_type(index):
	return "个人" if index % 3 else "企业"


def _customer_code(customer_type, counters):
	prefix = "RIDER" if customer_type == "个人" else "CORP"
	counters[prefix] += 1
	return f"MOCK-{prefix}-{counters[prefix]:04d}"


def _build_record(randomizer, anchor, customer_type, customer_code, activation_date, status=None):
	city = _weighted_choice(randomizer, _CITIES)
	service_status = status or _weighted_choice(randomizer, _STATUSES)
	if customer_type == "个人":
		vehicle_count = 1
		battery_count = randomizer.randint(2, 4)
		service_plan = _weighted_choice(randomizer, (("基础换电", 35), ("畅换", 65)))
		monthly_fee = _weighted_choice(randomizer, ((299, 25), (399, 50), (499, 25)))
		customer_name = f"演示骑手{customer_code[-4:]}"
		organization = ""
		contact_person = ""
	else:
		vehicle_count = randomizer.randint(2, 18)
		battery_count = vehicle_count * randomizer.randint(2, 4)
		service_plan = "企业车队"
		monthly_fee = vehicle_count * _weighted_choice(randomizer, ((549, 30), (599, 45), (649, 25)))
		customer_name = f"演示企业{customer_code[-4:]}"
		organization = customer_name
		contact_person = f"联系人{customer_code[-4:]}"

	record = {
		"doctype": "Service Subscription",
		"customer_code": customer_code,
		"customer_name": customer_name,
		"customer_type": customer_type,
		"contact_person": contact_person,
		"organization": organization,
		"service_plan": service_plan,
		"service_status": service_status,
		"activation_date": activation_date.isoformat(),
		"acquisition_channel": _weighted_choice(randomizer, _CHANNELS),
		"province": "浙江省",
		"city": city,
		"swap_station": _weighted_choice(randomizer, _STATIONS),
		"battery_model": _weighted_choice(randomizer, _BATTERY_MODELS),
		"vehicle_count": vehicle_count,
		"battery_count": battery_count,
		"monthly_fee": monthly_fee,
		"churn_date": None,
		"churn_reason": None,
		"churn_note": None,
		"is_mock": 1,
	}
	if service_status == "已流失":
		churn_date = min(anchor - timedelta(days=1), activation_date + timedelta(days=randomizer.randint(14, 150)))
		record["churn_date"] = churn_date.isoformat()
		record["churn_reason"] = _weighted_choice(randomizer, _CHURN_REASONS)
		if record["churn_reason"] == "其他":
			record["churn_note"] = "演示数据：其他运营原因"
	return record


def _build_records(count):
	randomizer = random.Random(_SEED)
	anchor = _month_anchor()
	counters = {"RIDER": 0, "CORP": 0}
	reactivation_count = int(count * 0.12)
	records = []

	for index in range(reactivation_count):
		customer_type = _customer_type(index)
		customer_code = _customer_code(customer_type, counters)
		activation_date = anchor - timedelta(days=randomizer.randint(210, 340))
		records.append(
			_build_record(randomizer, anchor, customer_type, customer_code, activation_date, status="已流失")
		)
		reactivation_date = min(
			anchor - timedelta(days=1), activation_date + timedelta(days=randomizer.randint(40, 120))
		)
		records.append(
			_build_record(randomizer, anchor, customer_type, customer_code, reactivation_date, status="在服")
		)

	for index in range(count - (reactivation_count * 2)):
		customer_type = _customer_type(index + reactivation_count)
		customer_code = _customer_code(customer_type, counters)
		activation_date = anchor - timedelta(days=randomizer.randint(1, 365))
		records.append(_build_record(randomizer, anchor, customer_type, customer_code, activation_date))
	return records


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

	for record in _build_records(count):
		frappe.get_doc(record).insert(ignore_permissions=True)
	frappe.db.commit()
	return {"created": count, "skipped": 0}


def after_install() -> None:
	seed_demo_data()
