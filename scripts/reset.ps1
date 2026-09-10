param(
    [switch]$Force
)

. (Join-Path $PSScriptRoot "common.ps1")

if (-not $Force) {
    throw "Reset deletes the battery-growth database, site files, and logs. Re-run with -Force to confirm."
}

Write-BatteryStage "environment"
Assert-BatteryCommand "docker"
Assert-BatteryVolumeOwnership

Write-BatteryStage "services"
Invoke-BatteryCompose down --volumes --remove-orphans
Write-Host "Removed only the validated battery-growth containers, network, and named volumes."
