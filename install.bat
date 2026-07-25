@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

set "TELEMETRY_MODE=ask"
set "TELEMETRY_NOTICE="
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--telemetry=on" set "TELEMETRY_MODE=on"
if /I "%~1"=="--telemetry=off" set "TELEMETRY_MODE=off"
for /f "tokens=1,* delims==" %%a in ("%~1") do (
    if /I "%%a"=="--accept-telemetry-notice" set "TELEMETRY_NOTICE=%%b"
)
shift
goto parse_args
:args_done
if defined CI if /I "%TELEMETRY_MODE%"=="ask" set "TELEMETRY_MODE=off"

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
pip install ".[office]" --quiet --disable-pip-version-check
if %ERRORLEVEL% neq 0 (
    echo  ERROR: Failed to install Python dependencies.
    pause
    exit /b 1
)
echo        Python dependencies installed.

:: -- Optional installation telemetry (unchecked/off by default) --
if /I "%TELEMETRY_MODE%"=="ask" (
    echo.
    echo  Help improve Shogun AFM ^(optional^)
    echo  Shared: version, OS family, install type, operating mode,
    echo  random installation ID, and one weekly active signal.
    echo  Never shared: prompts, responses, files, memory, messages,
    echo  people, credentials, local paths, hostnames, or hardware IDs.
    echo  Exact schema: docs\telemetry.md
    echo  Privacy: https://www.alphahorizon.io/shogun/telemetry-privacy/
    set /p "TELEMETRY_CHOICE= Share anonymous installation statistics? [y/N]: "
    if /I "!TELEMETRY_CHOICE!"=="y" (
        set "TELEMETRY_MODE=on"
        set "TELEMETRY_NOTICE=1.0"
    ) else (
        set "TELEMETRY_MODE=off"
    )
)
if /I "%TELEMETRY_MODE%"=="on" (
    if "%TELEMETRY_NOTICE%"=="1.0" (
        python -m shogun.telemetry.cli enable --notice-version 1.0
        echo        Optional installation telemetry enabled.
    ) else (
        python -m shogun.telemetry.cli disable
        echo        Telemetry remains disabled: notice version 1.0 was not explicitly accepted.
    )
) else (
    python -m shogun.telemetry.cli disable
    echo        Optional installation telemetry remains disabled.
)

:: -- Step 4b: Install Mado browser (Playwright Chromium) --------
echo        Installing Mado browser engine (Chromium)...
playwright install chromium --with-deps 2>nul || python -m playwright install chromium --with-deps 2>nul
echo        Mado browser engine ready.

:: -- Step 4c: Install Ronin desktop control (optional) ----------
echo.
set /p INSTALL_RONIN="  Enable desktop control (Ronin)? Allows AI to control mouse/keyboard. [y/N]: "
if /i "%INSTALL_RONIN%"=="y" (
    echo        Installing Ronin desktop dependencies...
    pip install ".[ronin]" --quiet --disable-pip-version-check
    if %ERRORLEVEL% neq 0 (
        echo        Warning: Ronin dependencies failed to install. You can try again later in the Setup Wizard.
    ) else (
        echo        Ronin desktop dependencies installed.
    )
) else (
    echo        Skipping Ronin. You can enable it later in the Setup Wizard or Shogun Profile.
)

:: -- Step 5: Bootstrap database ---------------------------------
echo [5/8] Bootstrapping database...
python -c "import asyncio; from shogun.bootstrap import bootstrap; asyncio.run(bootstrap())" 2>nul
echo        Database ready.

:: -- Step 6: Install and build frontend -------------------------
echo [6/8] Building frontend...
cd frontend
call npm install --silent
if %ERRORLEVEL% neq 0 (
    echo  WARNING: npm install failed. The frontend may not work correctly.
    echo           Try running 'npm install' manually in the frontend folder.
    cd ..
    goto step7
)
call npm run build
if %ERRORLEVEL% neq 0 (
    echo  WARNING: Frontend build failed. The UI may be outdated.
    echo           Try running 'npm run build' manually in the frontend folder.
    cd ..
    goto step7
)
cd ..
echo        Frontend built.


:step7
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
echo  :   Your browser will open when the server is ready.       :
echo  :                                                          :
echo  :   A desktop shortcut has been created.                   :
echo  :   Use it to launch Shogun in the future.                 :
echo  :                                                          :
echo  :   Press Ctrl+C to stop the server.                       :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

:: The Python server opens setup as soon as it is ready.
set "SHOGUN_BROWSER_URL=http://localhost:8000/setup"

:: Start the server (blocking)
python -m shogun
