@echo off
echo.
echo ============================================================
echo   Intelligenter Fragebogen - KI-Assistent
echo   Starte Chat-Interface...
echo ============================================================
echo.

cd /d "%~dp0"
call .venv\Scripts\activate.bat
python chat.py

pause
