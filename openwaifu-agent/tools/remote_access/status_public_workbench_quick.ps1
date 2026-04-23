Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "remote_access_common.ps1")

$state = Read-QuickTunnelState -RefreshFromLogs
Write-QuickTunnelStatus -State $state
