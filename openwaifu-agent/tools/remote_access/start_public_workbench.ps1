param(
    [string]$ConfigPath = "",
    [string]$CloudflaredPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "remote_access_common.ps1")

function Invoke-WithCloudflaredEnvironment {
    param(
        [scriptblock]$Action
    )

    $proxyEnvKeys = @(
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy"
    )
    $saved = @{}
    foreach ($key in $proxyEnvKeys) {
        $saved[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
    }

    foreach ($key in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")) {
        [Environment]::SetEnvironmentVariable($key, "", "Process")
    }
    foreach ($key in @("NO_PROXY", "no_proxy")) {
        [Environment]::SetEnvironmentVariable($key, "127.0.0.1,localhost", "Process")
    }

    try {
        & $Action
    } finally {
        foreach ($key in $proxyEnvKeys) {
            if ($null -eq $saved[$key]) {
                [Environment]::SetEnvironmentVariable($key, $null, "Process")
            } else {
                [Environment]::SetEnvironmentVariable($key, $saved[$key], "Process")
            }
        }
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent (Split-Path -Parent $scriptDir)

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $scriptDir "cloudflared.public_workbench.local.yml"
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Missing cloudflared config: $ConfigPath`nCopy tools/remote_access/cloudflared.public_workbench.example.yml and create your own .local file first."
}

$logsDir = Join-Path $projectDir "runtime\service_logs\remote_access"
$stateDir = Join-Path $projectDir "runtime\service_state\shared\remote_access"
$statePath = Join-Path $stateDir "cloudflared_public_workbench.json"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Encoding utf8 -Raw $statePath | ConvertFrom-Json
    if ($state.pid -and (Get-Process -Id $state.pid -ErrorAction SilentlyContinue)) {
        Write-Host "[remote-access] cloudflared is already running, pid=$($state.pid)"
        exit 0
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
}

$orphanProcess = Find-CloudflaredProcessByCommandFragments -Fragments @("tunnel", "--config", $ConfigPath, "run")
if ($null -ne $orphanProcess) {
    Stop-Process -Id $orphanProcess.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[remote-access] stopped stale cloudflared process, pid=$($orphanProcess.ProcessId)"
}

Push-Location $projectDir
try {
    & python run_public_workbench.py --no-open-browser | Out-Null
} finally {
    Pop-Location
}

if (-not $CloudflaredPath) {
    $cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cloudflaredCommand) {
        $CloudflaredPath = $cloudflaredCommand.Source
    } else {
        $fallbackPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
        if (Test-Path -LiteralPath $fallbackPath) {
            $CloudflaredPath = $fallbackPath
        } else {
            throw "cloudflared was not found. Install Cloudflare.cloudflared or pass -CloudflaredPath explicitly."
        }
    }
}

$stdoutPath = Join-Path $logsDir "cloudflared.public_workbench.stdout.log"
$stderrPath = Join-Path $logsDir "cloudflared.public_workbench.stderr.log"
$process = Invoke-WithCloudflaredEnvironment {
    Start-Process `
        -FilePath $CloudflaredPath `
        -ArgumentList @("tunnel", "--config", $ConfigPath, "run") `
        -WorkingDirectory $projectDir `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -WindowStyle Hidden `
        -PassThru
}

$statePayload = @{
    pid = $process.Id
    configPath = $ConfigPath
    stdoutPath = $stdoutPath
    stderrPath = $stderrPath
    startedAt = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 4
$statePayload | Set-Content -Encoding utf8 $statePath

Write-Host "[remote-access] public workbench is running at http://127.0.0.1:8767"
Write-Host "[remote-access] cloudflared pid=$($process.Id)"
Write-Host "[remote-access] stdout=$stdoutPath"
Write-Host "[remote-access] stderr=$stderrPath"
