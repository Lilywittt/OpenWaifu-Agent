param(
    [string]$CloudflaredPath = "",
    [int]$ReadyTimeoutSeconds = 30
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

$context = Get-QuickTunnelContext
$projectDir = $context.projectDir
$logsDir = $context.logsDir
$stateDir = $context.stateDir
$statePath = $context.statePath
$stdoutPath = $context.stdoutPath
$stderrPath = $context.stderrPath
$urlPattern = $context.urlPattern

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -Encoding utf8 -Raw $statePath | ConvertFrom-Json
    if ($state.pid) {
        $running = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
        if ($running) {
            $publicUrl = ""
            if ($null -ne $state.publicUrl) {
                $publicUrl = [string]$state.publicUrl
            }
            if (-not $publicUrl) {
                foreach ($logPath in @($stdoutPath, $stderrPath)) {
                    if (-not (Test-Path -LiteralPath $logPath)) {
                        continue
                    }
                    $content = Get-Content -Encoding utf8 -Raw $logPath
                    if ([string]::IsNullOrWhiteSpace($content)) {
                        continue
                    }
                    $match = [regex]::Match($content, $urlPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
                    if ($match.Success) {
                        $publicUrl = $match.Value
                        $state.publicUrl = $publicUrl
                        ($state | ConvertTo-Json -Depth 4) | Set-Content -Encoding utf8 $statePath
                        break
                    }
                }
            }
            if ($publicUrl) {
                Write-Output "[remote-access] Quick Tunnel is already running: $publicUrl"
                Write-Output "[remote-access] state=$statePath"
                exit 0
            } else {
                Stop-Process -Id $state.pid -Force
                Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
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

$process = Invoke-WithCloudflaredEnvironment {
    Start-Process -FilePath $CloudflaredPath -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8767", "--protocol", "http2") -WorkingDirectory $projectDir -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -WindowStyle Hidden -PassThru
}

$initialState = @{
    pid = $process.Id
    stdoutPath = $stdoutPath
    stderrPath = $stderrPath
    publicUrl = ""
    startedAt = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 4
$initialState | Set-Content -Encoding utf8 $statePath

$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
$publicUrl = ""

while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        break
    }

    foreach ($logPath in @($stdoutPath, $stderrPath)) {
        if (-not (Test-Path -LiteralPath $logPath)) {
            continue
        }
        $content = Get-Content -Encoding utf8 -Raw $logPath
        if ([string]::IsNullOrWhiteSpace($content)) {
            continue
        }
        $match = [regex]::Match($content, $urlPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($match.Success) {
            $publicUrl = $match.Value
            break
        }
    }

    if ($publicUrl) {
        break
    }

    Start-Sleep -Milliseconds 500
}

if (-not $publicUrl) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    throw ("Quick Tunnel failed. No trycloudflare URL was detected within {0}s. stdout={1} stderr={2}" -f $ReadyTimeoutSeconds, $stdoutPath, $stderrPath)
}

$readyState = @{
    pid = $process.Id
    stdoutPath = $stdoutPath
    stderrPath = $stderrPath
    publicUrl = $publicUrl
    startedAt = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 4
$readyState | Set-Content -Encoding utf8 $statePath

Write-Output "[remote-access] public workbench is running at http://127.0.0.1:8767"
Write-Output "[remote-access] Quick Tunnel URL: $publicUrl"
Write-Output "[remote-access] cloudflared pid=$($process.Id)"
Write-Output "[remote-access] state=$statePath"
Write-Output "[remote-access] stdout=$stdoutPath"
Write-Output "[remote-access] stderr=$stderrPath"
