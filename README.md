# 智格用户增长中心（Battery Growth）

面向换电服务运营的独立 Frappe Framework v15 App：以“每次订阅一条记录”保留开通、暂停、流失和重新开通的生命周期，提供可审计增长报表、深色运营大屏及默认离线可用的规则型运营简报。

仅依赖 Frappe `>=15.0.0,<16.0.0`，不依赖 ERPNext、Pulse 或 Insights。

## 项目概览

显示名称为“智格用户增长中心”，App 名为 `battery_growth`，业务 DocType 为 `Service Subscription`（用户服务开通/流失记录）。同一客户重新开通时新建订阅，旧订阅的流失历史保留。

## 功能清单

- 个人/企业订阅、状态、区域、套餐、渠道、车辆、电池和月服务费；服务端校验日期、状态、车辆和数值边界。
- 固定随机种子的 240 条 Mock 数据，可幂等生成且仅重建 `is_mock = 1` 的记录。
- `User Growth Analysis` Script Report：月/周筛选、Summary、混合图、表格与订阅列表钻取。
- `/app/battery-growth-dashboard` 深色大屏：六个 KPI、趋势/分布、加载/空/错误状态、自动刷新和全屏。
- 默认本地规则简报；可选 OpenAI-compatible Provider，异常时安全回退规则结果。

## 架构

```text
Service Subscription
        │
        ▼
analytics.metrics.get_growth_metrics
 ├──────► User Growth Analysis Script Report
 ├──────► dashboard API ─► Battery Growth Dashboard
 └──────► 严格脱敏的聚合上下文 ─► 本地规则 / OpenAI-compatible Provider
```

`analytics/filters.py` 统一校验日期和白名单筛选，`analytics/metrics.py` 是报表、大屏和洞察的唯一指标来源。API 先检查 `Service Subscription` Read 权限，再返回固定聚合 Schema；页面 JavaScript 只请求和呈现，不重算指标。

## 前置条件

- Frappe v15、可用 MariaDB/Redis Bench、Python `>=3.10,<3.15`、Node.js 18+、Yarn 1.22+。
- 验证 site 为 `battery.localhost`；设置、报表和大屏默认需要 System Manager 或目标 DocType 的相应权限。

### Windows 与 WSL

Frappe v15 的 Bench、数据库迁移和资产构建应在 Linux 环境执行。Windows 推荐使用 WSL（Ubuntu）：进入 WSL 中的 Bench 后运行下列 `bench` 命令。PowerShell 找不到 `bench` 是环境缺失，不是 App 运行结论。

### Docker 验证说明

