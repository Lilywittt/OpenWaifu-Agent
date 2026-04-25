Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Get-CloudflaredReadyState {
    param(
        [string]$ReadyUrl
    )

    if (-not $ReadyUrl) {
        return [pscustomobject]@{
            Ready = $false
            ReadyConnections = 0
        }
    }

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

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$workspaceDir = Split-Path -Parent $projectDir
$agentDir = Join-Path $workspaceDir "openwaifu-agent"
$runtimeProfilePath = Join-Path $projectDir "runtime\public_workbench_ingress\runtime.json"
$statePath = Join-Path $projectDir "runtime\public_workbench_ingress\cloudflared.state.json"

if (-not (Test-Path -LiteralPath (Join-Path $agentDir "run_public_workbench.py"))) {
    throw "Missing sibling project: $agentDir"
}

Push-Location $agentDir
try {
    & python run_public_workbench.py status
} finally {
    Pop-Location
}

if (Test-Path -LiteralPath $runtimeProfilePath) {
    $runtime = Get-Content -Encoding utf8 -Raw $runtimeProfilePath | ConvertFrom-Json
    Write-Host "[workbench-ingress] runtimeProfile=$runtimeProfilePath"
    Write-Host "[workbench-ingress] runtimeHostname=https://$($runtime.hostname)/"
    Write-Host "[workbench-ingress] runtimeTunnelId=$($runtime.tunnel.id)"
    Write-Host "[workbench-ingress] runtimeGeneratedAt=$($runtime.generatedAt)"
} else {
    Write-Host "[workbench-ingress] runtimeProfile is missing"
    Write-Host "[workbench-ingress] run npm.cmd run bootstrap:workbench once before starting ingress"
}

if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Host "[workbench-ingress] cloudflared state is missing"
    exit 0
}

$state = Get-Content -Encoding utf8 -Raw $statePath | ConvertFrom-Json
$running = $false
if ($state.pid) {
    $running = [bool](Get-Process -Id $state.pid -ErrorAction SilentlyContinue)
}

$readyState = Get-CloudflaredReadyState -ReadyUrl $state.metricsUrl
$statusCode = Get-PublicEndpointStatus -Url ("https://{0}/api/healthz" -f $state.hostname)

Write-Host "[workbench-ingress] hostname=https://$($state.hostname)/"
Write-Host "[workbench-ingress] cloudflaredPid=$($state.pid)"
Write-Host "[workbench-ingress] cloudflaredAlive=$running"
Write-Host "[workbench-ingress] metrics=$($state.metricsUrl)"
Write-Host "[workbench-ingress] cloudflaredReady=$($readyState.Ready)"
Write-Host "[workbench-ingress] readyConnections=$($readyState.ReadyConnections)"
Write-Host "[workbench-ingress] publicStatusCode=$statusCode"
if ($null -ne $state.PSObject.Properties["protocol"] -and $state.protocol) {
    Write-Host "[workbench-ingress] protocol=$($state.protocol)"
}
Write-Host "[workbench-ingress] stdout=$($state.stdoutPath)"
Write-Host "[workbench-ingress] stderr=$($state.stderrPath)"
