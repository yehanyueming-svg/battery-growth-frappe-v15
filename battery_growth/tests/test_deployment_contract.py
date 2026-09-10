"""Dependency-light contracts for the reproducible Docker demo environment."""

import json
import re
import subprocess
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FRAPPE_DOCKER_REVISION = "380b9d069ab949754fe78331af647b673984dc04"
REQUIRED_SERVICES = (
    "configurator",
    "site-init",
    "backend",
    "frontend",
    "websocket",
    "queue-short",
    "queue-long",
    "scheduler",
    "db",
    "redis-cache",
    "redis-queue",
)
REQUIRED_STAGES = (
    "prerequisites",
    "submodule",
    "environment",
    "build",
    "dependencies",
    "site-init",
    "services",
    "health",
)


def read(relative_path: str) -> str:
    path = REPOSITORY_ROOT / relative_path
    if not path.is_file():
        raise AssertionError(f"required project file is missing: {relative_path}")
    return path.read_text(encoding="utf-8")


def service_block(compose: str, service: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(service)}:\s*\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\s*\n|^volumes:\s*$)",
        compose,
    )
    if not match:
        raise AssertionError(f"Compose service is missing: {service}")
    return match.group("body")


def gitlink_revision(relative_path: str) -> str:
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", relative_path],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    fields = result.stdout.split()
    if len(fields) < 2 or fields[0] != "160000":
        raise AssertionError(f"expected a tracked Git submodule at {relative_path}")
    return fields[1]


