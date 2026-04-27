param(
    [switch]$StopWorkbench
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "remote_access_common.ps1")

$context = Get-QuickTunnelContext
$projectDir = $context.projectDir
$statePath = $context.statePath

if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Encoding utf8 -Raw $statePath | ConvertFrom-Json
    if ($state.pid) {
        $process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $state.pid -Force
            Write-Output "[remote-access] stopped Quick Tunnel, pid=$($state.pid)"
        }
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
} else {
    Write-Output "[remote-access] Quick Tunnel was not running."
}

$orphanProcess = Find-CloudflaredProcessByCommandFragments -Fragments @("tunnel", "--url", "http://127.0.0.1:8767")
if ($null -ne $orphanProcess) {
    Stop-Process -Id $orphanProcess.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Output "[remote-access] stopped stale Quick Tunnel process, pid=$($orphanProcess.ProcessId)"
}

if ($StopWorkbench) {
    Push-Location $projectDir
    try {
        & python run_public_workbench.py stop
    } finally {
        Pop-Location
    }
}
