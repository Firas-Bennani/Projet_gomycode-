@echo off
echo ========================================================
echo   Starting Standalone 3D + AI Industrial Copilot
echo ========================================================
echo.

echo Starting Backend Server (FastAPI + AI Multi-Agent + IoT)...
start "Backend - FastAPI" cmd /k "cd /d %~dp0backend && .\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo Starting Frontend Dev Server (Vite + Three.js)...
start "Frontend - Vite 3D AI" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 2 /nobreak >nul

echo Opening browser at http://localhost:5173...
start http://localhost:5173

echo ========================================================
echo   3D AI Copilot Application Started Successfully!
echo ========================================================
