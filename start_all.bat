@echo off
echo ========================================
echo    42 Grad Interview System Starter
echo ========================================
echo.

REM Backend starten (Flask auf Port 5000)
echo [1/2] Starte Backend (Flask)...
cd /d "%~dp0interview-orchestrator"
start "Interview Backend" cmd /k "call .\.venv\Scripts\python.exe .\web_app.py"

REM Warte auf Backend-Bereitschaft (prueft /api/llm/status Endpunkt)
echo Warte auf Backend-Initialisierung (RAG-System)...
:wait_loop
timeout /t 2 /nobreak >nul
curl -s http://localhost:5000/api/llm/status >nul 2>&1
if errorlevel 1 (
    echo    ... Backend startet noch ...
    goto wait_loop
)
echo    Backend ist bereit!

REM Frontend starten (Vite auf Port 3000)
echo [2/2] Starte Frontend (React)...
cd /d "%~dp0frontend"
start "Interview Frontend" cmd /k "npm run dev"

echo.
echo ========================================
echo    Beide Server wurden gestartet!
echo ========================================
echo.
echo    Backend:  http://localhost:5000
echo    Frontend: http://localhost:3000
echo.
echo    Zum Beenden: Beide Konsolenfenster schliessen
echo ========================================
echo.

REM Browser oeffnen nach kurzer Wartezeit
timeout /t 3 /nobreak >nul
start http://localhost:3000

exit
