# Battery Growth Complete Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Frappe v15 App into a reproducible, one-command local demo project with pinned Docker infrastructure, idempotent lifecycle tooling, a modular dashboard, correct AI-cache behavior, and reviewable verification evidence.

**Architecture:** Compose layers the pinned upstream `frappe_docker` core and MariaDB definitions with a repository-owned override that adds Redis, an idempotent `site-init` job, health gates, stable volume names, and the single published frontend port. Platform entry scripts share identical constants and phases, while the App exposes a Bench-callable deployment assertion. The Desk page remains the Frappe lifecycle entry and lazy-loads a native JavaScript bundle split into focused global modules.

**Tech Stack:** Frappe Framework `v15.120.0`, Python 3.10+, MariaDB, Redis, Docker Engine 23+/Compose v2, PowerShell 7/Windows PowerShell 5.1, POSIX Bash, Frappe asset bundler, native DOM/Frappe Charts, unittest, Node 20, Ruff, ESLint, Prettier, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-battery-growth-complete-project-design.md`

## Global Constraints

- Pin Frappe to `v15.120.0` and `frappe_docker` to `380b9d069ab949754fe78331af647b673984dc04`; never follow upstream `main` implicitly.
- Use Compose project name `battery-growth`, site `battery.localhost`, published HTTP port `8080`, and local-demo Administrator password `admin`.
- Include only `battery_growth`; do not introduce ERPNext, Pulse, Insights, React, Vue, or a second chart library.
- Keep MariaDB and Redis unexposed; publish only the frontend and preserve the named `battery-growth-db`, `battery-growth-sites`, and `battery-growth-logs` volumes.
- Normal startup must preserve user data and keep exactly 240 idempotent Mock subscriptions; destructive reset requires `--yes` or `-Force`.
- Keep AI keys out of images, build arguments, `.env.example`, logs, tests, and Provider payloads.
- Preserve the current DocType, report, page route, API method names, response schemas, permission checks, and shared `analytics.metrics` calculations.
- Treat Docker as a repeatable local demo/development environment, not a production deployment.

---

### Task 1: Deployment contract and pinned upstream

**Files:**
- Create: `.env.example`
- Create: `.gitmodules`
- Create: `deploy/apps.json`
- Create: `deploy/compose.override.yaml`
- Create: `battery_growth/tests/test_deployment_contract.py`
- Add submodule: `deploy/frappe_docker` at `380b9d069ab949754fe78331af647b673984dc04`

**Interfaces:**
- Consumes: upstream `compose.yaml`, `overrides/compose.mariadb.yaml`, and `images/layered/Containerfile`.
- Produces: the canonical Compose invocation `docker compose --project-name battery-growth --env-file .env -f deploy/frappe_docker/compose.yaml -f deploy/frappe_docker/overrides/compose.mariadb.yaml -f deploy/compose.override.yaml`; environment names used by every script.

- [ ] **Step 1: Write the failing deployment contract**

```python
class TestDeploymentContract(unittest.TestCase):
    def test_versions_services_ports_and_volumes_are_pinned(self):
        env = read(".env.example")
        compose = read("deploy/compose.override.yaml")
        self.assertIn("FRAPPE_VERSION=v15.120.0", env)
        self.assertEqual(gitlink_revision("deploy/frappe_docker"), "380b9d069ab949754fe78331af647b673984dc04")
        for service in REQUIRED_SERVICES:
            self.assertRegex(compose, rf"(?m)^  {re.escape(service)}:")
        self.assertIn('name: battery-growth-db', compose)
        self.assertIn('name: battery-growth-sites', compose)
        self.assertIn('name: battery-growth-logs', compose)
        self.assertNotRegex(service_block(compose, "db"), r"(?m)^    ports:")
        self.assertNotRegex(service_block(compose, "redis-cache"), r"(?m)^    ports:")
        self.assertNotRegex(service_block(compose, "redis-queue"), r"(?m)^    ports:")
```

The same test parses `deploy/apps.json`, asserts the sole URL is this public repository and the ref is `feature/battery-growth`, and checks that `site-init` contains guarded site creation, conditional App installation, developer mode, migrate, asset build, cache clear, and non-rebuilding seed invocation.

- [ ] **Step 2: Run the focused test and observe the missing-file failure**

Run: `python -m unittest battery_growth.tests.test_deployment_contract -v`

Expected: FAIL because `.env.example`, `deploy/apps.json`, and `deploy/compose.override.yaml` do not exist.

- [ ] **Step 3: Add the pinned submodule and minimal Compose configuration**

Run:

```powershell
git submodule add https://github.com/frappe/frappe_docker.git deploy/frappe_docker
git -C deploy/frappe_docker checkout 380b9d069ab949754fe78331af647b673984dc04
```

Create a BuildKit-secret `apps.json` with only `https://github.com/yehanyueming-svg/battery-growth-frappe-v15.git` at `feature/battery-growth`. Define `redis-cache`, `redis-queue`, `site-init`, health checks, frontend port `${HTTP_PUBLISH_PORT:-8080}:8080`, and stable volume names in the override. Make all runtime Frappe services depend on a successful `site-init`.

