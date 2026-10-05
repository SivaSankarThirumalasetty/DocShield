# ==============================================================================
# DocShield — Auto-Healing Watchdog for FastAPI + Public Cloudflare Worker API
# ==============================================================================
# Monitors BOTH the local FastAPI server (127.0.0.1:8000) AND the live public
# Cloudflare Worker endpoint (https://docshield.sivasankar-t1606.workers.dev/api/health)
# every 20 seconds. If either stops or the public Cloudflare tunnel expires/disconnects,
# automatically invokes scripts/start-cloudflare-tunnel.ps1 to heal the connection.
# ==============================================================================

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LauncherScript = Join-Path $PSScriptRoot "start-cloudflare-tunnel.ps1"
$PublicHealthUrl = "https://docshield.sivasankar-t1606.workers.dev/api/health"
$Headers = @{ "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DocShield-Watchdog/2.0" }

function Test-DocShieldEndToEnd {
    # 1. Check cloudflared process
    $CfProc = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
    if (-not $CfProc) {
        return $false
    }

    # 2. Check local FastAPI health
    try {
        $LocalHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 5
        if ($LocalHealth.status -ne "healthy") {
            return $false
        }
    } catch {
        return $false
    }

    # 3. Check public Cloudflare Worker health (2 attempts to avoid transient network blips)
    for ($attempt = 0; $attempt -lt 2; $attempt++) {
        try {
            $PublicHealth = Invoke-RestMethod -Uri $PublicHealthUrl -Headers $Headers -Method Get -TimeoutSec 8
            if ($PublicHealth.status -eq "healthy") {
                return $true
            }
        } catch {}
        Start-Sleep -Seconds 2
    }

    return $false
}

# Initial check immediately on watchdog startup (e.g., right after Windows boot)
if (-not (Test-DocShieldEndToEnd)) {
    try {
        & powershell.exe -ExecutionPolicy Bypass -File $LauncherScript
    } catch {}
}

while ($true) {
    Start-Sleep -Seconds 20
    if (-not (Test-DocShieldEndToEnd)) {
        try {
            & powershell.exe -ExecutionPolicy Bypass -File $LauncherScript
        } catch {}
    }
}
