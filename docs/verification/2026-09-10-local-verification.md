# 2026-09-10 本地验证记录

- 验证日期：2026-09-10（Asia/Shanghai）。
- 主机环境：Windows PowerShell；Python `3.13.9`；Node `v24.14.1`；Docker 命令不可用；未发现可用 WSL/Bench。
- Frappe 版本：目标固定 `15.120.0`；当前主机未运行真实站点，尚未现场复核。
- App 提交：工作区 `feature/battery-growth`；本记录所在提交即待验收交付版本，Docker 验收时由镜像 OCI revision 标签与 `HEAD` 自动核对。

## 已运行

- 依赖轻量 Python 全量回归：83 项通过，5 项因没有 Frappe site database 按测试声明跳过。
- 部署拓扑、生命周期、验收、CI 与文档契约：12 项通过，包含在上述 83 项中。
- 拆分后大屏模块契约与浏览器契约：均通过。
- Ruff：锁定版本 `0.6.9` 的 lint 与 format check 均通过。
- ESLint：项目锁定版本 `8.57.1` 通过。
- Prettier：项目锁定版本 `3.3.3`，以 `--end-of-line auto` 排除 Windows checkout 换行差异后通过；本轮新增文件另按 LF 格式化。
- PowerShell 语法：所有 `scripts/*.ps1` 通过 AST parser。
- Bash 语法：所有 `scripts/*.sh` 通过 Git for Windows Bash `-n`。
- JSON/YAML：仅校验仓库自有文件；JSON 解析与 YAML 解析均通过，上游子模块内容不被改写。
- 凭据模式扫描：仓库自有文件未发现 API token、GitHub token 或私钥模式。
- Git 补丁空白检查：通过。

## 环境门槛下未运行

- 空卷启动：未运行；主机没有 Docker Engine。
- Compose 合并配置：未运行；主机没有 Docker Compose 命令。轻量 CI 已配置在有 Docker 的 Linux runner 上执行 `docker compose config --quiet`。
- 重复启动：未运行；主机没有 Docker Engine。
- 持久化：未运行；主机没有 Docker Engine。
- Bench 测试：未运行；主机没有 Frappe Bench/site。
- 真实浏览器：本轮未运行；没有可访问的真实 Frappe site。仓库既有截图来自先前记录的 Frappe `15.120.0` 会话，本轮不冒充重新验收。

具备 Docker 的环境应按顺序执行：

```powershell
./scripts/reset.ps1 -Force
./scripts/up.ps1
./scripts/verify.ps1
./scripts/up.ps1 -SkipBuild
./scripts/verify.ps1 -SkipBenchTests
./scripts/down.ps1
./scripts/up.ps1 -SkipBuild
./scripts/verify.ps1 -SkipBenchTests
```

只有空卷、幂等、持久化、Bench 和真实浏览器验收均完成后，才能创建最终不可变发布标签。
