$ErrorActionPreference = "Stop"

$script:RepositoryRoot = Split-Path -Parent $PSScriptRoot
$script:EnvironmentFile = Join-Path $script:RepositoryRoot ".env"
if (-not (Test-Path -LiteralPath $script:EnvironmentFile)) {
    $script:EnvironmentFile = Join-Path $script:RepositoryRoot ".env.example"
}
$script:ComposeProject = "battery-growth"
$script:ComposeFiles = @(
    (Join-Path $script:RepositoryRoot "deploy/frappe_docker/compose.yaml"),
    (Join-Path $script:RepositoryRoot "deploy/frappe_docker/overrides/compose.mariadb.yaml"),
    (Join-Path $script:RepositoryRoot "deploy/compose.override.yaml")
)
$script:ExpectedVolumes = @(
    "battery-growth-db",
    "battery-growth-sites",
    "battery-growth-logs"
)

function Write-BatteryStage {
    param([Parameter(Mandatory = $true)][string]$Name)
    Write-Host "`n[$Name]" -ForegroundColor Cyan
}
function Get-BatteryEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Default = ""
    )
    if (-not (Test-Path -LiteralPath $script:EnvironmentFile)) {
        return $Default
    }
    foreach ($line in Get-Content -LiteralPath $script:EnvironmentFile) {
        if ($line -match "^$([regex]::Escape($Name))=(.*)$") {
            return $Matches[1].Trim()
        }
    }
    return $Default
}

function Initialize-BatteryEnvironment {
    $target = Join-Path $script:RepositoryRoot ".env"
    if (-not (Test-Path -LiteralPath $target)) {
        Copy-Item -LiteralPath (Join-Path $script:RepositoryRoot ".env.example") -Destination $target
        Write-Host "Created .env from .env.example"
    }
    $script:EnvironmentFile = $target
}

function Assert-BatteryCommand {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

function Invoke-BatteryCompose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$RemainingArguments)
    $composeArguments = @("compose", "--project-name", $script:ComposeProject, "--env-file", $script:EnvironmentFile)
    foreach ($file in $script:ComposeFiles) {
        $composeArguments += @("--file", $file)
    }
    $composeArguments += $RemainingArguments
    & docker @composeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE. Run ./scripts/logs.ps1 for diagnostics."
    }
}

function Get-BatteryImageReference {
    $image = Get-BatteryEnvValue -Name "CUSTOM_IMAGE" -Default "battery-growth"
    $tag = Get-BatteryEnvValue -Name "CUSTOM_TAG" -Default "v15.120.0"
    return "${image}:${tag}"
}

function Test-BatteryProjectFrontendRunning {
    $container = & docker ps --filter "label=com.docker.compose.project=$script:ComposeProject" --filter "label=com.docker.compose.service=frontend" --format "{{.ID}}" 2>$null
    return ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($container | Out-String)))
}

function Assert-BatteryVolumeOwnership {
    foreach ($volume in $script:ExpectedVolumes) {
        & docker volume inspect $volume *> $null
        if ($LASTEXITCODE -ne 0) {
            continue
        }
        $project = & docker volume inspect --format '{{ index .Labels "com.docker.compose.project" }}' $volume
        if ($LASTEXITCODE -ne 0 -or $project.Trim() -ne $script:ComposeProject) {
            throw "Refusing reset: volume '$volume' is not owned by Compose project '$script:ComposeProject'."
        }
    }
}
