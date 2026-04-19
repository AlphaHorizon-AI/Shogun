@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ═══════════════════════════════════════════════════════════════
::  SHOGUN — One-Click Downloader & Installer (Windows)
::  
::  This is a STANDALONE file. Download it, double-click it,
::  and Shogun will be installed automatically. No git required.
:: ═══════════════════════════════════════════════════════════════

title Shogun — Installing...

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║     ███████╗██╗  ██╗ ██████╗  ██████╗ ██╗   ██╗███╗   ██╗║
echo  ║     ██╔════╝██║  ██║██╔═══██╗██╔════╝ ██║   ██║████╗  ██║║
echo  ║     ███████╗███████║██║   ██║██║  ███╗██║   ██║██╔██╗ ██║║
echo  ║     ╚════██║██╔══██║██║   ██║██║   ██║██║   ██║██║╚██╗██║║
echo  ║     ███████║██║  ██║╚██████╔╝╚██████╔╝╚██████╔╝██║ ╚████║║
echo  ║     ╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝║
echo  ║                                                          ║
echo  ║       AI Agent Framework — One-Click Installer           ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Configuration ──────────────────────────────────────────────
set "REPO=AlphaHorizon-AI/Shogun"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\Shogun"
set "ZIP_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "ZIP_FILE=%TEMP%\shogun-download.zip"

:: ── Check prerequisites ────────────────────────────────────────
echo   Checking prerequisites...
echo.

:: Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ❌  Python is not installed.
    echo.
    echo   Please install Python 3.10+ from:
    echo   https://python.org/downloads
    echo.
    echo   IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
    echo   ✅  Python %%v
)

:: Check Node.js
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ❌  Node.js is not installed.
    echo.
    echo   Please install Node.js 18+ from:
    echo   https://nodejs.org
    echo.
    pause
    exit /b 1
)
for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do (
    echo   ✅  Node.js %%v
)
echo.

:: ── Download ───────────────────────────────────────────────────
echo   📥  Downloading Shogun from GitHub...
echo       %ZIP_URL%
echo.

:: Use PowerShell to download (available on all modern Windows)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
   (New-Object Net.WebClient).DownloadFile('%ZIP_URL%', '%ZIP_FILE%')"

if not exist "%ZIP_FILE%" (
    echo   ❌  Download failed. Please check your internet connection.
    pause
    exit /b 1
)
echo   ✅  Download complete.
echo.

:: ── Extract ────────────────────────────────────────────────────
echo   📦  Extracting to %INSTALL_DIR%...

:: Remove old installation if present
if exist "%INSTALL_DIR%" (
    echo   ⚠️  Existing installation found. Backing up configs...
    if exist "%INSTALL_DIR%\configs\setup.json" (
        copy "%INSTALL_DIR%\configs\setup.json" "%TEMP%\shogun_setup_backup.json" >nul 2>&1
    )
    if exist "%INSTALL_DIR%\data" (
        echo   📁  Data directory preserved (will not be overwritten).
    )
)

:: Extract ZIP using PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TEMP%\shogun-extract' -Force"

:: Move extracted folder to install directory
if exist "%TEMP%\shogun-extract\Shogun-%BRANCH%" (
    :: Create install dir if needed
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    :: Use robocopy to merge (preserves existing data/)
    robocopy "%TEMP%\shogun-extract\Shogun-%BRANCH%" "%INSTALL_DIR%" /E /XD data venv node_modules /NFL /NDL /NJH /NJS >nul 2>&1
)

:: Restore backup if it existed
if exist "%TEMP%\shogun_setup_backup.json" (
    if not exist "%INSTALL_DIR%\configs" mkdir "%INSTALL_DIR%\configs"
    copy "%TEMP%\shogun_setup_backup.json" "%INSTALL_DIR%\configs\setup.json" >nul 2>&1
    del "%TEMP%\shogun_setup_backup.json" >nul 2>&1
)

:: Cleanup
del "%ZIP_FILE%" >nul 2>&1
rmdir /s /q "%TEMP%\shogun-extract" >nul 2>&1

echo   ✅  Extracted to %INSTALL_DIR%
echo.

:: ── Run installer ──────────────────────────────────────────────
echo   🚀  Running Shogun installer...
echo.

cd /d "%INSTALL_DIR%"
call install.bat
