@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ===============================================================
::  GENSUI — One-Click Installer (Windows)
::  Central Command & Security Control Plane for Shogun
:: ===============================================================

cd /d "%~dp0"

echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :       GENSUI - Central Command for Shogun                :
echo  :       One-Click Installer                                :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

:: -- Step 1: Check Python -----------------------------------------
echo [1/7] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Please install Python 3.10+ from https://python.org
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo        Found Python %PY_VER%

:: -- Step 2: Check Node.js ----------------------------------------
echo [2/7] Checking Node.js...
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

:: -- Step 3: Create Python virtual environment --------------------
echo [3/7] Creating Python virtual environment...
if exist ".venv\Scripts\activate.bat" (
    echo        Existing .venv found — reusing.
) else (
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo        Virtual environment created.
)

:: -- Step 4: Install Python dependencies --------------------------
echo [4/7] Installing Gensui server dependencies...
call .venv\Scripts\activate.bat
pip install . --quiet --disable-pip-version-check
if %ERRORLEVEL% neq 0 (
    echo  ERROR: Failed to install Python dependencies.
    pause
    exit /b 1
)
echo        Server dependencies installed.

:: -- Step 5: Build frontend ---------------------------------------
echo [5/7] Building Gensui Admin UI...
if exist "frontend\package.json" (
    cd frontend
    call npm install --silent 2>nul
    call npm run build --silent 2>nul
    cd ..
    echo        Admin UI built.
) else (
    echo        No frontend found — skipping.
)

:: -- Step 6: Create .env if not present ---------------------------
echo [6/7] Configuring environment...
if not exist ".env" (
    copy ".env.example" ".env" >nul 2>&1
    :: Generate random JWT secret
    for /f %%i in ('python -c "import secrets; print(secrets.token_urlsafe(48))"') do set JWT_SECRET=%%i
    for /f %%i in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set ADMIN_SECRET=%%i
    powershell -Command "(Get-Content .env) -replace 'change-me-to-a-random-64-char-string', '%JWT_SECRET%' | Set-Content .env"
    powershell -Command "(Get-Content .env) -replace 'change-me-to-a-random-admin-password', '%ADMIN_SECRET%' | Set-Content .env"
    echo        .env created with random secrets.
) else (
    echo        .env already exists — keeping existing config.
)

:: -- Step 7: Start server -----------------------------------------
echo [7/7] Starting Gensui...
echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :   Installation complete!                                 :
echo  :                                                          :
echo  :   Gensui is starting at http://localhost:8787            :
echo  :   API docs at http://localhost:8787/docs                 :
echo  :                                                          :
echo  :   Admin: admin@gensui.local                              :
echo  :   Password: stored in gensui\.env                       :
echo  :                                                          :
echo  :   Press Ctrl+C to stop the server.                       :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8787"

set PYTHONPATH=%~dp0..
python -m gensui
