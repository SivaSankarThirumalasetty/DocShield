# ==============================================================================
# DocShield — $0 Cloudflare Tunnel + FastAPI Backend Launcher (Path B)
# ==============================================================================
# Starts the real DocShield FastAPI v2.0.0 AI/CV backend locally on port 8000,
# opens a Cloudflare Quick Tunnel (trycloudflare.com), and automatically updates
# the Cloudflare Worker secret `BACKEND_ORIGIN` on:
#   https://docshield.sivasankar-t1606.workers.dev
# ==============================================================================

param(
    [int]$Port = 8000,
    [string]$FrontendOrigin = "https://docshield.sivasankar-t1606.workers.dev"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " DocShield Cloudflare Tunnel + FastAPI v2.0.0 Launcher ($0 Tier)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Locate cloudflared binary
$CloudflaredPath = "cloudflared"
if (-not (Get-Command $CloudflaredPath -ErrorAction SilentlyContinue)) {
    $DefaultPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path $DefaultPath) {
        $CloudflaredPath = $DefaultPath
    } else {
        Write-Error "cloudflared.exe not found. Install via: winget install Cloudflare.cloudflared"
        exit 1
    }
}

# 2. Ensure FastAPI backend is running on 127.0.0.1:$Port
$BackendHealthy = $false
try {
    $HealthCheck = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -Method Get -TimeoutSec 2
    if ($HealthCheck.status -eq "healthy") {
        $BackendHealthy = $true
        Write-Host "[1/3] FastAPI backend already healthy on http://127.0.0.1:$Port (v$($HealthCheck.version))" -ForegroundColor Green
    }
} catch {}

if (-not $BackendHealthy) {
    Write-Host "[1/3] Starting FastAPI v2.0.0 backend on http://127.0.0.1:$Port ..." -ForegroundColor Yellow
    $env:DOCSHIELD_ENV = "production"
    $env:DOCSHIELD_MODE = "PROTOTYPE"
    $env:FRONTEND_ORIGIN = $FrontendOrigin
    Start-Process -FilePath "py" -ArgumentList "-3.11", "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "$Port" -WorkingDirectory $RepoRoot -WindowStyle Minimized

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        try {
            $HealthCheck = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -Method Get -TimeoutSec 2
            if ($HealthCheck.status -eq "healthy") {
                $BackendHealthy = $true
                Write-Host "      FastAPI backend ready on http://127.0.0.1:$Port" -ForegroundColor Green
                break
            }
        } catch {}
    }
    if (-not $BackendHealthy) {
        Write-Error "FastAPI backend failed to become healthy on http://127.0.0.1:$Port"
        exit 1
    }
}

# 3. Launch Cloudflare Quick Tunnel and capture URL
$TunnelLog = Join-Path $env:TEMP "docshield-cloudflared.log"
if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force }

Write-Host "[2/3] Starting Cloudflare Tunnel to http://127.0.0.1:$Port ..." -ForegroundColor Yellow
$TunnelProc = Start-Process -FilePath $CloudflaredPath -ArgumentList "tunnel", "--url", "http://127.0.0.1:$Port", "--no-autoupdate", "--logfile", $TunnelLog -PassThru -WindowStyle Minimized

$TunnelUrl = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $TunnelLog) {
        $LogContent = Get-Content $TunnelLog -Raw -ErrorAction SilentlyContinue
        if ($LogContent -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
            $TunnelUrl = $Matches[1]
            break
        }
    }
}

if (-not $TunnelUrl) {
    Write-Error "Failed to obtain trycloudflare.com URL from cloudflared logs."
    exit 1
}

Write-Host "      Cloudflare Tunnel active: $TunnelUrl" -ForegroundColor Green

# 4. Update Cloudflare Worker BACKEND_ORIGIN secret
Write-Host "[3/3] Updating Cloudflare Worker BACKEND_ORIGIN secret ..." -ForegroundColor Yellow
$TunnelUrl | npx wrangler secret put BACKEND_ORIGIN

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " DocShield Live on Cloudflare!" -ForegroundColor Green
Write-Host " Frontend + API Gateway : $FrontendOrigin" -ForegroundColor Green
Write-Host " Active Tunnel Origin   : $TunnelUrl (PID: $($TunnelProc.Id))" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Cyan

# Keep process alive so background daemon / terminal session holds the tunnel open
Wait-Process -Id $TunnelProc.Id

