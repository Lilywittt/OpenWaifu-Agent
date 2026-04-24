param(
    [switch]$StopWorkbench
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$workspaceDir = Split-Path -Parent $projectDir
$agentDir = Join-Path $workspaceDir "openwaifu-agent"
$statePath = Join-Path $projectDir "runtime\public_workbench_ingress\cloudflared.state.json"

if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Host "[workbench-ingress] nothing is running"
    exit 0
}

$state = Get-Content -Encoding utf8 -Raw $statePath | ConvertFrom-Json
if ($state.pid -and (Get-Process -Id $state.pid -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $state.pid -Force
    Write-Host "[workbench-ingress] stopped cloudflared pid=$($state.pid)"
} else {
    Write-Host "[workbench-ingress] cloudflared is already stopped"
}

Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue

if ($StopWorkbench) {
    if (-not (Test-Path -LiteralPath (Join-Path $agentDir "run_public_workbench.py"))) {
        throw "Missing sibling project: $agentDir"
    }

    Push-Location $agentDir
    try {
        & python run_public_workbench.py stop
    } finally {
        Pop-Location
    }
}
