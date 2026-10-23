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
if exist "%VENV_DIR%\node-runtime\node.exe" set "PATH=%CD%\%VENV_DIR%\node-runtime;%PATH%"
python shogun\security_maintenance.py check --node
if errorlevel 1 exit /b 1

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

:: The Python entry point resolves the configured address and recognizes an
:: existing Shogun listener before opening the browser.
:: Preserve an explicit SHOGUN_BROWSER_URL; Python supplies the default from
:: API_HOST/API_PORT rather than forcing another application's port.
echo   Shogun is starting...
echo   Your browser will open automatically.
echo.
echo   Press Ctrl+C to stop the server.
echo.

:: The Python server opens the browser as soon as it is ready.
set "SHOGUN_MANAGED_BROWSER=true"

:: Start the server (blocking; keeps the window open)
set "SHOGUN_LAUNCHER_MANAGED=true"
:run_shogun
python -m shogun
set "SHOGUN_EXIT_CODE=!ERRORLEVEL!"

if exist ".states\restart-requested" (
    del /q ".states\restart-requested" >nul 2>&1
    echo.
    echo   Restart requested. Starting Shogun again...
    timeout /t 2 /nobreak >nul
    goto run_shogun
)

if exist ".states\shutdown-requested" (
    del /q ".states\shutdown-requested" >nul 2>&1
    echo.
    echo   Tenshu shut down safely.
    exit /b 0
)

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
