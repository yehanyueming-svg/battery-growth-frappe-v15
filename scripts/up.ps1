param(
    [switch]$SkipBuild
)

. (Join-Path $PSScriptRoot "common.ps1")

Write-BatteryStage "prerequisites"
Assert-BatteryCommand "git"
Assert-BatteryCommand "docker"
$serverVersionOutput = & docker version --format "{{.Server.Version}}" 2>$null
$serverVersionExitCode = $LASTEXITCODE
$serverVersionText = $serverVersionOutput | Select-Object -First 1
if ($serverVersionExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($serverVersionText)) {
    throw "Docker Engine is not running. Start Docker Desktop or the Linux Docker service."
}
$serverVersion = [version](($serverVersionText -split "-")[0])
if ($serverVersion.Major -lt 23) {
    throw "Docker Engine 23 or newer is required for BuildKit secrets; found $serverVersionText."
}
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 is required."
}
$driveName = ([IO.Path]::GetPathRoot($script:RepositoryRoot)).TrimEnd("\\").TrimEnd(":")
$freeBytes = (Get-PSDrive -Name $driveName).Free
if ($freeBytes -lt 10GB) {
    throw "At least 10 GiB free disk space is required; found $([math]::Round($freeBytes / 1GB, 1)) GiB."
}
$port = [int](Get-BatteryEnvValue -Name "HTTP_PUBLISH_PORT" -Default "8080")
$portInUse = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
    Where-Object { $_.Port -eq $port }
if ($portInUse -and -not (Test-BatteryProjectFrontendRunning)) {
    throw "Port $port is already in use by another process. Change HTTP_PUBLISH_PORT in .env."
}

Write-BatteryStage "submodule"
$submodule = Join-Path $script:RepositoryRoot "deploy/frappe_docker"
if (-not (Test-Path -LiteralPath (Join-Path $submodule "compose.yaml"))) {
    & git -C $script:RepositoryRoot submodule update --init --depth 1 -- deploy/frappe_docker
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to initialize deploy/frappe_docker. Check Git and network access."
    }
}
$expectedUpstream = Get-BatteryEnvValue -Name "FRAPPE_DOCKER_REVISION" -Default "380b9d069ab949754fe78331af647b673984dc04"
$actualUpstream = (& git -C $submodule rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualUpstream -ne $expectedUpstream) {
    throw "frappe_docker revision mismatch: expected $expectedUpstream, found $actualUpstream."
}

Write-BatteryStage "environment"
Initialize-BatteryEnvironment
$siteName = Get-BatteryEnvValue -Name "SITE_NAME" -Default "battery.localhost"
$port = [int](Get-BatteryEnvValue -Name "HTTP_PUBLISH_PORT" -Default "8080")

