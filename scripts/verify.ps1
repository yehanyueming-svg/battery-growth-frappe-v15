param(
    [switch]$SkipBenchTests
)

. (Join-Path $PSScriptRoot "common.ps1")

Write-BatteryStage "verification"
Assert-BatteryCommand "git"
Assert-BatteryCommand "docker"
$revision = (& git -C $script:RepositoryRoot rev-parse HEAD).Trim()
$imageReference = Get-BatteryImageReference
$imageRevision = (& docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' $imageReference).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect image '$imageReference'. Run ./scripts/up.ps1 first."
}
if ($imageRevision -ne $revision) {
    throw "Image revision mismatch: expected $revision, found $imageRevision."
}

$siteName = Get-BatteryEnvValue -Name "SITE_NAME" -Default "battery.localhost"
$frappeVersion = (Get-BatteryEnvValue -Name "FRAPPE_VERSION" -Default "v15.120.0").TrimStart("v")
Invoke-BatteryCompose exec -T backend bench --site $siteName execute battery_growth.setup.verification.assert_deployment --kwargs "{'expected_frappe_version': '$frappeVersion', 'expected_mock_count': 240}"

if (-not $SkipBenchTests) {
    Invoke-BatteryCompose exec -T backend bench --site $siteName set-config --parse allow_tests True
    try {
        Invoke-BatteryCompose exec -T backend bench --site $siteName run-tests --app battery_growth
    } finally {
        Invoke-BatteryCompose exec -T backend bench --site $siteName set-config --parse allow_tests False
    }
} else {
    Write-Host "Skipping Bench tests by request."
}

$port = [int](Get-BatteryEnvValue -Name "HTTP_PUBLISH_PORT" -Default "8080")
$routes = @(
    "/api/method/ping",
    "/login",
    "/app/service-subscription",
    "/app/query-report/User%20Growth%20Analysis",
    "/app/battery-growth-dashboard",
    "/app/growth-ai-settings"
)
foreach ($route in $routes) {
    $uri = "http://127.0.0.1:$port$route"
    $response = Invoke-WebRequest -UseBasicParsing -Uri $uri -Headers @{ Host = $siteName } -TimeoutSec 20
    if ($response.StatusCode -ge 400) {
        throw "Route verification failed for $route with HTTP $($response.StatusCode)."
    }
    if ($route -eq "/api/method/ping" -and $response.Content -notmatch "pong") {
        throw "Ping route returned HTTP 200 without the expected pong response."
    }
    Write-Host "OK $($response.StatusCode) $route"
}

Write-Host "Deployment verification passed for image revision $revision."