也可使用 [Frappe Docker](https://github.com/frappe/frappe_docker)：先按其文档启动带 MariaDB、Redis、worker 和 frontend 的开发 stack，再将本仓库作为可编辑 App 提供给容器内 Bench，并在该 Bench shell 中运行同一套 `install-app`、`migrate`、`build` 与 `run-tests` 命令。本 App 不要求额外镜像或 ERPNext。不要把数据库密码或 Provider API Key 写进仓库。

## 标准 Bench 安装

将 `<repository-url>` 替换为实际 Git 地址，并在目标 Bench 执行：

```powershell
bench get-app <repository-url>
bench --site battery.localhost install-app battery_growth
bench --site battery.localhost set-config developer_mode 1
bench --site battery.localhost migrate
bench build --app battery_growth
bench --site battery.localhost clear-cache
bench restart
```

`developer_mode` 有利于开发标准元数据，但不能替代 `migrate`。首次安装的 `after_install` 会写入默认 240 条演示订阅。

## 启用开发者模式

对已安装的 `battery.localhost`，执行 `bench --site battery.localhost set-config developer_mode 1` 后再 `migrate`、`build` 和清缓存；此设置便于开发标准 DocType、Report、Page 与 Workspace 元数据，不会绕过权限或数据库迁移。

## Mock 数据行为

生成器使用固定种子 `20260903`，覆盖最近 12 个完整月份、个人/企业、浙江主要城市与少量外省市、在服/暂停/流失和部分重新开通。普通调用遇到 Mock 行会跳过；只有 `rebuild=1` 才删除 Mock 行，用户创建的数据不会删除。

```powershell
bench --site battery.localhost execute battery_growth.setup.demo.seed_demo_data --kwargs "{'rebuild': 1, 'count': 240}"
bench --site battery.localhost execute frappe.client.get_count --kwargs "{'doctype': 'Service Subscription', 'filters': {'is_mock': 1}}"
```

计数应为 `240`；`count` 仅支持 1–1000。

## 路由

- Workspace：Desk 中的 `Battery Growth` / “智格用户增长中心”（通常 `/app/battery-growth`）。
- 订阅列表：`/app/service-subscription`。
- 用户增长分析：`/app/query-report/User%20Growth%20Analysis`。
- 运营大屏：`/app/battery-growth-dashboard`。
- AI 设置：`/app/growth-ai-settings`（System Manager）。

这些是 Frappe Desk 的 `/app` 路径，host 由 site 配置决定。

## 报表公式

日期端点均为包含关系；暂停仍属于在服生命周期，流失从 `churn_date` 当日生效（当日不在服）。所有筛选同时作用于指标和分布。

| 指标 | 计算口径 |
| --- | --- |
| 期初在服 | 开始日前一天已开通且未流失的订阅数 |
| 新开通 / 流失 | `activation_date` / `churn_date` 位于本期的订阅数 |
| 净增长 | 新开通 − 流失 |
| 期末在服 | 期末已开通且未在该日或之前流失的订阅数 |
| 流失率 | 流失 ÷ 期初在服 × 100%；期初为 0 时为 0 |
| 新增车辆 / 新增月服务费 | 本期开通行的 `vehicle_count` / `monthly_fee` 合计 |

支持日期、月/周、客户类型、省份、城市、套餐和获客渠道；最大跨度 36 个月。点击非零“新增用户”或“流失用户”可跳转到对应订阅列表。

## 大屏控制项

大屏使用同一聚合指标，提供日期、客户类型、省/市、套餐、渠道筛选，刷新、默认关闭的五分钟自动刷新和全屏。页面不可见时暂停轮询。六个 KPI 为在服用户、服务车辆、本期新增、本期流失、净增长和流失率；趋势与区域、客户类型、套餐、流失原因、换电站分布均来自单一 API 响应。

页面适配 1920×1080 运营屏和 1366×768/笔记本宽度，窄屏应堆叠而不横向滚动。

## 本地规则 AI

默认 Provider 为“本地规则”，不需网络、密钥或模型。它依据流失率、净增长和区域集中度，输出最多三条带证据和建议的确定性洞察；这是可正常使用的主路径。

## OpenAI-compatible 设置

System Manager 可在 `Growth AI Settings` 选择 `OpenAI Compatible`，填写 Base URL、模型、Password 类型 API Key、超时（1–120 秒）和缓存（1–1440 分钟）。服务端请求 `<base-url>/chat/completions`，要求 `summary` 和 1–3 条合法结构化洞察，并限制响应为 100 KB。

超时、非 2xx、无效 JSON、Schema/URL/配置错误或缺少 Key 时，仅记录不含密钥/载荷的错误摘要，并自动显示“规则回退”。AI 文案不是原始业务数据或统计依据。

## 隐私边界

外部 Provider 仅收到筛选值、聚合 Summary、周期指标和分布。`customer_code`、`customer_name`、`mobile`、`contact_person`、单条订阅及原始明细不会进入 AI 上下文，也不会由大屏 API 返回。两个 API 均先检查 Read 权限；生成简报接口仅接受 POST。

## 测试与质量检查

可用 Bench 中，权威 Frappe 集成测试为：

```powershell
bench --site battery.localhost run-tests --app battery_growth
```

完整验证顺序：

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

无 Bench 的本地回归（不替代上面的集成测试）：

```powershell
python -m unittest discover -s battery_growth/tests -t . -v
node battery_growth/tests/test_dashboard_page_contract.js
```

`.github/workflows/quality.yml` 使用 Python 3.10、固定版本 Ruff、JSON 校验及 Node 格式/静态/页面契约检查。它没有 Bench、MariaDB 或 Frappe runner，不能替代上述权威 Bench 测试或全新安装验收。

## 截图

当前工作树没有可运行 Frappe/Bench site，故未创建或引用占位 PNG。必须由真实 Frappe v15 浏览器会话（1920×1080）捕获后才加入：

- `docs/screenshots/subscriptions.png`：带 Mock 行和筛选器的订阅列表。
- `docs/screenshots/user-growth-report.png`：Summary、混合图和表格。
- `docs/screenshots/operations-dashboard.png`：全屏深色大屏与 AI 来源标签。

截图必须有 Frappe chrome 或可识别路由状态，且不得有真实个人数据。

## 故障排查

| 现象 | 处理方式 |
| --- | --- |
| PowerShell 找不到 `bench` | 在 WSL/Linux 或 Docker 的 Bench 中运行，不在本 App 内安装系统组件。 |
| 页面/元数据未出现 | 依次执行 `migrate`、`bench build --app battery_growth`、`clear-cache` 后刷新。 |
| 没有演示数据 | 执行上方 `rebuild: 1, count: 240` 命令并核对计数。 |
| 日期提示错误 | 日期需有效，开始不得晚于结束，跨度不得超过 36 个月。 |
| 大屏无数据/不能生成简报 | 确认 `Service Subscription` Read 权限；本地规则不需 Provider。 |
| Provider 回退 | 核对 Base URL、模型、Password API Key、超时和 JSON Schema；回退是安全设计。 |
| CI 通过但 Bench 失败 | 以 `bench --site battery.localhost run-tests --app battery_growth` 与全新站点验收为准。 |

## 许可证

[MIT](license.txt)。

## GitHub 与技术参考

- [Frappe Framework](https://github.com/frappe/frappe)：v15 框架、Desk、DocType、Report 与 Page。
- [Frappe Docker](https://github.com/frappe/frappe_docker)：容器化开发/验证环境。
- [frappe/pulse](https://github.com/frappe/pulse)：分析边界调研参考，不是运行依赖。
- [frappe/insights](https://github.com/frappe/insights)：BI 范围调研参考，不是运行依赖。

本项目采用原生独立 App，避免引入不需要的 Pulse/Insights 运行时依赖。
