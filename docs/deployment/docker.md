# Docker 本地演示与开发部署

本仓库使用官方 `frappe_docker` 的 layered 镜像和分进程 Compose 架构，目标是让评审者从干净克隆稳定复现项目。它不是 TLS、备份、监控、高可用等生产能力的替代品。

## 固定版本

- Frappe：`v15.120.0`。
- `frappe_docker`：`380b9d069ab949754fe78331af647b673984dc04`。
- Compose 项目：`battery-growth`。
- Site：`battery.localhost`。
- 前端端口：`8080`；MariaDB 和 Redis 不发布宿主机端口。

上游仓库作为 `deploy/frappe_docker` Git 子模块提交。启动脚本核对实际子模块 HEAD，发现漂移会立即终止。

## 前置条件

- Windows：Docker Desktop 使用 WSL2 后端；从 PowerShell 运行 `scripts/up.ps1`。
- Linux：Docker Engine 23+ 和 Compose v2；从 Bash 运行 `scripts/up.sh`。
- Git、10 GiB 可用磁盘、可访问 GitHub/Docker Hub，以及空闲的配置端口。

Docker Engine 23+ 是硬要求，因为 `deploy/apps.json` 通过 BuildKit `--secret id=apps_json` 传入构建。App URL 或将来的私有凭据不会成为镜像历史里的 build argument。`CACHE_BUST` 使用当前 App 提交，镜像同时写入 `org.opencontainers.image.revision` 标签供验收脚本核对。

## Compose 分层

每次调用都按固定顺序组合：

1. `deploy/frappe_docker/compose.yaml`：backend、frontend、websocket、worker 和 scheduler。
2. `deploy/frappe_docker/overrides/compose.mariadb.yaml`：MariaDB 与健康检查。
3. `deploy/compose.override.yaml`：Redis、`site-init`、健康门、端口、日志挂载和稳定卷名。

持久卷为 `battery-growth-db`、`battery-growth-sites` 和 `battery-growth-logs`。数据库和站点卷使 `down`/`up` 后数据仍在；日志卷为诊断保留现场。

## 首次启动

Windows：

```powershell
./scripts/up.ps1
```

Linux/WSL：

```bash
./scripts/up.sh
```

阶段按 `prerequisites`、`submodule`、`environment`、`build`、`dependencies`、`site-init`、`services`、`health` 输出。缺少 `.env` 时只从 `.env.example` 创建一次；之后尊重用户配置。

`site-init` 仅在站点目录不存在时执行 `new-site`，仅在 App 未安装时执行 `install-app`；每次都会设置 developer mode、迁移、验证资产构建、清缓存，并以 `rebuild=0` 调用 Mock 生成器。生成器检测已有 Mock 行后跳过，因此普通启动不删除用户记录、不重建也不追加 Mock 数据。

镜像从公开 Git 分支构建，所以本地启动要求 tracked 文件干净且 `HEAD` 已推送到跟踪分支。CI 设置 `BATTERY_GROWTH_APP_REF` 为完整提交 SHA，并生成临时 BuildKit secret，使 detached checkout 也构建准确提交。官方 layered Containerfile 会删除 App 的 `.git` 目录，因此提交一致性使用 OCI revision 标签验证，而不是在运行容器内伪造 Git 信息。

## 验证与生命周期

完整验证会检查镜像提交标签、Frappe 版本、App 安装、developer mode、240 条 Mock、个人/企业类型、标准元数据、Bench App 测试和 HTTP 路由：

```powershell
./scripts/verify.ps1
./scripts/logs.ps1
./scripts/down.ps1
```

```bash
./scripts/verify.sh
./scripts/logs.sh
./scripts/down.sh
```

`scripts/logs.ps1` 和 `scripts/logs.sh` 汇总 Compose 状态、容器健康状态及最近日志，并替换 `.env` 中的数据库/管理员密码和常见 API Key/Authorization 值。

如需清空本项目的站点和数据库，使用：

```powershell
./scripts/reset.ps1 -Force
```

```bash
./scripts/reset.sh --yes
```

重置前会验证已存在卷的 Compose owner 标签；任何卷不属于 `battery-growth` 都会拒绝执行。该操作删除三个命名卷，无法由脚本恢复。

## 配置与安全

`.env` 被 Git 忽略。示例管理员密码和数据库密码只适用于隔离的本地演示；任何共享环境都必须修改。外部 AI Provider 默认关闭，示例文件、Compose、构建参数和 CI 均不包含 API Key。AI Key 仍只存入 Frappe Password 字段。