Write-BatteryStage "build"
$revision = (& git -C $script:RepositoryRoot rev-parse HEAD).Trim()
if (-not $SkipBuild) {
    $dirty = & git -C $script:RepositoryRoot status --porcelain --untracked-files=no
    if ($dirty) {
        throw "Tracked files are dirty. Commit them before building the remote-source image."
    }
    $appRef = $env:BATTERY_GROWTH_APP_REF
    if (-not [string]::IsNullOrWhiteSpace($appRef)) {
        if ($appRef -notmatch '^[A-Za-z0-9._/-]+$' -or $appRef -ne $revision) {
            throw "BATTERY_GROWTH_APP_REF must be the current full commit revision for an exact CI build."
        }
    } else {
        $upstreamRevision = & git -C $script:RepositoryRoot rev-parse '@{upstream}' 2>$null
        if ($LASTEXITCODE -ne 0 -or $upstreamRevision.Trim() -ne $revision) {
            throw "HEAD must be pushed to its tracked branch before building the remote-source image."
        }
    }
    $frappeVersion = Get-BatteryEnvValue -Name "FRAPPE_VERSION" -Default "v15.120.0"
    $imageReference = Get-BatteryImageReference
    $builderImageReference = "${imageReference}-build"
    $appsJsonPath = Join-Path $script:RepositoryRoot "deploy/apps.json"
    $temporaryAppsJson = $null
    if (-not [string]::IsNullOrWhiteSpace($appRef)) {
        $appsDefinition = @(Get-Content -Raw -LiteralPath $appsJsonPath | ConvertFrom-Json)
        $appsDefinition[0].branch = $appRef
        $temporaryAppsJson = [IO.Path]::GetTempFileName()
        $json = ConvertTo-Json $appsDefinition -Depth 4
        [IO.File]::WriteAllText($temporaryAppsJson, $json, (New-Object Text.UTF8Encoding($false)))
        $appsJsonPath = $temporaryAppsJson
    }
    $buildArguments = @(
        "build",
        "--build-arg", "FRAPPE_BRANCH=$frappeVersion",
        "--build-arg", "CACHE_BUST=$revision",
        "--secret", "id=apps_json,src=$appsJsonPath",
        "--label", "org.opencontainers.image.revision=$revision",
        "--label", "org.opencontainers.image.source=https://github.com/yehanyueming-svg/battery-growth-frappe-v15",
        "--tag", $builderImageReference,
        "--file", (Join-Path $submodule "images/layered/Containerfile"),
        $submodule
    )
    try {
        & docker @buildArguments
        $buildExitCode = $LASTEXITCODE
    } finally {
        if ($temporaryAppsJson) {
            Remove-Item -LiteralPath $temporaryAppsJson -Force
        }
    }
    if ($buildExitCode -ne 0) {
        throw "Layered image build failed. Re-run ./scripts/logs.ps1 after services have started."
    }
    $runtimeBuildArguments = @(
        "build",
        "--build-arg", "SOURCE_IMAGE=$builderImageReference",
        "--label", "org.opencontainers.image.revision=$revision",
        "--label", "org.opencontainers.image.source=https://github.com/yehanyueming-svg/battery-growth-frappe-v15",
        "--tag", $imageReference,
        "--file", (Join-Path $script:RepositoryRoot "deploy/runtime.Containerfile"),
        (Join-Path $script:RepositoryRoot "deploy")
    )
    & docker @runtimeBuildArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime image normalization failed."
    }
} else {
    Write-Host "Skipping image build by request."
}

Write-BatteryStage "dependencies"
Invoke-BatteryCompose up "-d" db redis-cache redis-queue
Invoke-BatteryCompose up --no-deps --exit-code-from configurator configurator

Write-BatteryStage "site-init"
Invoke-BatteryCompose up --no-deps --exit-code-from site-init site-init

Write-BatteryStage "services"
Invoke-BatteryCompose up "-d" --no-deps backend websocket queue-short queue-long scheduler frontend

Write-BatteryStage "health"
$healthUri = "http://127.0.0.1:$port/api/method/ping"
$deadline = (Get-Date).AddMinutes(3)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUri -Headers @{ Host = $siteName } -TimeoutSec 5
        if ($response.StatusCode -eq 200 -and $response.Content -match 'pong') {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}
if (-not $healthy) {
    throw "Health check timed out. Run ./scripts/logs.ps1 for container status and redacted logs."
}

Write-Host "Battery Growth is ready at http://${siteName}:$port"
Write-Warning "Local demo login only: Administrator / admin. Do not reuse this password outside local evaluation."
Write-Host "Workspace: http://${siteName}:$port/app/battery-growth"
Write-Host "Subscriptions: http://${siteName}:$port/app/service-subscription"
Write-Host "Report: http://${siteName}:$port/app/query-report/User%20Growth%20Analysis"
Write-Host "Dashboard: http://${siteName}:$port/app/battery-growth-dashboard"
Write-Host "AI settings: http://${siteName}:$port/app/growth-ai-settings"
