@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title Shogun - The Tenshu

:: Navigate to script directory (handles shortcut launches)
cd /d "%~dp0"

echo.
echo   SHOGUN - Starting the Tenshu...
echo.

:: Check if venv exists (support both "venv" and ".venv" names)
set "VENV_DIR="
if exist "venv\Scripts\activate.bat" (
    set "VENV_DIR=venv"
)
if exist ".venv\Scripts\activate.bat" (
    set "VENV_DIR=.venv"
)

if "%VENV_DIR%"=="" (
    echo   ERROR: Virtual environment not found.
    echo   Looked for: venv\ and .venv\
    echo   Please run install.bat first.
    echo.
    echo   Press any key to close...
    pause >nul
    exit /b 1
)

:: Activate venv
echo   Using virtual environment: %VENV_DIR%
call %VENV_DIR%\Scripts\activate.bat

:: Build frontend on every launch so the served UI always matches this codebase.
:: This prevents stale laptop builds from hiding newly-added tabs or panels.
echo   Building frontend assets...
cd frontend
call npm run build --silent
if errorlevel 1 (
    cd ..
    echo.
    echo   ERROR: Frontend build failed.
    echo   Please run Shogun-Repair-Update.bat, then start Shogun again.
    echo.
    echo   Press any key to close...
    pause >nul
    exit /b 1
)
cd ..
echo   Frontend assets ready.

:: A second shortcut launch should reopen the existing Tenshu, not try to bind
:: the same port and report that Shogun stopped.
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://localhost:8000/api/v1/health'; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo   Shogun is already running. Opening the Tenshu...
    start "" "http://localhost:8000"
    timeout /t 2 /nobreak >nul
    exit /b 0
)

echo   Shogun is starting at http://localhost:8000
echo   Your browser will open automatically.
echo.
echo   Press Ctrl+C to stop the server.
echo.

:: The Python server opens the browser as soon as it is ready.
set "SHOGUN_BROWSER_URL=http://localhost:8000"

:: Start the server (blocking; keeps the window open)
python -m shogun
set "SHOGUN_EXIT_CODE=!ERRORLEVEL!"

:: If the server exits, keep the window open so the user can see errors
echo.
if "!SHOGUN_EXIT_CODE!"=="0" (
    echo   Shogun stopped normally.
) else (
    echo   ERROR: Shogun stopped unexpectedly ^(exit code !SHOGUN_EXIT_CODE!^).
    if exist "logs\startup-error.log" (
        echo   Startup details: %CD%\logs\startup-error.log
    )
)
echo   Press any key to close this window.
pause >nul
exit /b !SHOGUN_EXIT_CODE!
