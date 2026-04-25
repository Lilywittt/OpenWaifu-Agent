param(
    [switch]$RefreshRuntime,
    [string]$CloudflaredPath = "",
    [int]$ReadyTimeoutSeconds = 90,
    [string]$Protocol = "http2"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-CloudflareApiToken {
    $envFilePath = Join-Path $projectDir ".env.local"
    $processValue = [Environment]::GetEnvironmentVariable("CLOUDFLARE_API_TOKEN", "Process")
    if ($processValue) {
        return $processValue
    }

    if (Test-Path -LiteralPath $envFilePath) {
        foreach ($rawLine in Get-Content -Encoding utf8 $envFilePath) {
            $line = $rawLine.Trim()
            if (-not $line -or $line.StartsWith("#")) {
                continue
            }

            if ($line.StartsWith("export ")) {
                $line = $line.Substring(7).Trim()
            }

            $separatorIndex = $line.IndexOf("=")
            if ($separatorIndex -le 0) {
                continue
            }

            $key = $line.Substring(0, $separatorIndex).Trim()
            if ($key -ne "CLOUDFLARE_API_TOKEN") {
                continue
            }

            $value = $line.Substring($separatorIndex + 1).Trim()
            if ($value.Length -ge 2) {
                if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
            }

            if ($value) {
                return $value
            }
        }
    }

    $userValue = [Environment]::GetEnvironmentVariable("CLOUDFLARE_API_TOKEN", "User")
    if ($userValue) {
        return $userValue
    }

    $machineValue = [Environment]::GetEnvironmentVariable("CLOUDFLARE_API_TOKEN", "Machine")
    if ($machineValue) {
        return $machineValue
    }

    return ""
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$runtimeProfilePath = Join-Path $projectDir "runtime\public_workbench_ingress\runtime.json"
$startScriptPath = Join-Path $scriptDir "start-public-workbench-ingress.ps1"
$statusScriptPath = Join-Path $scriptDir "status-public-workbench-ingress.ps1"
$runtimeScriptPath = Join-Path $scriptDir "get-public-workbench-runtime.mjs"

$needsRuntimeRefresh = $RefreshRuntime -or -not (Test-Path -LiteralPath $runtimeProfilePath)

if ($needsRuntimeRefresh) {
    Write-Host "[workbench-bootstrap] refreshing formal runtime profile"
    $apiToken = Resolve-CloudflareApiToken
    if (-not $apiToken) {
        throw "Missing CLOUDFLARE_API_TOKEN.`nSet it in the current shell or Windows user environment, then rerun npm.cmd run bootstrap:workbench."
    }

    [Environment]::SetEnvironmentVariable("CLOUDFLARE_API_TOKEN", $apiToken, "Process")
    Push-Location $projectDir
    try {
        & node $runtimeScriptPath --refresh
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to refresh public workbench runtime profile."
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[workbench-bootstrap] using existing runtime profile"
    Push-Location $projectDir
    try {
        & node $runtimeScriptPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to read public workbench runtime profile."
        }
    } finally {
        Pop-Location
    }
}

Write-Host "[workbench-bootstrap] starting public ingress"
& $startScriptPath -CloudflaredPath $CloudflaredPath -ReadyTimeoutSeconds $ReadyTimeoutSeconds -Protocol $Protocol
Write-Host "[workbench-bootstrap] final status"
& $statusScriptPath
