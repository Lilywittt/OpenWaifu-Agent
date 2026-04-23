param(
    [switch]$StopWorkbench
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent (Split-Path -Parent $scriptDir)
$statePath = Join-Path $projectDir "runtime\service_state\shared\remote_access\cloudflared_public_workbench.json"

if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Encoding utf8 -Raw $statePath | ConvertFrom-Json
    if ($state.pid) {
        $process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $state.pid -Force
            Write-Host "[remote-access] stopped cloudflared, pid=$($state.pid)"
        }
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
}

if ($StopWorkbench) {
    Push-Location $projectDir
    try {
        & python run_public_workbench.py stop
    } finally {
        Pop-Location
    }
}
