param(
    [ValidateRange(1, 5000)][int]$Tail = 200
)

. (Join-Path $PSScriptRoot "common.ps1")

function Protect-BatteryLogText {
    param([Parameter(Mandatory = $true)][string]$Text)
    foreach ($name in @("DB_PASSWORD", "ADMIN_PASSWORD")) {
        $value = Get-BatteryEnvValue -Name $name
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $Text = $Text -replace [regex]::Escape($value), "[REDACTED]"
        }
    }
    $Text = $Text -replace '(?i)(api[_-]?key|authorization)(["''=: ]+)\S+', '$1$2[REDACTED]'
    return $Text
}

Write-BatteryStage "services"
$composeArguments = @("compose", "--project-name", $script:ComposeProject, "--env-file", $script:EnvironmentFile)
foreach ($file in $script:ComposeFiles) {
    $composeArguments += @("--file", $file)
}
$status = (& docker @composeArguments ps 2>&1 | Out-String)
Write-Output (Protect-BatteryLogText -Text $status)

Write-BatteryStage "health"
$health = (& docker ps --filter "label=com.docker.compose.project=$script:ComposeProject" --format "table {{.Names}}`t{{.Status}}" 2>&1 | Out-String)
Write-Output (Protect-BatteryLogText -Text $health)

Write-BatteryStage "logs"
$logs = (& docker @composeArguments logs --no-color --tail $Tail 2>&1 | Out-String)
Write-Output (Protect-BatteryLogText -Text $logs)
