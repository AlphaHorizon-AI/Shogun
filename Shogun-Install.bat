@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ===============================================================
::  SHOGUN - One-Click Downloader & Installer (Windows)
::
::  This is a STANDALONE file. Download it, double-click it,
::  and Shogun will be installed automatically. No git required.
::  Prerequisites (Python, Node.js) will be installed for you.
:: ===============================================================

title Shogun - Installing...

echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :      SHOGUN - AI Agent Framework One-Click Installer     :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

:: -- Configuration ----------------------------------------------
set "REPO=AlphaHorizon-AI/Shogun"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\Shogun"
set "ZIP_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "ZIP_FILE=%TEMP%\shogun-download.zip"
:: -- Check and install prerequisites ----------------------------
echo  ======================================================
echo   Checking prerequisites...
echo  ======================================================
echo.

:: -- Python -----------------------------------------------------
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Python is not installed.
    echo.
    echo   Shogun requires Python 3.10+ to run.
    echo   Please download and install it from: https://www.python.org/downloads/
    echo   Be sure to check "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
        echo   [OK] Python %%v
    )
)

:: -- Node.js ----------------------------------------------------
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Node.js is not installed.
    echo.
    echo   Shogun requires Node.js v18+ to build the interface.
    echo   Please download and install it from: https://nodejs.org/
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do (
        echo   [OK] Node.js %%v
    )
)

echo.

:: -- Download ---------------------------------------------------
echo  ======================================================
echo   [+] Downloading Shogun from GitHub...
echo  ======================================================
echo.
echo       %ZIP_URL%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%ZIP_URL%', '%ZIP_FILE%')"

if not exist "%ZIP_FILE%" (
    echo   [!] Download failed. Please check your internet connection.
    pause
    exit /b 1
)
echo   [OK] Download complete.
echo.

:: -- Extract ----------------------------------------------------
echo   [+] Extracting to %INSTALL_DIR%...

if exist "%INSTALL_DIR%\configs\setup.json" (
    copy "%INSTALL_DIR%\configs\setup.json" "%TEMP%\shogun_setup_backup.json" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TEMP%\shogun-extract' -Force"

if exist "%TEMP%\shogun-extract\Shogun-%BRANCH%" (
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    robocopy "%TEMP%\shogun-extract\Shogun-%BRANCH%" "%INSTALL_DIR%" /E /XD data venv node_modules /NFL /NDL /NJH /NJS >nul 2>&1
)

if exist "%TEMP%\shogun_setup_backup.json" (
    if not exist "%INSTALL_DIR%\configs" mkdir "%INSTALL_DIR%\configs"
    copy "%TEMP%\shogun_setup_backup.json" "%INSTALL_DIR%\configs\setup.json" >nul 2>&1
    del "%TEMP%\shogun_setup_backup.json" >nul 2>&1
)

del "%ZIP_FILE%" >nul 2>&1
rmdir /s /q "%TEMP%\shogun-extract" >nul 2>&1

echo   [OK] Extracted to %INSTALL_DIR%
echo.

:: -- Run installer ----------------------------------------------
echo  ======================================================
echo   [+] Running Shogun installer...
echo  ======================================================
echo.

cd /d "%INSTALL_DIR%"
if exist "install.bat" (
    call install.bat
    exit /b 0
) else (
    echo   [!] Error: install.bat not found in %INSTALL_DIR%
    pause
    exit /b 1
)