- [ ] **Step 4: Run contract and Compose normalization checks**

Run:

```powershell
python -m unittest battery_growth.tests.test_deployment_contract -v
Copy-Item .env.example .env
docker compose --project-name battery-growth --env-file .env -f deploy/frappe_docker/compose.yaml -f deploy/frappe_docker/overrides/compose.mariadb.yaml -f deploy/compose.override.yaml config --quiet
```

Expected: unit contract PASS; Compose config PASS when Docker Compose is installed. Remove only the generated ignored `.env` after the check.

- [ ] **Step 5: Commit the independently reviewable deployment topology**

```powershell
git add .env.example .gitmodules deploy battery_growth/tests/test_deployment_contract.py
git commit -m "feat: add pinned Frappe Docker topology"
```

### Task 2: Cross-platform lifecycle scripts

**Files:**
- Create: `scripts/common.ps1`
- Create: `scripts/common.sh`
- Create: `scripts/up.ps1`
- Create: `scripts/up.sh`
- Create: `scripts/down.ps1`
- Create: `scripts/down.sh`
- Create: `scripts/logs.ps1`
- Create: `scripts/logs.sh`
- Create: `scripts/reset.ps1`
- Create: `scripts/reset.sh`
- Modify: `battery_growth/tests/test_deployment_contract.py`

**Interfaces:**
- Consumes: Task 1 environment names and canonical Compose file order.
- Produces: `Invoke-BatteryCompose`/`battery_compose`, named stages `prerequisites`, `submodule`, `environment`, `build`, `dependencies`, `site-init`, `services`, and `health`, plus safe lifecycle entry points.

- [ ] **Step 1: Extend the contract with script parity and safety failures**

```python
def test_platform_scripts_share_project_files_and_stages(self):
    for script in (read("scripts/common.ps1"), read("scripts/common.sh")):
        self.assertIn("battery-growth", script)
        self.assertIn("deploy/frappe_docker/compose.yaml", normalized(script))
        self.assertIn("deploy/compose.override.yaml", normalized(script))
    for stage in REQUIRED_STAGES:
        self.assertIn(stage, read("scripts/up.ps1"))
        self.assertIn(stage, read("scripts/up.sh"))

def test_reset_requires_explicit_confirmation(self):
    self.assertRegex(read("scripts/reset.ps1"), r"\[switch\]\$Force")
    self.assertIn('--yes', read("scripts/reset.sh"))
```

- [ ] **Step 2: Run the focused test and observe missing-script failures**

Run: `python -m unittest battery_growth.tests.test_deployment_contract -v`

Expected: FAIL on `scripts/common.ps1`.

- [ ] **Step 3: Implement shared wrappers and one-command startup**

PowerShell and Bash startup must: locate the repository without depending on the caller's current directory; require Git, Docker Engine 23+, Compose v2, an available configured port, and 10 GiB free; initialize and verify the exact submodule commit; copy `.env.example` only when `.env` is absent; reject an App revision that is dirty or not the tracked upstream commit before a remote-source image build; build the layered image with `--secret id=apps_json`, `FRAPPE_BRANCH=v15.120.0`, `CACHE_BUST=<HEAD>`, and OCI revision/source labels; start dependency services; run the idempotent `site-init`; start runtime services; and poll `/api/method/ping` with a bounded timeout.

- [ ] **Step 4: Implement down, redacted logs, and guarded reset**

`down` calls Compose down without `--volumes`. `logs` prints `ps`, inspectable health, and the last 200 log lines after replacing values for `DB_PASSWORD`, `ADMIN_PASSWORD`, and common API-key patterns with `[REDACTED]`. `reset` refuses without confirmation, validates the Compose project and exact expected volume names, then runs `down --volumes --remove-orphans`.

- [ ] **Step 5: Validate syntax and contract**

Run:

```powershell
python -m unittest battery_growth.tests.test_deployment_contract -v
$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts/up.ps1), [ref]$null, [ref]$null)
bash -n scripts/common.sh scripts/up.sh scripts/down.sh scripts/logs.sh scripts/reset.sh
```

