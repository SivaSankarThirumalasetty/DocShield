# ==============================================================================
# DocShield — $0 Cloudflare Tunnel + FastAPI Backend Launcher (Path B)
# ==============================================================================
# Starts the real DocShield FastAPI v2.0.0 AI/CV backend locally on port 8000,
# opens a Cloudflare Quick Tunnel (trycloudflare.com), and automatically updates
# the Cloudflare Worker secret `BACKEND_ORIGIN` on:
#   https://docshield.sivasankar-t1606.workers.dev
# Uses Win32_Process WMI creation so background daemons survive terminal exit.
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
$CloudflaredPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
if (-not (Test-Path $CloudflaredPath)) {
    $Cmd = Get-Command "cloudflared" -ErrorAction SilentlyContinue
    if ($Cmd) {
        $CloudflaredPath = $Cmd.Source
    } else {
        Write-Error "cloudflared.exe not found. Install via: winget install Cloudflare.cloudflared"
        exit 1
    }
}

$StartupInfo = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }

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
    Write-Host "[1/3] Starting detached FastAPI v2.0.0 backend on http://0.0.0.0:$Port ..." -ForegroundColor Yellow
    $UvicornCmd = "cmd.exe /c `"set DOCSHIELD_ENV=production&& set DOCSHIELD_MODE=PROTOTYPE&& set FRONTEND_ORIGIN=$FrontendOrigin&& py -3.11 -m uvicorn backend.main:app --host 0.0.0.0 --port $Port`""
    $UvicornWmi = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = $UvicornCmd
        CurrentDirectory = $RepoRoot
        ProcessStartupInformation = $StartupInfo
    }

    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 1
        try {
            $HealthCheck = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -Method Get -TimeoutSec 2
            if ($HealthCheck.status -eq "healthy") {
                $BackendHealthy = $true
                Write-Host "      FastAPI backend ready on http://0.0.0.0:$Port (PID: $($UvicornWmi.ProcessId))" -ForegroundColor Green
                break
            }
        } catch {}
    }
    if (-not $BackendHealthy) {
        Write-Error "FastAPI backend failed to become healthy on http://0.0.0.1:$Port"
        exit 1
    }
}

# 3. Stop any stale cloudflared quick-tunnel processes and start a fresh detached HTTP/2 IPv4 tunnel
Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

$TunnelLog = Join-Path $env:TEMP "docshield-cloudflared.log"
if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force }

Write-Host "[2/3] Starting detached Cloudflare Tunnel (HTTP/2 IPv4) to http://127.0.0.1:$Port ..." -ForegroundColor Yellow
$TunnelCmd = "`"$CloudflaredPath`" tunnel --url http://127.0.0.1:$Port --no-autoupdate --protocol http2 --edge-ip-version 4 --logfile `"$TunnelLog`""
$TunnelWmi = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $TunnelCmd
    CurrentDirectory = $RepoRoot
    ProcessStartupInformation = $StartupInfo
}

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

Write-Host "      Cloudflare Tunnel active: $TunnelUrl (PID: $($TunnelWmi.ProcessId))" -ForegroundColor Green

# 4. Update Cloudflare Worker BACKEND_ORIGIN secret
Write-Host "[3/3] Updating Cloudflare Worker BACKEND_ORIGIN secret ..." -ForegroundColor Yellow
$TunnelUrl | npx wrangler secret put BACKEND_ORIGIN

# 5. Ensure Windows Startup auto-launch wrapper is registered for reboots
try {
    $StartupFolder = [Environment]::GetFolderPath("Startup")
    if ($StartupFolder -and (Test-Path $StartupFolder)) {
        $WatchdogScript = Join-Path $PSScriptRoot "keep-tunnel-alive.ps1"
        $VbsPath = Join-Path $StartupFolder "DocShield-Tunnel-Autostart.vbs"
        $VbsContent = "Set WshShell = CreateObject(""WScript.Shell"")`r`nWshShell.Run ""powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File """"$WatchdogScript"""""", 0, False`r`n"
        Set-Content -Path $VbsPath -Value $VbsContent -Encoding ASCII -Force
    }
} catch {}

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " DocShield Live on Cloudflare!" -ForegroundColor Green
Write-Host " Frontend + API Gateway : $FrontendOrigin" -ForegroundColor Green
Write-Host " Active Tunnel Origin   : $TunnelUrl (PID: $($TunnelWmi.ProcessId))" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Cyan

