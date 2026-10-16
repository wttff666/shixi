@echo off
cd /d "%~dp0"
echo Starting Remote Diagnosis platform...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-background.ps1"
if errorlevel 1 (
  echo.
  echo Start failed. Check data\server.log.error for details.
) else (
  echo.
  echo Open http://127.0.0.1:8091 in your browser.
)
echo.
pause
