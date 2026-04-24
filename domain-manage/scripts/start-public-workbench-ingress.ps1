param(
    [string]$TunnelToken = "",
    [string]$Hostname = "hi.openwaifu-agent.uk",
    [string]$CloudflaredPath = "",
    [int]$ReadyTimeoutSeconds = 90,
    [int]$MetricsPort = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Resolve-CloudflaredPath {
    param(
        [string]$PreferredPath
    )

    if ($PreferredPath) {
        return $PreferredPath
    }

    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $fallback = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path -LiteralPath $fallback) {
        return $fallback
    }

    throw "cloudflared was not found."
}

function Invoke-WithNormalizedPathEnvironment {
    param(
        [scriptblock]$Action
    )

    $processPath = [Environment]::GetEnvironmentVariable("Path", "Process")
    $processPATH = [Environment]::GetEnvironmentVariable("PATH", "Process")

    if ($processPath -and $processPATH) {
        [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
    }

    try {
        & $Action
    } finally {
        if ($processPath -and $processPATH) {
            [Environment]::SetEnvironmentVariable("PATH", $processPATH, "Process")
        }
    }
}

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

function Get-PublicEndpointStatus {
    param(
        [string]$Url
    )

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $request = $null

    try {
        $client.Timeout = [TimeSpan]::FromSeconds(5)
        $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $Url)
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        return [int]$response.StatusCode
    } catch {
        return 0
    } finally {
        if ($request) {
            $request.Dispose()
        }
        $client.Dispose()
        $handler.Dispose()
    }
}

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    try {
        return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    } finally {
        $listener.Stop()
    }
}

function Get-CloudflaredReadyState {
    param(
        [string]$ReadyUrl
    )

    try {
        $response = Invoke-RestMethod -Uri $ReadyUrl -UseBasicParsing -TimeoutSec 5
        $readyConnections = 0
        if ($null -ne $response.readyConnections) {
            $readyConnections = [int]$response.readyConnections
        }

        return [pscustomobject]@{
            Ready = ([int]$response.status -eq 200 -and $readyConnections -gt 0)
            ReadyConnections = $readyConnections
        }
    } catch {
        return [pscustomobject]@{
            Ready = $false
            ReadyConnections = 0
        }
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$workspaceDir = Split-Path -Parent $projectDir
$agentDir = Join-Path $workspaceDir "openwaifu-agent"
$runtimeDir = Join-Path $projectDir "runtime\public_workbench_ingress"
$statePath = Join-Path $runtimeDir "cloudflared.state.json"
$stdoutPath = Join-Path $runtimeDir "cloudflared.stdout.log"
$stderrPath = Join-Path $runtimeDir "cloudflared.stderr.log"

if (-not (Test-Path -LiteralPath (Join-Path $agentDir "run_public_workbench.py"))) {
    throw "Missing sibling project: $agentDir"
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

if (Test-Path -LiteralPath $statePath) {
    $existingState = Get-Content -Encoding utf8 -Raw $statePath | ConvertFrom-Json
    if ($existingState.pid -and (Get-Process -Id $existingState.pid -ErrorAction SilentlyContinue)) {
        Write-Host "[workbench-ingress] cloudflared is already running, pid=$($existingState.pid)"
        Write-Host "[workbench-ingress] hostname=$($existingState.hostname)"
        Write-Host "[workbench-ingress] state=$statePath"
        exit 0
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
}

Push-Location $agentDir
try {
    & python run_public_workbench.py --no-open-browser | Out-Null
} finally {
    Pop-Location
}

if (-not $TunnelToken) {
    $runtimeJson = & node (Join-Path $scriptDir "get-public-workbench-runtime.mjs")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to fetch Cloudflare Tunnel runtime."
    }
    $runtime = $runtimeJson | ConvertFrom-Json
    $TunnelToken = [string]$runtime.tunnelToken
    $Hostname = [string]$runtime.hostname
}

if (-not $TunnelToken) {
    throw "Missing tunnel token."
}

$resolvedMetricsPort = $MetricsPort
if ($resolvedMetricsPort -le 0) {
    $resolvedMetricsPort = Get-FreeTcpPort
}

$metricsUrl = "http://127.0.0.1:$resolvedMetricsPort/ready"
$resolvedCloudflaredPath = Resolve-CloudflaredPath -PreferredPath $CloudflaredPath
$process = Invoke-WithCloudflaredEnvironment {
    Invoke-WithNormalizedPathEnvironment {
        Start-Process `
            -FilePath $resolvedCloudflaredPath `
            -ArgumentList @("tunnel", "--metrics", "127.0.0.1:$resolvedMetricsPort", "run", "--token", $TunnelToken) `
            -WorkingDirectory $projectDir `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -WindowStyle Hidden `
            -PassThru
    }
}

@{
    pid = $process.Id
    hostname = $Hostname
    metricsPort = $resolvedMetricsPort
    metricsUrl = $metricsUrl
    stdoutPath = $stdoutPath
    stderrPath = $stderrPath
    startedAt = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $statePath

$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
$publicUrl = "https://$Hostname/api/healthz"
$ready = $false
$publicStatusCode = 0
$readyConnections = 0

while ((Get-Date) -lt $deadline) {
    $process.Refresh()
    if ($process.HasExited) {
        break
    }

    $readyState = Get-CloudflaredReadyState -ReadyUrl $metricsUrl
    $readyConnections = [int]$readyState.ReadyConnections
    $publicStatusCode = Get-PublicEndpointStatus -Url $publicUrl

    if ($readyState.Ready -and $publicStatusCode -gt 0) {
        $ready = $true
        break
    }

    Start-Sleep -Seconds 1
}

if (-not $ready) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    throw "Cloudflare Tunnel did not become reachable within ${ReadyTimeoutSeconds}s."
}

Write-Host "[workbench-ingress] public workbench local url=http://127.0.0.1:8767"
Write-Host "[workbench-ingress] public hostname=https://$Hostname/"
Write-Host "[workbench-ingress] cloudflared pid=$($process.Id)"
Write-Host "[workbench-ingress] metrics=$metricsUrl"
Write-Host "[workbench-ingress] readyConnections=$readyConnections"
Write-Host "[workbench-ingress] state=$statePath"
Write-Host "[workbench-ingress] stdout=$stdoutPath"
Write-Host "[workbench-ingress] stderr=$stderrPath"
