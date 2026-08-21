@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
set "EXIT_CODE=1"

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
echo [1/8] Checking Python...
call python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Please install Python 3.10+ from https://python.org
    echo.
    pause
    goto :installer_exit
)
call python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Gensui requires Python 3.10 or newer.
    echo.
    pause
    goto :installer_exit
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo        Found Python %PY_VER%

:: -- Step 2: Check Node.js ----------------------------------------
echo [2/8] Checking Node.js...
call node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Node.js is not installed or not in PATH.
    echo  Please install Node.js 22.12 or newer, but below 25, from https://nodejs.org
    echo.
    pause
    goto :installer_exit
)

for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
set "GENSUI_NODE_VERSION=!NODE_VER!"
call python -c "import os; p=tuple(map(int, os.environ['GENSUI_NODE_VERSION'].lstrip('v').split('.')[:2])); raise SystemExit(0 if (22, 12) <= p < (25, 0) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Unsupported Node.js !NODE_VER!. Gensui requires 22.12 or newer, but below 25.
    echo.
    pause
    goto :installer_exit
)
echo        Found Node.js !NODE_VER!
set "GENSUI_NODE_VERSION="

:: -- Step 3: Create Python virtual environment --------------------
echo [3/8] Creating Python virtual environment...
if exist ".venv\Scripts\activate.bat" (
    echo        Existing .venv found — reusing.
) else (
    call python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo  ERROR: Failed to create virtual environment.
        pause
        goto :installer_exit
    )
    echo        Virtual environment created.
)

:: -- Step 4: Install Python dependencies --------------------------
echo [4/8] Installing Gensui server dependencies...
call .venv\Scripts\activate.bat
call pip install . --quiet --disable-pip-version-check
if %ERRORLEVEL% neq 0 (
    echo  ERROR: Failed to install Python dependencies.
    pause
    goto :installer_exit
)
echo        Server dependencies installed.

:: -- Step 5: Build frontend ---------------------------------------
echo [5/8] Building Gensui Admin UI...
if exist "frontend\package.json" (
    pushd frontend
    call npm install --silent 2>nul
    if errorlevel 1 (
        popd
        echo  ERROR: Failed to install Gensui frontend dependencies.
        pause
        goto :installer_exit
    )
    call npm run build --silent 2>nul
    if errorlevel 1 (
        popd
        echo  ERROR: Failed to build the Gensui Admin UI.
        pause
        goto :installer_exit
    )
    popd
    echo        Admin UI built.
) else (
    echo        No frontend found — skipping.
)

:: -- Step 6: Create .env if not present ---------------------------
echo [6/8] Configuring environment...
if not exist ".env" (
    copy ".env.example" ".env" >nul 2>&1
    if errorlevel 1 (
        echo  ERROR: Failed to create the Gensui environment file.
        pause
        goto :installer_exit
    )
    set "ENV_CREATED=1"
    for /f %%i in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set ADMIN_SECRET=%%i
    if not defined ADMIN_SECRET (
        del /f /q ".env" >nul 2>&1
        echo  ERROR: Failed to generate the Gensui administrator secret.
        pause
        goto :installer_exit
    )
    powershell -NoProfile -Command "$p=(Resolve-Path '.env').Path; $c=[IO.File]::ReadAllText($p).Replace('change-me-to-a-random-admin-password',$env:ADMIN_SECRET); [IO.File]::WriteAllText($p,$c,(New-Object Text.UTF8Encoding($false)))"
    if errorlevel 1 (
        del /f /q ".env" >nul 2>&1
        echo  ERROR: Failed to configure the Gensui environment file.
        pause
        goto :installer_exit
    )
    echo        .env created; JWT material will be generated in data\secrets.
) else (
    echo        .env already exists — keeping existing config.
)
powershell -NoProfile -Command "$p=(Resolve-Path '.env').Path; $id=[Security.Principal.WindowsIdentity]::GetCurrent().User; $acl=New-Object System.Security.AccessControl.FileSecurity; $acl.SetAccessRuleProtection($true,$false); $rule=New-Object System.Security.AccessControl.FileSystemAccessRule($id,'FullControl','Allow'); $acl.SetAccessRule($rule); Set-Acl -LiteralPath $p -AclObject $acl -ErrorAction Stop"
if errorlevel 1 (
    if defined ENV_CREATED del /f /q ".env" >nul 2>&1
    echo  ERROR: Could not restrict access to the secret-bearing .env file.
    pause
    goto :installer_exit
)
set "ADMIN_SECRET="
set "ENV_CREATED="

:: -- Step 7: Create desktop shortcut ------------------------------
echo [7/8] Creating desktop shortcut...
if exist "scripts\create_shortcut_win.bat" (
    call scripts\create_shortcut_win.bat
) else (
    echo        Warning: Shortcut script not found.
)

:: -- Step 8: Start server -----------------------------------------
echo [8/8] Starting Gensui...
echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :   Installation complete!                                 :
echo  :                                                          :
echo  :   Gensui is starting at http://localhost:8787            :
echo  :   API docs are disabled unless DEBUG=true                :
echo  :                                                          :
echo  :   Admin: admin@gensui.local                              :
echo  :   Password: stored in gensui\.env                       :
echo  :                                                          :
echo  :   A Gensui desktop shortcut has been created.            :
echo  :                                                          :
echo  :   Press Ctrl+C to stop the server.                       :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8787"

set PYTHONPATH=%~dp0..
python -m gensui
set "EXIT_CODE=%ERRORLEVEL%"

:installer_exit
endlocal & exit /b %EXIT_CODE%
