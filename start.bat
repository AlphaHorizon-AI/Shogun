@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ===============================================================
::  SHOGUN — Tenshu Launcher (Windows)
:: ===============================================================

title Shogun — The Tenshu

:: Navigate to script directory (handles shortcut launches)
cd /d "%~dp0"

echo.
echo   ⚔️  SHOGUN — Starting the Tenshu...
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
    echo   Looked for: venv\  and  .venv\
    echo   Please run install.bat first.
    echo.
    echo   Press any key to close...
    pause >nul
    exit /b 1
)

:: Activate venv
echo   Using virtual environment: %VENV_DIR%
call %VENV_DIR%\Scripts\activate.bat

:: Check if frontend is built
if not exist "frontend\dist\index.html" (
    echo   ⚠️  Frontend not built. Building now...
    cd frontend
    call npm run build --silent 2>nul
    cd ..
    echo   ✅  Frontend built.
)

echo   🌐  Shogun is starting at http://localhost:8000
echo   📖  Your browser will open automatically.
echo.
echo   Press Ctrl+C to stop the server.
echo.

:: Open browser after a short delay (background)
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"

:: Start the server (blocking — keeps the window open)
python -m shogun

:: If the server exits, keep the window open so the user can see errors
echo.
echo   ⚠️  Shogun has stopped.
echo   Press any key to close this window.
pause >nul

