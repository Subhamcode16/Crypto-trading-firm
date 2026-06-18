@echo off
setlocal
echo ===================================================
echo 🚀 STARTING CRYPTO TRADING BOT SYSTEM
echo ===================================================

:: Fix Python encoding on Windows
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: 0. Clean up existing processes (Ports and Lingering Python)
echo [SYSTEM] Clearing ports 8001, 8080, 5173 and killing lingering Python processes...
powershell -Command "Stop-Process -Name python -ErrorAction SilentlyContinue; 8001, 8080, 5173 | ForEach-Object { Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 4 } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } } 2>$null"

:: 1. Start Admin API Server (FastAPI) & Gamified Agent
echo [API] Starting Admin API Server and Agent...
start "API & AGENT - Server" cmd /k "cd backend && .\venv\Scripts\python.exe -m uvicorn src.server:app --port 8001 --reload"

:: 3. Start WebSocket/Scenario Server (Node.js)
echo [SERVER] Starting Mock API and Scenario Server...
start "SERVER - WebSocket" cmd /k "cd server && node index.js"

:: 4. Start Frontend (React/Vite Office UI)
echo [FRONTEND] Starting Vite Development Server...
start "FRONTEND - Office UI" cmd /k "cd frontend && npm run dev"

echo.
echo ===================================================
echo ✅ ALL SYSTEMS INITIALIZED
echo ===================================================
echo.
echo Please review the three newly opened terminal windows:
echo 1. BACKEND - Periodic Token Discovery (Bot Logic)
echo 2. SERVER  - Real-time WebSocket Data (Scenarios)
echo 3. FRONTEND - Pixel art dashboard (http://localhost:5173)
echo.
echo Press any key to close this launcher...
pause > nul
endlocal
