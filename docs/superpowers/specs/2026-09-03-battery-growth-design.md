# Battery Growth：智格用户增长中心设计规格

日期：2026-09-03  
目标框架：Frappe Framework v15  
App 包名：`battery_growth`  
产品名称：智格用户增长中心

## 1. 背景与目标

浙江智格科技有限公司为物流领域的低速电动车辆提供动力电池、充换电设备及相关销售、租赁和运营服务。本项目用于演示以 Frappe v15 构建业务单据、经营报表和运营大屏的完整能力，并通过可选 AI 运营简报展示 Agent 能力的安全集成方式。

交付一个可以安装到纯 Frappe v15 站点的独立 App，包含：

1. 用户服务开通/流失记录 DocType，并预置可重复生成的 Mock 数据；
2. 用户增长分析 Script Report；
3. 智格换电运营态势 Desk Page；
4. 可选 AI 运营简报，未配置模型时仍可完整运行。

## 2. GitHub 项目调研与复用决策

调研发现两个相关官方项目：

- [`frappe/pulse`](https://github.com/frappe/pulse)：跟踪用户交互、使用趋势和产品健康度，适合参考分析边界、测试方式及事件聚合思路；但其核心是遥测事件、Redis 缓冲和消费管道，不符合服务订阅单据的业务语义，并与 Frappe `develop` 分支能力存在较强耦合。
- [`frappe/insights`](https://github.com/frappe/insights)：完整 BI 平台，图表和查询能力强，但对本题而言依赖和产品范围过大，无法充分展示候选人独立实现 Frappe 报表及页面的能力。

因此采用独立原生 Frappe App。实现可参考上述项目的边界与工程实践，但不复制其业务代码，也不将其作为运行依赖。

## 3. 范围

### 3.1 包含

- 个人骑手与企业客户两种客户类型；
- 服务订阅全生命周期的当前状态与历史订阅记录；
- 开通、流失、净增长、在服规模和流失率统计；
- 车辆、电池、服务费等换电业务规模指标；
- 日期、客户类型、区域、套餐、渠道等筛选；
- 深色、全屏、响应式运营大屏；
- 本地规则分析和 OpenAI 兼容接口两种 AI 模式；
- 自动 Mock 数据、安装说明、测试和实际运行截图。

### 3.2 不包含

- 实际充换电硬件接入、遥测采集或实时设备控制；
- 完整 CRM、计费、合同、库存或换电订单系统；
- 大模型训练、微调或向量知识库；
- 对 ERPNext 的强依赖；
- Pulse 或 Insights 的运行时依赖。

这些边界让 App 能安装在纯 Frappe v15 站点，同时保留未来接入 ERPNext Customer、Item、Asset 或 Subscription 的扩展空间。

## 4. 总体架构

App 分为四个职责清晰的层次：

1. **业务数据层**：`Service Subscription` DocType 保存订阅生命周期数据并执行字段级业务校验。
2. **指标服务层**：统一的 Python 聚合模块计算报表、大屏和 AI 所需指标，避免三处重复统计口径。
3. **展示层**：Script Report 提供可审计的数据表和标准图表；Desk Page 提供深色大屏及交互筛选。
4. **洞察层**：本地规则引擎或可选 OpenAI 兼容 Provider 只消费聚合指标，失败时安全回退。

数据流如下：

```text
Service Subscription
        │
        ▼
统一指标聚合服务 ─────► User Growth Analysis Report
        │
        ├────────────► Dashboard API ─► Battery Growth Dashboard Page
        │
        └────────────► 脱敏聚合上下文 ─► 规则引擎 / LLM Provider
```

## 5. 数据模型

### 5.1 Service Subscription

中文标签：用户服务开通/流失记录。每条记录代表一次服务订阅。同一客户流失后重新开通时创建新订阅，从而保留历史生命周期。

建议命名规则：`ZGS-.YYYY.-.#####`。

| 分组 | 字段名 | 类型 | 约束或说明 |
| --- | --- | --- | --- |
| 客户 | `customer_code` | Data | 必填、列表显示，用于识别同一客户 |
| 客户 | `customer_name` | Data | 必填、列表显示、可搜索 |
| 客户 | `customer_type` | Select | 必填：个人、企业 |
| 客户 | `contact_person` | Data | 企业联系人；个人可为空 |
| 客户 | `mobile` | Data | 可选；不得进入 AI 上下文 |
| 客户 | `organization` | Data | 个人用户所属企业，可选 |
| 服务 | `service_plan` | Select | 必填：基础换电、畅换、企业车队 |
| 服务 | `service_status` | Select | 必填：在服、暂停、已流失 |
| 服务 | `activation_date` | Date | 必填、建立索引 |
| 服务 | `churn_date` | Date | 已流失时必填、建立索引 |
| 服务 | `acquisition_channel` | Select | 直营网点、企业合作、渠道代理、线上推广 |
| 区域 | `province` | Data | 必填、建立索引 |
| 区域 | `city` | Data | 必填、建立索引 |
| 区域 | `swap_station` | Data | 可选 |
| 设备 | `battery_model` | Data | 可选 |
| 规模 | `vehicle_count` | Int | 必填且大于 0；个人默认 1 |
| 规模 | `battery_count` | Int | 必填且大于 0 |
| 规模 | `monthly_fee` | Currency | 非负 |
| 流失 | `churn_reason` | Select | 价格、服务覆盖、迁移、业务停止、竞品、其他 |
| 流失 | `churn_note` | Small Text | 选择“其他”时必填 |
| 系统 | `is_mock` | Check | 隐藏、只读；仅由演示数据生成器设置 |

标准字段 `owner`、`creation`、`modified`、`modified_by` 用于审计；启用 Track Changes。

### 5.2 业务规则

- `service_status = 已流失` 时必须提供 `churn_date` 和 `churn_reason`；
- `churn_date` 不得早于 `activation_date`；
- 在服或暂停记录不得保留流失日期、原因和说明；
- 个人客户的 `vehicle_count` 固定为 1；企业客户允许大于 1；
- `vehicle_count`、`battery_count` 必须大于 0，`monthly_fee` 不得小于 0；
- 流失原因是“其他”时必须填写说明；
- 业务校验在 Python Controller 中实现，不仅依赖前端脚本。

### 5.3 Growth AI Settings

辅助 Single DocType，只有 System Manager 可写。

字段包括：是否启用、Provider（本地规则/OpenAI Compatible）、Base URL、模型名、API Key（Password）、超时秒数和缓存分钟数。默认使用本地规则，不需要网络或密钥。

## 6. Mock 数据

安装后由 `after_install` 调用确定性数据生成器，默认生成约 200 条、覆盖最近 12 个完整月份的订阅记录：

- 同时包含个人和企业客户；
- 覆盖浙江省主要城市，并包含少量其他区域；
- 包含在服、暂停、流失和重新开通场景；
- 套餐、渠道、换电站、电池型号和流失原因具有合理分布；
- 企业客户的车辆和电池数量高于个人客户；
- 使用固定随机种子，便于测试断言和不同环境横向比较。

生成器必须幂等：已存在带 Mock 标记的数据时，普通执行跳过；显式传入重建参数时，仅删除由本生成器创建的 Mock 记录并重新生成，不删除用户创建的数据。

## 7. 用户增长分析报表

标准 Script Report：`User Growth Analysis`，中文名称“用户增长分析”，引用 `Service Subscription`。

### 7.1 筛选

- `from_date`、`to_date`，默认最近 12 个月；
- 粒度：月、周；
- 客户类型：全部、个人、企业；
- 省份、城市、服务套餐、获客渠道。

必须验证日期完整性、先后顺序和最大查询范围，错误时显示可操作的中文提示。

### 7.2 指标口径

- **在服用户**：截至指定日期已开通，并且没有在该日期之前流失的订阅；暂停仍属于在服生命周期；
- **新增用户**：开通日期位于统计周期内的订阅数；
- **流失用户**：流失日期位于统计周期内的订阅数；
- **净增长**：新增用户数减流失用户数；
- **流失率**：本期流失用户数除以期初在服用户数；期初为零时显示 0，而不是报错；
- **新增车辆数**：本期开通订阅的 `vehicle_count` 合计；
- **新增月服务费**：本期开通订阅的 `monthly_fee` 合计。

同一客户重新开通的新订阅计为新增，旧订阅的历史流失仍保留。

### 7.3 输出

报表列为周期、期初在服、新开通、流失、净增长、期末在服、流失率、新增车辆和新增月服务费。

顶部 Summary 显示期末在服、累计新增、累计流失、净增长和流失率。混合图使用柱状图表示新增/流失，以折线表示期末在服。数量单元格通过 Formatter 跳转至带相应日期与状态条件的订阅列表。保留 Frappe 标准排序、筛选和导出能力。

## 8. 智格换电运营态势大屏

标准 Desk Page 路由：`battery-growth-dashboard`，中文标题“智格换电运营态势”。

### 8.1 视觉与布局

采用已确认的“深色运营大屏”方向：高对比、低装饰、适合 1920×1080 远距离查看。布局同时适配普通笔记本；窄屏时卡片和图表依次堆叠，避免横向滚动。

- 顶部工具栏：日期范围、客户类型、省市、套餐、刷新、自动刷新和全屏；
- KPI：在服用户、服务车辆、本期新增、本期流失、净增长、流失率；
- 主趋势图：新增/流失柱状数据和在服用户折线；
- 辅助图：区域用户排名、客户类型结构、套餐分布、流失原因、换电站 TOP；
- AI 运营简报：异常、可能原因、建议动作、生成方式和生成时间。

所有颜色含义同时配有文字或图例，不依赖颜色单独传达状态。图表提供 Tooltip、图例切换、加载态、空态和错误态。自动刷新默认关闭，开启后每五分钟刷新；页面不可见时暂停轮询。全屏退出后恢复原布局。

### 8.2 API 与权限

大屏只调用一个聚合读取 API 获取主要数据，减少重复请求和口径漂移。API：

- 验证当前用户对 `Service Subscription` 的 Read 权限；
- 解析和白名单化筛选参数；
- 使用 Frappe Query Builder 或参数化 SQL；
- 返回固定 Schema 的 KPI、趋势和分布数据；
- 不返回手机号、联系人或单条客户明细。

AI 生成使用独立 POST API，避免 GET 请求触发外部模型调用。

## 9. AI 运营简报

### 9.1 本地规则模式

默认模式无需模型：根据环比变化、流失率阈值、区域集中度、客户类型差异、套餐与流失原因组合生成最多三条洞察。每条洞察包含级别、标题、证据和建议。

规则结果必须由确定性测试覆盖，不能仅返回随机文案。

### 9.2 OpenAI 兼容模式

启用后，服务端将聚合指标转换为固定结构的上下文，调用管理员配置的 OpenAI 兼容 Chat Completions 接口。上下文不得包含姓名、手机号、联系人、客户编码或单条订阅记录。

模型被要求返回结构化 JSON：

```json
{
  "summary": "一句话总结",
  "insights": [
    {
      "level": "info|warning|critical",
      "title": "标题",
      "evidence": "可由指标验证的证据",
      "action": "建议动作"
    }
  ]
}
```

服务端验证顶层结构、条数、字段类型和长度。网络超时、非 2xx、无效 JSON、Schema 不符或未配置密钥时，记录不含密钥的错误日志并自动返回本地规则结果。请求设置有限超时，不在响应或日志中暴露 API Key。

相同用户可见范围、筛选条件和指标快照在配置时间内缓存。大屏明确显示“规则分析”或“AI 生成”，并显示时间；AI 文案不作为原始数据存储或统计依据。

## 10. 工程结构

```text
battery_growth/
├── battery_growth/
│   ├── hooks.py
│   ├── modules.txt
│   ├── api/
│   │   ├── dashboard.py
│   │   └── insights.py
│   ├── analytics/
│   │   ├── filters.py
│   │   ├── metrics.py
│   │   └── rules.py
│   ├── setup/
│   │   └── demo.py
│   └── battery_growth/
│       ├── doctype/
│       │   ├── service_subscription/
│       │   └── growth_ai_settings/
│       ├── report/user_growth_analysis/
│       ├── page/battery_growth_dashboard/
│       └── workspace/battery_growth/
├── docs/screenshots/
├── pyproject.toml
├── license.txt
└── README.md
```

聚合计算集中在 `analytics/metrics.py`，报表和大屏调用同一公共函数。API 只负责权限、输入输出和缓存；页面 JavaScript 只负责筛选状态、请求及渲染；AI Provider 只负责将已经脱敏的聚合上下文转换成简报。

## 11. 安装与开发体验

README 提供以下完整路径：

1. 创建或进入 Frappe v15 Bench；
2. `bench get-app` 获取仓库；
3. `bench --site <site> install-app battery_growth`；
4. `bench --site <site> set-config developer_mode 1`；
5. `bench build --app battery_growth`、清缓存并重启；
6. 打开 Workspace、报表和 `/app/battery-growth-dashboard`；
7. 可选配置 OpenAI 兼容模型；
8. 运行测试及重新生成 Mock 数据。

README 说明 Frappe v15 兼容性、统计口径、权限、常见安装问题和 AI 降级行为，并放置实际运行截图。

## 12. 测试与质量门槛

### 12.1 自动测试

- DocType：状态字段、日期顺序、个人/企业车辆规则、数值边界和流失原因；
- Metrics：期初、期末、新增、流失、净增长、流失率及筛选；
- Report：月/周分桶、Summary、Chart 和空数据；
- Dashboard API：权限、筛选白名单、返回 Schema 和脱敏；
- AI：规则输出、成功解析、超时、HTTP 错误、无效 JSON、Schema 错误和回退；
- Mock：固定数据量、关键分布和幂等执行。

### 12.2 工具检查

- Python：Ruff 格式与静态检查；
- JavaScript：ESLint/Prettier；
- Frappe：`bench --site <site> run-tests --app battery_growth`；
- 安装：在全新 Frappe v15 站点执行安装、迁移和构建；
- UI：至少验证 1920×1080 与常见笔记本宽度，检查加载、空数据、错误、全屏和筛选状态。

## 13. 验收条件

项目仅在以下条件全部满足时视为完成：

1. App 可在全新 Frappe v15 站点安装，无手工数据库操作；
2. 安装后存在可查看、编辑和筛选的预设 Mock 订阅；
3. 报表指标与固定测试数据的人工计算一致；
4. 大屏所有图表均来自同一 DocType 数据并响应筛选；
5. 深色大屏在 1920×1080 下无重叠、裁切或横向滚动；
6. 未配置模型时 AI 简报可用；模型调用失败时自动回退；
7. API 权限有效，AI 上下文与响应不包含客户个人信息；
8. 自动测试通过，README 命令可复现安装和验证；
9. 仓库包含实际运行截图，不使用静态假图冒充成品。

## 14. 关键取舍

- 使用“一次订阅一条记录”，以较小模型复杂度同时保留重开历史；
- 暂停仍计入在服生命周期，因为当前模型没有暂停起止流水；
- 用区域排名代替地图，避免引入外部地图资源、授权和离线加载问题；
- AI 只处理聚合数据并提供规则回退，避免模型成为核心功能单点；
- App 不依赖 ERPNext，确保评审者只安装 Frappe v15 即可验收。
