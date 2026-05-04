@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ===============================================================
::  SHOGUN - One-Click Installer (Windows)
:: ===============================================================

:: Ensure we run from the script's own directory
cd /d "%~dp0"

echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :            SHOGUN AI Framework - Installer               :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

:: -- Step 1: Check Python ---------------------------------------
echo [1/8] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Please install Python 3.10+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo        Found Python %PY_VER%

:: -- Step 2: Check Node.js --------------------------------------
echo [2/8] Checking Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERROR: Node.js is not installed or not in PATH.
    echo  Please install Node.js 18+ from https://nodejs.org
    echo.
    pause
    exit /b 1
)

for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do set NODE_VER=%%v
echo        Found Node.js %NODE_VER%

:: -- Step 3: Create Python virtual environment ------------------
echo [3/8] Creating Python virtual environment...
set "VENV_DIR="
if exist ".venv\Scripts\activate.bat" (
    set "VENV_DIR=.venv"
    echo        Existing .venv found — reusing.
)
if exist "venv\Scripts\activate.bat" (
    set "VENV_DIR=venv"
    echo        Existing venv found — reusing.
)
if "%VENV_DIR%"=="" (
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    set "VENV_DIR=venv"
    echo        Virtual environment created.
)

:: -- Step 4: Install Python dependencies ------------------------
echo [4/8] Installing Python dependencies...
call %VENV_DIR%\Scripts\activate.bat
pip install . --quiet --disable-pip-version-check
if %ERRORLEVEL% neq 0 (
    echo  ERROR: Failed to install Python dependencies.
    pause
    exit /b 1
)
echo        Python dependencies installed.

:: -- Step 5: Bootstrap database ---------------------------------
echo [5/8] Bootstrapping database...
python -c "import asyncio; from shogun.bootstrap import bootstrap; asyncio.run(bootstrap())" 2>nul
echo        Database ready.

:: -- Step 6: Install and build frontend -------------------------
echo [6/8] Building frontend...
cd frontend
call npm install --silent 2>nul
call npm run build --silent 2>nul
cd ..
echo        Frontend built.

:: -- Step 7: Create desktop shortcut ----------------------------
echo [7/8] Creating desktop shortcut...
if exist "scripts\create_shortcut_win.bat" (
    call scripts\create_shortcut_win.bat
) else (
    echo        Warning: Shortcut script not found.
)

:: -- Step 8: Done -----------------------------------------------
echo [8/8] Starting Shogun...
echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :   Installation complete!                                 :
echo  :                                                          :
echo  :   Shogun is starting at http://localhost:8000/setup      :
echo  :   Your browser will open automatically in 5 seconds.     :
echo  :                                                          :
echo  :   A desktop shortcut has been created.                   :
echo  :   Use it to launch Shogun in the future.                 :
echo  :                                                          :
echo  :   Press Ctrl+C to stop the server.                       :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

:: Open browser after a short delay
start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8000/setup"

:: Start the server (blocking)
python -m shogun
