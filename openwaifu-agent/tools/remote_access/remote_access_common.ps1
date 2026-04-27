Set-StrictMode -Version Latest

function Get-RemoteAccessProjectDir {
    $scriptDir = Split-Path -Parent $PSScriptRoot
    return (Split-Path -Parent $scriptDir)
}

function Get-QuickTunnelContext {
    $projectDir = Get-RemoteAccessProjectDir
    $logsDir = Join-Path $projectDir "runtime\service_logs\remote_access"
    $stateDir = Join-Path $projectDir "runtime\service_state\shared\remote_access"

    [ordered]@{
        projectDir = $projectDir
        logsDir = $logsDir
        stateDir = $stateDir
        statePath = Join-Path $stateDir "cloudflared_public_workbench_quick.json"
        stdoutPath = Join-Path $logsDir "cloudflared.public_workbench.quick.stdout.log"
        stderrPath = Join-Path $logsDir "cloudflared.public_workbench.quick.stderr.log"
        urlPattern = 'https://[-a-z0-9]+\.trycloudflare\.com'
    }
}

function Find-CloudflaredProcessByCommandFragments {
    param(
        [string[]]$Fragments
    )

    $processes = Get-CimInstance Win32_Process -Filter "name='cloudflared.exe'" -ErrorAction SilentlyContinue
    if (-not $processes) {
        $processes = Get-CimInstance Win32_Process -Filter "name='cloudflared'" -ErrorAction SilentlyContinue
    }

    foreach ($process in $processes) {
        $commandLine = [string]$process.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) {
            continue
        }
        $matched = $true
        foreach ($fragment in $Fragments) {
            if (-not $commandLine.Contains($fragment)) {
                $matched = $false
                break
            }
        }
        if ($matched) {
            return $process
        }
    }

    return $null
}

function Resolve-QuickTunnelUrlFromLogs {
    param(
        [hashtable]$Context
    )

    foreach ($logPath in @($Context.stdoutPath, $Context.stderrPath)) {
        if (-not (Test-Path -LiteralPath $logPath)) {
            continue
        }
        $content = Get-Content -Encoding utf8 -Raw $logPath
        if ([string]::IsNullOrWhiteSpace($content)) {
            continue
        }
        $match = [regex]::Match($content, $Context.urlPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($match.Success) {
            return $match.Value
        }
    }

    return ""
}

function Read-QuickTunnelState {
    param(
        [switch]$RefreshFromLogs
    )

    $context = Get-QuickTunnelContext
    if (-not (Test-Path -LiteralPath $context.statePath)) {
        return $null
    }

    $state = Get-Content -Encoding utf8 -Raw $context.statePath | ConvertFrom-Json
    $process = $null
    if ($state.pid) {
        $process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
    }

    if ($RefreshFromLogs -and [string]::IsNullOrWhiteSpace([string]$state.publicUrl)) {
        $resolvedUrl = Resolve-QuickTunnelUrlFromLogs -Context $context
        if ($resolvedUrl) {
            $state.publicUrl = $resolvedUrl
            ($state | ConvertTo-Json -Depth 4) | Set-Content -Encoding utf8 $context.statePath
        }
    }

    [pscustomobject]@{
        pid = $state.pid
        processAlive = [bool]$process
        publicUrl = [string]$state.publicUrl
        startedAt = [string]$state.startedAt
        stdoutPath = [string]$state.stdoutPath
        stderrPath = [string]$state.stderrPath
        statePath = $context.statePath
    }
}

function Test-QuickTunnelPublicUrl {
    param(
        [string]$PublicUrl
    )

    if ([string]::IsNullOrWhiteSpace($PublicUrl)) {
        return $null
    }

    $originalProgressPreference = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    try {
        $httpCode = & curl.exe -I -s -o NUL -w "%{http_code}" --max-time 10 $PublicUrl
        if ($LASTEXITCODE -ne 0) {
            return [pscustomobject]@{
                ok = $false
                code = ""
            }
        }

        $code = ([string]$httpCode).Trim()
        $healthy = -not [string]::IsNullOrWhiteSpace($code) -and $code -ne "000" -and $code -ne "530"
        return [pscustomobject]@{
            ok = $healthy
            code = $code
        }
    } finally {
        $ProgressPreference = $originalProgressPreference
    }
}

function Write-QuickTunnelStatus {
    param(
        [psobject]$State
    )

    if ($null -eq $State) {
        Write-Output "[remote-access] Quick Tunnel is not running."
        return
    }

    if (-not $State.processAlive) {
        Write-Output "[remote-access] Quick Tunnel state exists but the process is gone."
        Write-Output "[remote-access] state=$($State.statePath)"
        return
    }

    Write-Output "[remote-access] Quick Tunnel is running."
    if ($State.publicUrl) {
        Write-Output "[remote-access] publicUrl=$($State.publicUrl)"
        $health = Test-QuickTunnelPublicUrl -PublicUrl $State.publicUrl
        if ($null -ne $health) {
            if ($health.ok) {
                Write-Output "[remote-access] publicHealth=ok (http=$($health.code))"
            } else {
                Write-Output "[remote-access] publicHealth=bad (http=$($health.code))"
            }
        }
    }
    Write-Output "[remote-access] pid=$($State.pid)"
    Write-Output "[remote-access] state=$($State.statePath)"
    Write-Output "[remote-access] stdout=$($State.stdoutPath)"
    Write-Output "[remote-access] stderr=$($State.stderrPath)"
}