Expected: contract PASS, PowerShell parser reports no errors, Bash syntax PASS where Bash is installed.

- [ ] **Step 6: Commit lifecycle tooling**

```powershell
git add scripts battery_growth/tests/test_deployment_contract.py
git commit -m "feat: add safe cross-platform Docker lifecycle"
```

### Task 3: Executable deployment verification

**Files:**
- Create: `battery_growth/setup/verification.py`
- Create: `battery_growth/tests/test_deployment_verification_unit.py`
- Create: `scripts/verify.ps1`
- Create: `scripts/verify.sh`
- Modify: `battery_growth/tests/test_deployment_contract.py`

**Interfaces:**
- Consumes: `Service Subscription`, Frappe configuration, Task 1 image label, and Task 2 Compose wrappers.
- Produces: `battery_growth.setup.verification.assert_deployment(expected_frappe_version="15.120.0", expected_mock_count=240) -> dict` and platform verification commands that fail nonzero on any mismatch.

- [ ] **Step 1: Write dependency-light assertion tests**

```python
def test_assert_deployment_returns_expected_facts(self):
    facts = verification.assert_deployment()
    self.assertEqual(facts["frappe_version"], "15.120.0")
    self.assertEqual(facts["mock_count"], 240)
    self.assertEqual(facts["customer_types"], ["个人", "企业"])

def test_assert_deployment_rejects_wrong_mock_count(self):
    fake_db.mock_count = 239
    with self.assertRaisesRegex(AssertionError, "expected 240"):
        verification.assert_deployment()
```

- [ ] **Step 2: Run the focused test and observe the missing-module failure**

Run: `python -m unittest battery_growth.tests.test_deployment_verification_unit -v`

Expected: FAIL because `battery_growth.setup.verification` is absent.

- [ ] **Step 3: Implement strict server-side deployment facts**

The assertion checks exact Frappe version, installed App, `developer_mode == 1`, Mock count, presence of both customer types, and standard DocType/Report/Page records. It returns only non-sensitive aggregate facts and never mutates the site.

- [ ] **Step 4: Implement host verification scripts**

Both scripts print the `verification` stage, confirm the image OCI revision label equals the checked-out `HEAD`, execute the server assertion in `backend`, run `bench --site battery.localhost run-tests --app battery_growth`, and make HTTP requests to ping, login, subscription, report, dashboard, and settings routes. Any mismatch exits nonzero.

- [ ] **Step 5: Run unit and static script checks**

Run:

```powershell
python -m unittest battery_growth.tests.test_deployment_verification_unit battery_growth.tests.test_deployment_contract -v
bash -n scripts/verify.sh
```

Expected: PASS.

- [ ] **Step 6: Commit verification tooling**

```powershell
git add battery_growth/setup/verification.py battery_growth/tests/test_deployment_verification_unit.py battery_growth/tests/test_deployment_contract.py scripts/verify.ps1 scripts/verify.sh
git commit -m "test: add executable deployment verification"
```

### Task 4: Modular dashboard bundle and AI cache semantics

**Files:**
- Create: `battery_growth/public/js/battery_growth_dashboard.bundle.js`
- Create: `battery_growth/public/js/dashboard/utils.js`
- Create: `battery_growth/public/js/dashboard/dom.js`
- Create: `battery_growth/public/js/dashboard/charts.js`
- Create: `battery_growth/public/js/dashboard/controller.js`
- Create: `battery_growth/tests/test_dashboard_modules.js`
- Modify: `battery_growth/battery_growth/page/battery_growth_dashboard/battery_growth_dashboard.js`
- Modify: `battery_growth/tests/test_dashboard_page_contract.js`
- Modify: `package.json`

**Interfaces:**
- Consumes: unchanged dashboard API methods and Frappe Page lifecycle.
- Produces: `globalThis.batteryGrowthDashboard.create(wrapper) -> BatteryGrowthDashboard`; pure helpers `text`, `number`, `clampPercent`, `isDashboardPayload`, and `briefForce(hasRenderedBrief)`; page entry lazy-loads `battery_growth_dashboard.bundle.js` via `frappe.require`.

- [ ] **Step 1: Write failing module and cache-semantic tests**

```javascript
assert.equal(modules.utils.text(null), "");
assert.equal(modules.utils.clampPercent(120), 100);
assert.equal(modules.utils.isDashboardPayload({ periods: [] }), true);
assert.equal(modules.utils.briefForce(false), 0);
assert.equal(modules.utils.briefForce(true), 1);
```

