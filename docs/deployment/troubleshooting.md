# Docker 故障诊断

所有启动错误会保留容器和卷。先运行 `./scripts/logs.ps1` 或 `./scripts/logs.sh`，再按失败阶段定位。

## prerequisites

- 找不到 Docker：启动 Docker Desktop 或 Linux Docker Engine；确认 `docker version` 同时返回 Client 和 Server。
- Docker Engine 版本过低：升级到 23+，否则 BuildKit secret 不受支持。
- Compose 不可用：安装 Compose v2，命令必须是 `docker compose version`。
- 端口占用：停止占用 `8080` 的其他进程，或修改 `.env` 的 `HTTP_PUBLISH_PORT`。同一 `battery-growth` frontend 已运行时允许幂等重跑。
- 磁盘不足：释放项目所在磁盘或 Docker 数据盘空间，至少保留 10 GiB。

## submodule 与 build

- 子模块缺失：运行 `git submodule update --init --recursive`，再核对 `git -C deploy/frappe_docker rev-parse HEAD`。
- 提交不匹配：不要跟随上游 main；切回 `.env.example` 中的固定提交。
- tracked 文件未提交或 HEAD 未推送：layered 镜像从远端 App URL 构建。本地代码必须先提交、推送，才能保证镜像与工作区一致。
- BuildKit 拉取失败：检查 GitHub、Docker Hub、代理和 DNS；现场不会被 reset。

## dependencies 与 site-init

- MariaDB 不健康：查看 `db` 日志，核对 `.env` 的 `DB_PASSWORD`，不要在控制台粘贴真实密码。
- Redis 不健康：检查 `redis-cache`/`redis-queue` 的 `redis-cli ping` 健康结果。
- `site-init` 超时：确认 configurator 已生成包含 db/redis host 的 `sites/common_site_config.json`，然后查看 `site-init` 最近日志。
- 站点已存在但迁移失败：保留 `battery-growth-sites` 与 `battery-growth-db`，修复迁移原因后重跑 `up`；不要先 reset 丢失证据。
- Mock 不是 240：运行 `verify` 获取服务端断言。普通启动不会删除已有 Mock；只有显式 reset 后的新站点会从空数据重建。

## services 与 health

- 后端健康检查失败：检查 `backend` 是否能以 `battery.localhost` Host 访问 `/api/method/ping`。
- frontend 超时：检查 backend、websocket 和 site-init 的依赖状态，以及宿主机端口映射。
- 页面跳登录：Desk 路由要求登录，这是正常权限边界；使用本地演示 Administrator 登录。

## down 与 reset

`down` 不带 `--volumes`，只停止服务。`reset` 是破坏性命令：PowerShell 必须传 `-Force`，Bash 必须传 `--yes`。如果卷 owner 校验失败，先确认是否存在同名手工卷；不要绕过校验或直接删除未知卷。