class TestDeploymentContract(unittest.TestCase):
    def test_versions_custom_app_and_upstream_are_pinned(self):
        env = read(".env.example")
        self.assertIn("FRAPPE_VERSION=v15.120.0", env)
        self.assertIn("FRAPPE_DOCKER_REVISION=" + FRAPPE_DOCKER_REVISION, env)
        self.assertIn("SITE_NAME=battery.localhost", env)
        self.assertIn("HTTP_PUBLISH_PORT=8080", env)

        apps = json.loads(read("deploy/apps.json"))
        self.assertEqual(
            apps,
            [
                {
                    "url": "https://github.com/yehanyueming-svg/battery-growth-frappe-v15.git",
                    "branch": "feature/battery-growth",
                }
            ],
        )
        self.assertIn("deploy/frappe_docker", read(".gitmodules").replace("\\", "/"))
        self.assertEqual(gitlink_revision("deploy/frappe_docker"), FRAPPE_DOCKER_REVISION)

    def test_compose_has_complete_private_topology(self):
        compose = read("deploy/compose.override.yaml")
        for service in REQUIRED_SERVICES:
            self.assertRegex(compose, rf"(?m)^  {re.escape(service)}:\s*$")

        self.assertIn("${HTTP_PUBLISH_PORT:-8080}:8080", service_block(compose, "frontend"))
        for private_service in ("db", "redis-cache", "redis-queue"):
            self.assertNotRegex(service_block(compose, private_service), r"(?m)^    ports:\s*$")

        self.assertRegex(compose, r"(?ms)^  sites:.*?name: battery-growth-sites$")
        self.assertRegex(compose, r"(?ms)^  db-data:.*?name: battery-growth-db$")
        self.assertRegex(compose, r"(?ms)^  logs:.*?name: battery-growth-logs$")

    def test_site_init_is_idempotent_and_preserves_user_data(self):
        site_init = service_block(read("deploy/compose.override.yaml"), "site-init")
        for expected in (
            'if [ ! -d "sites/$${SITE_NAME}" ]',
            "bench new-site",
            'bench --site "$${SITE_NAME}" list-apps',
            'bench --site "$${SITE_NAME}" install-app battery_growth',
            'bench --site "$${SITE_NAME}" set-config developer_mode 1',
            'bench --site "$${SITE_NAME}" migrate',
            "bench build --apps battery_growth",
            'bench --site "$${SITE_NAME}" clear-cache',
            "battery_growth.setup.demo.seed_demo_data",
        ):
            self.assertIn(expected, site_init)
        self.assertIn("'rebuild': 0", site_init)
        self.assertNotIn("drop-site", site_init)
        self.assertNotIn("'rebuild': 1", site_init)

    def test_platform_scripts_share_the_same_project_and_compose_layers(self):
        powershell = read("scripts/common.ps1").replace("\\", "/")
        bash = read("scripts/common.sh").replace("\\", "/")
        for script in (powershell, bash):
            self.assertIn("battery-growth", script)
            self.assertIn("deploy/frappe_docker/compose.yaml", script)
            self.assertIn("deploy/frappe_docker/overrides/compose.mariadb.yaml", script)
            self.assertIn("deploy/compose.override.yaml", script)

    def test_start_scripts_expose_stable_phases_and_build_safely(self):
        powershell = read("scripts/up.ps1")
        bash = read("scripts/up.sh")
        for stage in REQUIRED_STAGES:
            self.assertIn(stage, powershell)
            self.assertIn(stage, bash)
        for script in (powershell, bash):
            self.assertIn("--secret", script)
            self.assertIn("id=apps_json", script)
            self.assertIn("BATTERY_GROWTH_APP_REF", script)
            self.assertIn("CACHE_BUST", script)
            self.assertIn("org.opencontainers.image.revision", script)
            self.assertIn("/api/method/ping", script)
            self.assertNotIn("API_KEY", script)

    def test_down_preserves_volumes_and_reset_requires_confirmation(self):
        for relative_path in ("scripts/down.ps1", "scripts/down.sh"):
            down = read(relative_path)
            self.assertIn("down", down)
            self.assertNotIn("--volumes", down)

        reset_ps = read("scripts/reset.ps1")
        reset_sh = read("scripts/reset.sh")
        self.assertIn("[switch]$Force", reset_ps)
        self.assertIn("--yes", reset_sh)
        reset_implementations = (
            reset_ps + read("scripts/common.ps1"),
            reset_sh + read("scripts/common.sh"),
        )
        for script in reset_implementations:
            self.assertIn("battery-growth-db", script)
            self.assertIn("battery-growth-sites", script)
            self.assertIn("battery-growth-logs", script)
            self.assertIn("--volumes", script)

    def test_log_scripts_redact_passwords(self):
        for relative_path in ("scripts/logs.ps1", "scripts/logs.sh"):
            script = read(relative_path)
            self.assertIn("[REDACTED]", script)
            self.assertIn("DB_PASSWORD", script)
            self.assertIn("ADMIN_PASSWORD", script)
            self.assertIn("--tail", script)

    def test_verify_scripts_check_revision_site_tests_and_routes(self):
        for relative_path in ("scripts/verify.ps1", "scripts/verify.sh"):
            script = read(relative_path)
            self.assertIn("verification", script)
            self.assertIn("org.opencontainers.image.revision", script)
            self.assertIn("battery_growth.setup.verification.assert_deployment", script)
            self.assertIn("run-tests", script)
            self.assertIn("--app", script)
            self.assertIn("battery_growth", script)
            for route in (
                "/api/method/ping",
                "/login",
                "/app/service-subscription",
                "/app/query-report/User%20Growth%20Analysis",
                "/app/battery-growth-dashboard",
                "/app/growth-ai-settings",
            ):
                self.assertIn(route, script)

    def test_ci_initializes_submodules_and_runs_new_lightweight_checks(self):
        workflow = read(".github/workflows/quality.yml")
        self.assertIn("submodules: recursive", workflow)
        self.assertIn("test_deployment_contract", workflow)
        self.assertIn("test_deployment_verification_unit", workflow)
        self.assertIn("test_dashboard_modules.js", workflow)
        self.assertIn("docker compose", workflow)
        self.assertIn("bash -n", workflow)
        self.assertIn("git diff --check", workflow)

    def test_full_docker_ci_is_manual_or_tagged_and_uploads_only_redacted_logs(self):
        workflow = read(".github/workflows/docker-verification.yml")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertRegex(workflow, r"(?m)^\s+tags:\s*$")
        self.assertIn('"v*"', workflow)
        self.assertIn("submodules: recursive", workflow)
        self.assertGreaterEqual(workflow.count("scripts/up.sh"), 3)
        self.assertGreaterEqual(workflow.count("scripts/verify.sh"), 3)
        self.assertIn("scripts/down.sh", workflow)
        self.assertIn("scripts/logs.sh", workflow)
        self.assertIn("docker-diagnostics.log", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s+path:\s+.*\.env\s*$")

    def test_readme_leads_with_cross_platform_docker_quick_start(self):
        readme = read("README.md")
        docker_position = readme.index("## Docker 一键启动")
        bench_position = readme.index("## 标准 Bench 安装")
        self.assertLess(docker_position, bench_position)
        for command in ("./scripts/up.ps1", "./scripts/up.sh"):
            self.assertIn(command, readme)
        self.assertIn("http://battery.localhost:8080", readme)
        self.assertIn("./scripts/reset.ps1 -Force", readme)
        self.assertIn("./scripts/reset.sh --yes", readme)
        self.assertIn("本地演示与开发环境", readme)
        self.assertIn("不直接用于生产", readme)

    def test_delivery_documents_cover_operations_evidence_and_interview_topics(self):
        deployment = read("docs/deployment/docker.md")
        troubleshooting = read("docs/deployment/troubleshooting.md")
        verification = read("docs/verification/2026-09-10-local-verification.md")
        interview = read("docs/interview-guide.md")
        design = read("docs/superpowers/specs/2026-09-09-battery-growth-complete-project-design.md")

        for topic in (
            "v15.120.0",
            FRAPPE_DOCKER_REVISION,
            "BuildKit",
            "battery-growth-sites",
            "scripts/logs",
        ):
            self.assertIn(topic, deployment)
        for topic in ("端口", "Docker Engine", "site-init", "磁盘", "reset"):
            self.assertIn(topic, troubleshooting)
        for field in (
            "验证日期",
            "主机环境",
            "Frappe 版本",
            "App 提交",
            "空卷启动",
            "重复启动",
            "持久化",
            "Bench 测试",
            "真实浏览器",
        ):
            self.assertIn(field, verification)
        for topic in ("指标口径", "权限边界", "幂等", "Docker", "AI 降级", "后续扩展"):
            self.assertIn(topic, interview)
        self.assertIn("状态：已批准并实施", design)


if __name__ == "__main__":
    unittest.main()