Extend the browser contract so the first brief call asserts `force === 0`, the button initially says “生成简报”, a second click after rendering asserts `force === 1` and says “重新生成”, and any KPI refresh returns the brief to the first-generation state.

- [ ] **Step 2: Run Node tests and observe missing modules/incorrect force**

Run:

```powershell
node battery_growth/tests/test_dashboard_modules.js
node battery_growth/tests/test_dashboard_page_contract.js
```

Expected: module test fails because files are absent; page contract fails because production always sends `force: 1`.

- [ ] **Step 3: Move focused responsibilities into bundle modules**

Use small IIFEs that register under `globalThis.BatteryGrowthDashboardModules`, allowing both Frappe's bundler and dependency-free VM tests. `utils.js` owns coercion/schema/presentation helpers; `dom.js` owns safe text-only element, panel, KPI, distribution, empty/error, and brief rendering; `charts.js` owns Frappe Chart configuration/destruction; `controller.js` owns filters, API calls, request serials, refresh timer, fullscreen, and lifecycle. The bundle imports modules in dependency order and exposes only `create`.

- [ ] **Step 4: Replace the Page file with the lazy lifecycle adapter**

```javascript
frappe.pages[PAGE_NAME].on_page_load = (wrapper) => {
  wrapper.batteryGrowthDashboardLoading = frappe
    .require("battery_growth_dashboard.bundle.js")
    .then(() => {
      wrapper.batteryGrowthDashboard?.destroy();
      wrapper.batteryGrowthDashboard = globalThis.batteryGrowthDashboard.create(wrapper);
    });
};
```

`on_page_show` awaits the loading promise before calling `show()`. The controller tracks `hasRenderedBrief`; first generation sends `force: 0`, a displayed brief enables `force: 1`, and every filter/data refresh invalidates the brief.

- [ ] **Step 5: Run module, browser, lint, and format checks**

Run:

```powershell
node battery_growth/tests/test_dashboard_modules.js
node battery_growth/tests/test_dashboard_page_contract.js
yarn lint
yarn format:check
```

Expected: PASS.

- [ ] **Step 6: Commit the dashboard change**

```powershell
git add battery_growth/public battery_growth/battery_growth/page/battery_growth_dashboard/battery_growth_dashboard.js battery_growth/tests/test_dashboard_modules.js battery_growth/tests/test_dashboard_page_contract.js package.json
git commit -m "refactor: modularize dashboard and honor insight cache"
```

### Task 5: CI contracts and full Docker workflow

**Files:**
- Modify: `.github/workflows/quality.yml`
- Create: `.github/workflows/docker-verification.yml`
- Modify: `battery_growth/tests/test_deployment_contract.py`

**Interfaces:**
- Consumes: all commands from Tasks 1–4.
- Produces: push/PR lightweight checks and manual/tagged full empty-volume verification with sanitized diagnostic artifacts.

- [ ] **Step 1: Add failing workflow contract assertions**

```python
def test_ci_initializes_submodule_and_runs_new_contracts(self):
    quality = read(".github/workflows/quality.yml")
    docker = read(".github/workflows/docker-verification.yml")
    self.assertIn("submodules: recursive", quality)
    self.assertIn("test_deployment_contract", quality)
    self.assertIn("workflow_dispatch:", docker)
    self.assertIn("scripts/verify.sh", docker)
    self.assertNotIn(".env\n", artifact_paths(docker))
```

- [ ] **Step 2: Run the focused test and observe missing workflow coverage**

Run: `python -m unittest battery_growth.tests.test_deployment_contract -v`

Expected: FAIL because the current checkout omits submodules and no full Docker workflow exists.

- [ ] **Step 3: Update lightweight CI and add manual/tag workflow**

Quality CI checks out submodules, validates Compose with `.env.example`, runs deployment/verification unit tests and both Node suites, parses all shell scripts, and retains existing Ruff/Prettier/ESLint/JSON checks. Docker CI triggers on `workflow_dispatch` and `v*` tags, copies `.env.example`, runs `scripts/up.sh`, `scripts/verify.sh`, repeats `up`, checks the count again, performs `down`/`up`, verifies persistence, and uploads only output from `scripts/logs.sh` on failure.

- [ ] **Step 4: Run workflow contract and local lightweight parity**

Run:

```powershell
python -m unittest discover -s battery_growth/tests -t . -v
node battery_growth/tests/test_dashboard_modules.js
node battery_growth/tests/test_dashboard_page_contract.js
ruff check battery_growth
ruff format --check battery_growth
yarn lint
yarn format:check
```

Expected: PASS.

- [ ] **Step 5: Commit CI changes**

