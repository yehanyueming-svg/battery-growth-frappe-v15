# 智格用户增长中心：完整项目与工程调优设计

状态：已批准并实施（Docker/Bench 环境验收待执行）
设计确认日期：2026-09-09
目标分支：`feature/battery-growth`

## 1. 背景

现有仓库已经交付 Frappe v15 自定义 App，包含：

- `Service Subscription` 用户服务开通/暂停/流失单据及 240 条幂等 Mock 数据；
- `User Growth Analysis` 用户增长报表；
- `/app/battery-growth-dashboard` 深色运营大屏；
- 贯穿单据、报表、大屏和洞察的“客户类型”维度；
- 默认离线规则洞察与可选 OpenAI-compatible Provider；
- 依赖轻量测试、Frappe Bench 集成测试和真实页面截图。

当前主要缺口不是题面功能，而是面试官克隆仓库后仍需自行准备 Frappe 环境。此次优化把仓库提升为可独立搭建、运行、验证和讲解的完整项目，同时避免复制 Frappe 核心代码或伪装成生产部署。

## 2. 目标与成功标准

### 2.1 目标

1. Docker 成为主运行路径，标准 Frappe Bench 成为备用路径。
2. 支持 Windows Docker Desktop + WSL2 和 Linux Docker。
3. 首次运行自动完成镜像构建、依赖启动、站点创建、App 安装、迁移、资产构建和 Mock 数据生成。
4. 重复运行幂等，不重复生成数据，不破坏已有站点。
5. 保持现有 DocType、Report、Page、API、指标口径和路由兼容。
6. 对大屏内部结构和 AI 缓存语义进行有针对性的工程调优。
7. 提供分层测试、全新环境验收、真实截图、故障诊断和面试答辩材料。

### 2.2 可验证成功标准

- 在满足前置条件的新机器上，执行对应平台的一键启动脚本后可访问 `http://battery.localhost:8080`。
- 站点启用 `developer_mode`，安装 `battery_growth`，并包含恰好 240 条 Mock 订阅。
- 个人与企业数据均存在，三个核心页面可在 Frappe Desk 内访问。
- 第二次执行启动脚本后 Mock 数量不变。
- `down` 后重新启动，站点与数据仍存在。
- 全新 Docker 站点和标准 Bench 站点均通过 `bench --site battery.localhost run-tests --app battery_growth`。
- E 盘项目 Git 状态干净，CI 和完整 Docker 验收留有可复核证据。

## 3. 范围边界

### 3.1 本次包含

- 官方 `frappe_docker` 固定版本集成；
- 自定义 layered 镜像；
- 完整 Compose 服务编排；
- PowerShell 与 Bash 一键脚本；
- 初始化、健康检查、诊断、停止、重置和验收流程；
- 大屏模块化、响应式与可访问性调优；
- AI 简报缓存语义修正；
- CI、部署文档、验证记录和面试说明。

### 3.2 本次不包含

- TLS、正式域名、外部备份、集中监控、高可用或集群部署；
- 把 Frappe、MariaDB 数据文件、Docker 卷或 WSL 虚拟磁盘提交到 Git；
- ERPNext、Pulse、Insights 等额外运行依赖；
- 为展示复杂度而重写已经验证过的增长指标算法；
- 对外部 AI 结果进行自动业务决策。

该 Docker 环境明确定位为可重复的本地演示与开发环境，不宣称可直接用于生产。

## 4. 已选方案

采用“固定官方 `frappe_docker` + 项目适配层”。不复制整套上游仓库，也不使用把全部进程塞入一个容器的非标准方案。

### 4.1 版本锁定

- Frappe：`v15.120.0`，与现有双站点验收版本一致。
- `frappe_docker` 初始锁定提交：`380b9d069ab949754fe78331af647b673984dc04`。
- 自定义 App：实施阶段使用 `feature/battery-growth` 构建；最终验收通过后使用不可变标签 `v1.0.0-interview` 重建并复验。

若锁定的 `frappe_docker` 提交不能构建 Frappe v15，只允许改为另一个明确提交，并在验证记录中写明失败证据、替代提交和完整复验结果。禁止静默跟随 `main`。

