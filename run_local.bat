@echo off
title DocShield - Local Development Launcher
echo ========================================================
echo   DocShield: AI-assisted document screening prototype
echo   SIH26188 (MHA / Sashastra Seema Bal)
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/2] Launching DocShield FastAPI Backend on http://127.0.0.1:8000 ...
start "DocShield Backend" cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Launching DocShield Frontend on http://localhost:5173 ...
cd frontend
start "DocShield Frontend" cmd /k "npm run dev"

echo.
echo ========================================================
echo Both services are booting!
echo Frontend: http://localhost:5173
echo Backend API Docs:  http://127.0.0.1:8000/api/docs
echo ========================================================
echo.
timeout /t 3 >nul
start http://localhost:5173