```powershell
git add .github battery_growth/tests/test_deployment_contract.py
git commit -m "ci: add deployment and full Docker verification"
```

### Task 6: Deployment, verification, and interview documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-09-battery-growth-complete-project-design.md`
- Create: `docs/deployment/docker.md`
- Create: `docs/deployment/troubleshooting.md`
- Create: `docs/verification/2026-09-09-local-verification.md`
- Create: `docs/interview-guide.md`

**Interfaces:**
- Consumes: exact commands, limitations, and results from Tasks 1–5.
- Produces: clone-to-running quick starts, command reference, lifecycle/destructive-action explanation, honest verification record, and an interview narrative tied to implemented behavior.

- [ ] **Step 1: Write documentation checks into the deployment contract**

Assert README places Windows `./scripts/up.ps1` and Linux `./scripts/up.sh` before Bench setup, all documented routes use `http://battery.localhost:8080`, reset warnings name the confirmation flag, and the verification record contains fields for date, host, Frappe version, App revision, clean start, repeat start, persistence, Bench tests, and screenshots.

- [ ] **Step 2: Run the focused test and observe outdated README failures**

Run: `python -m unittest battery_growth.tests.test_deployment_contract -v`

Expected: FAIL because Docker is not yet the primary quick start.

- [ ] **Step 3: Rewrite the operational documentation**

Document Docker Desktop/WSL2 and Linux prerequisites, pinned upstream rationale, BuildKit secret and OCI revision label, one-command flows, safe `down`, destructive `reset`, diagnostic commands, immutable-image behavior, standard Bench fallback, architecture/data flow, and non-production scope. Update the design status to “已批准并实施”.

- [ ] **Step 4: Record only observed verification results**

Populate the local verification document with command, exit status, relevant version/count output, environment limitation, and timestamp. Mark Docker or browser rows “未运行：主机缺少 Docker/可用 Bench” instead of claiming success when unavailable.

- [ ] **Step 5: Run link/text contracts and format checks**

Run:

```powershell
python -m unittest battery_growth.tests.test_deployment_contract -v
git diff --check
```

Expected: PASS.

- [ ] **Step 6: Commit documentation**

```powershell
git add README.md docs battery_growth/tests/test_deployment_contract.py
git commit -m "docs: add reproducible deployment and interview guide"
```

### Task 7: Fresh verification, release evidence, and immutable tag

**Files:**
- Modify: `docs/verification/2026-09-09-local-verification.md`
- Update only after real browser verification: `docs/screenshots/operations-dashboard.png`

**Interfaces:**
- Consumes: clean committed branch and all lifecycle/verification tooling.
- Produces: reproducible command evidence and, only after every required gate passes, tag `v1.0.0-interview`.

- [ ] **Step 1: Run the complete dependency-light suite from a clean checkout**

```powershell
python -m unittest discover -s battery_growth/tests -t . -v
node battery_growth/tests/test_dashboard_modules.js
node battery_growth/tests/test_dashboard_page_contract.js
ruff check battery_growth
ruff format --check battery_growth
yarn lint
yarn format:check
git diff --check
```

Expected: all commands PASS.

- [ ] **Step 2: Run fresh Docker acceptance where Docker Engine is available**

```powershell
./scripts/reset.ps1 -Force
./scripts/up.ps1
./scripts/verify.ps1
./scripts/up.ps1
./scripts/verify.ps1 -SkipBenchTests
./scripts/down.ps1
./scripts/up.ps1 -SkipBuild
./scripts/verify.ps1 -SkipBenchTests
```

Expected: first run creates 240 Mock rows, second run remains at 240, and down/up preserves the site and count.

- [ ] **Step 3: Perform real Frappe browser checks**

At 1920×1080, 1366×768, and narrow mobile emulation, log in to the real Desk, verify subscription list/form, report filters/summary/chart/drill-down, dashboard filters/KPIs/charts/first cached brief/forced regeneration/fullscreen/error/empty states, and absence of horizontal scroll. Replace the dashboard screenshot only with the real route and Mock data.

- [ ] **Step 4: Record exact evidence and re-run the final gate**

Update the verification record with actual outputs and screenshot viewport metadata. Re-run Task 7 Step 1 plus `scripts/verify` after any evidence-file change.

- [ ] **Step 5: Push and tag only after all required gates pass**

```powershell
git push origin feature/battery-growth
git tag -a v1.0.0-interview -m "Battery Growth interview release"
git push origin v1.0.0-interview
```

If Docker or real-browser acceptance cannot run on the current host, stop before the tag, leave the branch with honest evidence, and report the exact remaining command sequence.