### 4.2 预期目录

```text
battery-growth-frappe-v15/
├─ battery_growth/                 # 现有 Frappe App
├─ .env.example                    # 演示配置模板；首次启动复制为 .env
├─ deploy/
│  ├─ frappe_docker/               # 固定提交的 Git 子模块
│  ├─ apps.json                    # 自定义镜像 App 清单
│  └─ compose.override.yaml        # 本项目 Compose 适配
├─ scripts/
│  ├─ up.ps1 / up.sh
│  ├─ verify.ps1 / verify.sh
│  ├─ logs.ps1 / logs.sh
│  ├─ down.ps1 / down.sh
│  └─ reset.ps1 / reset.sh
├─ docs/
│  ├─ deployment/
│  ├─ verification/
│  └─ interview-guide.md
└─ README.md
```

## 5. 容器架构

Compose 使用官方分进程架构：

- `db`：MariaDB；
- `redis-cache`：缓存；
- `redis-queue`：任务队列与发布订阅；
- `configurator`：写入共享数据库和 Redis 配置；
- `site-init`：幂等创建/升级站点；
- `backend`：Gunicorn/Frappe 后端；
- `frontend`：Nginx 静态资源和反向代理，宿主机只暴露此服务；
- `websocket`：实时通信；
- `queue-short`、`queue-long`：后台任务；
- `scheduler`：计划任务。

命名卷：

- `battery-growth-db`：MariaDB 数据；
- `battery-growth-sites`：站点配置与文件；
- `battery-growth-logs`：Bench 日志。

MariaDB 和 Redis 不映射宿主机端口。Compose 项目名固定为 `battery-growth`，所有脚本只操作该项目下的容器、网络和卷。

## 6. 镜像构建

使用固定 `frappe_docker` 提交中的官方 layered Containerfile。`apps.json` 只包含本 App，并在构建参数中明确 Frappe v15 引用。

预发布阶段从公开仓库的 `feature/battery-growth` 构建；发布阶段从 `v1.0.0-interview` 构建。验收脚本比较容器内 App Git 提交与预期提交，防止镜像与当前交付不一致。

镜像包含运行所需 App 代码和已构建资产。容器启动后不临时执行 `bench get-app`，避免运行时网络变化和多容器代码不一致。

## 7. 一键启动与幂等初始化

Windows 入口为 `scripts/up.ps1`，Linux 入口为 `scripts/up.sh`。两者仅负责平台适配，共享同一 Compose 文件、变量名和阶段定义。

克隆仓库后，Windows 用户执行 `./scripts/up.ps1`，Linux 用户执行 `./scripts/up.sh`。脚本负责首次生成根目录 `.env`，不要求用户手工拼接多份 Compose 参数。

启动顺序：

1. 检查 Docker Engine、Compose v2、Git、目标端口和最低可用磁盘空间。
2. 初始化并校验 `frappe_docker` 子模块提交。
3. `.env` 不存在时从模板创建，并显示本地演示地址与账号。
4. 编码并校验 `apps.json`，构建自定义 layered 镜像。
5. 启动数据库和 Redis，等待健康检查。
6. 运行 configurator 和 `site-init`。
7. 启动其余 Frappe 服务。
8. 轮询 `/api/method/ping`，成功后显示 Workspace、订阅、报表、大屏和 AI 设置路径。

`site-init` 行为：

- 站点不存在：创建 `battery.localhost`；
- App 未安装：安装 `battery_growth`；
- App 已安装：跳过安装；
- 始终设置 `developer_mode = 1`，执行 `migrate`、App 资产构建和缓存清理；
- Mock 行不存在：调用默认生成器创建 240 条；
- Mock 行已存在：不重建、不追加；
- 用户数据永不因普通启动被删除。

## 8. 配置与安全

默认配置：

- 站点：`battery.localhost`；
- HTTP 端口：`8080`；
- 登录用户：`Administrator`；
- 演示密码：`admin`，仅用于本地演示并在启动输出中警告；
- AI Provider：本地规则；
- 外部 AI API Key：不提供默认值。

