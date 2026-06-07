@echo off
setlocal

cd /d "%~dp0"

echo [run_demo.bat] Starting ASCE 7-16 Wind Load Demo...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1" -OpenBrowser

if errorlevel 1 (
  echo.
  echo [run_demo.bat] Startup script failed. Check the logs folder for details.
  pause
  exit /b 1
)

echo.
echo [run_demo.bat] Startup commands finished. Backend and frontend continue running in the background.
echo [run_demo.bat] Close the python.exe processes from Task Manager when you are done, or restart your terminal session.
pause
