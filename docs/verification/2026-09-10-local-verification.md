# 2026-09-11 本地验证记录

- 验证日期：2026-09-11（Asia/Shanghai）。
- 主机环境：Windows PowerShell；Python `3.13.9`；Node `v24.14.1`；Docker Desktop `4.90.0`；Docker Engine/CLI `29.7.2`（Linux `amd64`）；Docker Compose `v5.5.1`。
- Frappe 版本：真实容器站点 `15.120.0`。
- App 提交：应用代码基线为 `723c23194ab4bd1ecccec3629eae150b1de3fcc9`（`feature/battery-growth`）；本记录所在提交只更新验收文档，最终运行镜像的 OCI revision 由验证脚本继续与当前 `HEAD` 严格核对。
- 验收站点：`http://battery.localhost:8080`，本地演示账号 `Administrator`。

## 验收结论

完整通过。空卷安装、240 条 mock 数据、重复启动、数据卷持久化、Bench 测试、HTTP 路由以及真实浏览器中的单据、报表和大屏均已现场验证。验证完成后容器保持运行，方便继续查看。

## Docker 生命周期

- 空卷启动：通过。`scripts/reset.ps1 -Force` 后执行 `scripts/up.ps1`，站点创建、App 安装、迁移、资源构建和 mock 数据导入全部成功。
- 数据初始化：通过。首次创建 240 条服务订阅记录；客户类型同时包含“个人”和“企业”。
- 重复启动：通过。再次执行 `scripts/up.ps1 -SkipBuild`，初始化结果为 `created: 0, skipped: 240`，没有产生重复数据。
- 持久化：通过。执行 `scripts/down.ps1` 删除容器和网络但保留具名数据卷，再次启动后仍为 240 条；初始化仍为 `created: 0, skipped: 240`。
- 服务状态：通过。MariaDB、Redis、backend、frontend 均健康；queue、scheduler、websocket 正常运行。

## 应用与自动化测试

- 部署断言：通过。返回 Frappe `15.120.0`、App `battery_growth`、开发者模式 `1`、mock 数量 `240`，并识别 Doctype、Report、Page、Workspace 四类交付物。
- Bench 测试：通过。`94` 项执行成功，`18` 项按环境声明跳过；验证脚本临时开启 `allow_tests`，结束后已恢复为 `false`。
- 主机 Python 回归：`78 passed, 5 skipped`。
- JavaScript：ESLint、Prettier、大屏模块契约和浏览器契约全部通过。
- Python：Ruff lint 通过，Ruff format check 显示 `40 files already formatted`。
- 部署文件：PowerShell AST、Bash `-n`、Docker Compose `config --quiet`、JSON/YAML、凭据模式扫描和 Git 空白检查全部通过。

## HTTP 验证

以下路由均返回 HTTP `200`：

- `/api/method/ping`
- `/login`
- `/app/service-subscription`
- `/app/query-report/User%20Growth%20Analysis`
- `/app/battery-growth-dashboard`
- `/app/growth-ai-settings`

## 真实浏览器

使用真实浏览器登录 Frappe 后逐页验收：

- Workspace：快捷入口显示“服务订阅记录 240”，报表、大屏和 AI 设置入口可用。
- Doctype：`Service Subscription` 列表显示 `20 of 240`，客户编码、客户名称、客户类型、服务状态、开通日期、省份和城市筛选器均正常呈现。
- Report：默认 12 个月数据正常加载；摘要为期末在服 `187`、累计新增 `229`、累计流失 `53`、净增长 `176`、流失率 `22.080%`；明细表和图表均正常。
- Page：核心 KPI、用户增长趋势、客户类型、区域、服务套餐、流失原因、换电站 TOP 和 AI 运营简报区域均正常；页面检测到 2 个 SVG 图表且没有错误组件。
- 全屏：进入/退出按钮状态和大屏样式类切换正常；自动化浏览器不授予原生全屏权限时，页面降级样式仍可用。
- 响应式：在 `1920x1080`、`1366x768`、`390x844` 三种视口检查通过。对应文档宽度/滚动宽度分别为 `1905/1905`、`1351/1351`、`375/375`，没有水平溢出；移动端 KPI 自动切换为单列。
- 视觉复核：真实站点的 KPI、颜色、图例、比例条和文字均清晰可读；仓库截图与本次现场呈现一致，仅数据更新时间不同。

## 可复现命令

```powershell
./scripts/reset.ps1 -Force
./scripts/up.ps1
./scripts/verify.ps1
./scripts/up.ps1 -SkipBuild
./scripts/verify.ps1
./scripts/down.ps1
./scripts/up.ps1 -SkipBuild
./scripts/verify.ps1
```

`scripts/verify.ps1` 会校验运行镜像的 OCI revision 与当前 `HEAD` 一致；任一版本、数据、测试或 HTTP 检查失败都会以非零状态退出。
