@echo off
setlocal
echo ===================================================
echo 🚀 STARTING CRYPTO TRADING BOT SYSTEM
echo ===================================================

:: 0. Clean up existing processes (Ports and Lingering Python)
echo [SYSTEM] Clearing ports 8000, 8080, 5173 and killing lingering Python processes...
powershell -Command "Stop-Process -Name python -ErrorAction SilentlyContinue; 8000, 8080, 5173 | ForEach-Object { Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 4 } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } } 2>$null"

:: 1. Start Backend (Python Autonomous Logic)
echo [BACKEND] Starting Python Bot Logic...
:: Use the local virtual environment Python
start "BACKEND - Bot Logic" cmd /k "cd backend && .\venv\Scripts\python.exe src/main.py"

:: 2. Start Admin API Server (FastAPI)
echo [API] Starting Admin API Server...
start "API - Admin Server" cmd /k "cd backend && .\venv\Scripts\python.exe -m uvicorn src.server:app --port 8000 --reload"

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
