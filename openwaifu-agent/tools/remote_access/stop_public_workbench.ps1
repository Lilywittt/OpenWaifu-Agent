param(
    [switch]$StopWorkbench,
    [string]$ConfigPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent (Split-Path -Parent $scriptDir)
. (Join-Path $PSScriptRoot "remote_access_common.ps1")
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $scriptDir "cloudflared.public_workbench.local.yml"
}
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

$orphanProcess = Find-CloudflaredProcessByCommandFragments -Fragments @("tunnel", "--config", $ConfigPath, "run")
if ($null -ne $orphanProcess) {
    Stop-Process -Id $orphanProcess.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[remote-access] stopped stale cloudflared process, pid=$($orphanProcess.ProcessId)"
}

if ($StopWorkbench) {
    Push-Location $projectDir
    try {
        & python run_public_workbench.py stop
    } finally {
        Pop-Location
    }
}
