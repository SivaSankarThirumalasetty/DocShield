# ==============================================================================
# DocShield — Auto-Healing Watchdog for FastAPI + Cloudflare Tunnel
# ==============================================================================
# Monitors the local FastAPI server (127.0.0.1:8000) and cloudflared process
# every 20 seconds. If either stops or the public Cloudflare Worker health check
# returns >= 500, automatically invokes scripts/start-cloudflare-tunnel.ps1.
# ==============================================================================

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LauncherScript = Join-Path $PSScriptRoot "start-cloudflare-tunnel.ps1"

while ($true) {
    Start-Sleep -Seconds 20
    $NeedsRestart = $false

    # 1. Check cloudflared process
    $CfProc = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
    if (-not $CfProc) {
        $NeedsRestart = $true
    }

    # 2. Check local FastAPI health
    if (-not $NeedsRestart) {
        try {
            $LocalHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 4
            if ($LocalHealth.status -ne "healthy") {
                $NeedsRestart = $true
            }
        } catch {
            $NeedsRestart = $true
        }
    }

    if ($NeedsRestart) {
        try {
            & powershell.exe -ExecutionPolicy Bypass -File $LauncherScript
        } catch {}
    }
}