`.env` 被 Git 忽略，只提交 `.env.example`。数据库密码不输出到控制台。AI Key 继续保存在 Frappe Password 字段，不进入 Docker 构建参数、环境模板、日志或测试夹具。

现有 API 权限边界保持不变：读取大屏和生成洞察前均检查 `Service Subscription` Read 权限；洞察 API 仅接受 POST；外部 Provider 只收到严格白名单的聚合数据。

## 9. 失败处理与诊断

脚本为以下阶段输出稳定名称：`prerequisites`、`submodule`、`environment`、`build`、`dependencies`、`site-init`、`services`、`health`、`verification`。

- 任一阶段失败立即返回非零状态。
- 失败不自动删除卷或容器，保留现场。
- 错误消息给出下一条精确诊断命令。
- `logs` 汇总 `docker compose ps`、健康状态和最近日志，并过滤已知密码变量。
- 端口占用、Docker 未启动、磁盘不足、依赖超时和站点初始化失败均有独立提示。
- `down` 只停止服务并保留卷。
- `reset` 只删除固定项目的命名卷，必须传入 `--yes` 或 `-Force`；目标校验失败时拒绝执行。

## 10. App 内部调优

### 10.1 大屏模块化

现有 Page 路由保留。新增 Frappe v15 Bundle 入口并拆分：

- 页面入口与生命周期；
- API 请求、并发序列和自动刷新状态；
- KPI/分布/简报 DOM 渲染；
- Frappe Charts 配置与销毁；
- 纯格式化、Schema 检查和安全文本工具。

Page 原生脚本通过 `frappe.require` 懒加载 Bundle，再挂载现有 `on_page_load` 和 `on_page_show` 生命周期。继续使用原生 DOM API 和 Frappe Charts，不引入 React/Vue 或额外大型图表库。

### 10.2 交互与可访问性

- 保留日期、客户类型、地区、套餐、渠道、粒度、刷新、自动刷新和全屏控制；
- 覆盖加载、空数据、权限/网络错误和重试状态；
- 对异步请求做过期响应保护，页面隐藏或销毁后停止刷新；
- 适配 1920×1080、1366×768 和窄屏，不产生横向滚动；
- 补全按钮状态、ARIA 属性、键盘操作、焦点样式和必要的减少动画规则。

### 10.3 AI 缓存语义

当前页面生成简报时始终传 `force=1`，使服务端缓存对主要 UI 路径无效。调整为：

- 首次“生成简报”使用 `force=0`，允许读取相同聚合快照缓存；
- 已显示结果后提供“重新生成”，显式使用 `force=1`；
- 筛选或数据刷新后使当前简报失效；
- Provider 失败仍安全回退本地规则；
- 不改变 API 方法名、参数或响应 Schema。

### 10.4 明确不做的重构

现有 `analytics.metrics` 是报表、大屏和洞察的唯一指标来源，口径已有充分测试。本次不把它重写为复杂 SQL 聚合；性能扩展作为后续演进项记录，不混入交付环境优化。

## 11. 测试策略

### 11.1 静态质量

- Ruff lint/format；
- ESLint/Prettier；
- JSON 元数据解析；
- `git diff --check`；
- 密钥与危险配置模式扫描。

### 11.2 单元与契约测试

- 保留指标、筛选、Mock、权限、AI 脱敏与降级测试；
- 为大屏拆分出的纯函数添加 Node 测试；
- 为首次缓存与强制刷新语义添加失败先行测试；
- 为 Compose 服务、端口、卷、健康检查和脚本参数添加静态契约测试。

### 11.3 Docker 配置测试

- `docker compose config` 成功；
- 必需服务、网络和卷齐全；
- 数据库与 Redis 无宿主机端口；
- PowerShell/Bash 脚本引用同一项目名和配置文件；
- 重置脚本缺少确认参数时必须失败。

### 11.4 全新站点验收

从空卷执行：

