. (Join-Path $PSScriptRoot "common.ps1")

Write-BatteryStage "services"
Invoke-BatteryCompose down --remove-orphans
Write-Host "Services stopped. The battery-growth volumes and site data were preserved."