1. 构建并启动；
2. 验证 Frappe 版本、App 提交、站点和 developer mode；
3. 验证 Mock 数量、客户类型和标准元数据；
4. 运行完整 App Bench 测试；
5. 验证 HTTP ping、登录页和核心 Desk 路由；
6. 再次执行启动并确认 Mock 不重复；
7. `down`/`up` 后确认数据持久化。

### 11.5 视觉验收

真实登录 Frappe Desk，在 1920×1080、1366×768 和窄屏检查：

- 单据表单与列表；
- 报表 Summary、混合图、钻取和客户类型筛选；
- 大屏 KPI、图表、分布、AI 简报、全屏和错误/空状态。

截图必须来自真实 Frappe 路由，不使用静态仿制页面，且不包含真实个人数据。

## 12. CI 设计

每次 Push/PR：

- 运行现有依赖轻量测试；
- 运行 Python/JavaScript 格式和静态检查；
- 验证 JSON、Compose 与脚本契约；
- 不在每次提交中构建完整 Frappe 镜像。

手动触发及发布标签触发：

- 构建锁定的 Frappe v15 自定义镜像；
- 从空卷启动完整 Compose；
- 执行 `verify`；
- 失败时上传去敏后的容器和初始化日志；
- 不上传 `.env`、站点配置或秘密。

## 13. 文档与面试交付

README 首屏提供 Windows 与 Linux 快速开始，随后说明标准 Bench 安装。新增：

- 架构和版本锁定说明；
- 命令速查与生命周期；
- 全新安装验证记录；
- 常见失败和诊断路径；
- 真实截图及测试环境；
- `docs/interview-guide.md`：需求理解、指标口径、权限边界、幂等设计、Docker 取舍、AI 降级和后续扩展。

答辩材料用于解释真实设计，不包含虚假的性能、生产可用性或测试声明。

## 14. 数据流

业务数据流保持：

```text
Service Subscription
        │
        ▼
analytics.metrics.get_growth_metrics
 ├──────► User Growth Analysis
 ├──────► dashboard API ─────► Operations Dashboard
 └──────► 聚合脱敏上下文 ───► 本地规则 / OpenAI-compatible Provider
```

部署流：

```text
up.ps1 / up.sh
  ├─► 固定 frappe_docker + apps.json ─► layered image
  ├─► MariaDB + Redis health
  ├─► configurator + idempotent site-init
  ├─► Frappe runtime services
  └─► HTTP health + route summary
```

## 15. 风险与控制

- 上游 Docker 结构变化：用完整提交哈希和子模块锁定。
- 首次构建较慢：使用 layered 镜像、缓存和阶段化进度提示。
- 分支漂移：最终 Docker 构建只使用不可变发布标签，并校验容器内提交。
- Windows/Linux 脚本分叉：共享 Compose、环境变量和契约测试。
- 初始化中断：步骤幂等，卷保留，可查看日志后重跑。
- 演示密码误用：启动时警告、文档明确非生产、生产事项列为范围外。
- 前端拆分引入生命周期回归：保留 Page 入口契约并增加模块级测试和真实浏览器验收。
- AI 外部依赖不稳定：默认本地规则，Provider 失败安全回退。

## 16. 实施顺序

1. 建立 Docker 配置与脚本契约测试。
2. 引入并锁定官方 `frappe_docker`。
3. 完成跨平台启动、诊断、停止和重置脚本。
4. 在现有 WSL Bench 验证 App 回归。
5. 从空卷完成 Docker v15 安装与幂等验收。
6. 按测试驱动方式拆分大屏并修正 AI 缓存语义。
7. 执行真实浏览器视觉验收并更新截图。
8. 完善 README、部署、验证和面试说明。
9. 运行全部检查，提交、推送并建立最终不可变标签。

## 17. 参考

- Frappe Docker：https://github.com/frappe/frappe_docker
- 部署方式选择：https://github.com/frappe/frappe_docker/blob/main/docs/01-getting-started/01-choosing-a-deployment-method.md
- 镜像与 Compose 结构：https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/01-overview.md
- Frappe Asset Bundling：https://docs.frappe.io/framework/user/en/basics/asset-bundling
- Frappe v15：https://github.com/frappe/frappe/tree/version-15
