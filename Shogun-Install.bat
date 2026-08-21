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
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo   [!] Python 3.10 or newer is required.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do echo   [OK] Python %%v

:: -- Node.js ----------------------------------------------------
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Node.js is not installed.
    echo.
    echo   Shogun requires Node.js 22.12+ ^(but lower than 25^) to build the interface.
    echo   Please download and install it from: https://nodejs.org/
    echo.
    pause
    exit /b 1
)
node -e "const [major,minor]=process.versions.node.split('.').map(Number); process.exit((major>22||major===22&&minor>=12)&&major<25?0:1)" >nul 2>&1
if errorlevel 1 (
    echo   [!] Node.js 22.12 or newer, but lower than 25, is required.
    pause
    exit /b 1
)
for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do echo   [OK] Node.js %%v

echo.

:: -- Download ---------------------------------------------------
echo   [+] Resolving the immutable release source...
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $sha=(Invoke-RestMethod -UseBasicParsing -Headers @{'User-Agent'='Shogun-Installer'} -Uri 'https://api.github.com/repos/%REPO%/commits/%BRANCH%').sha; if(-not [regex]::IsMatch([string]$sha,'\A[0-9a-fA-F]{40}\z')){exit 1}; $sha.ToLowerInvariant()" 2^>nul`) do set "SOURCE_COMMIT=%%i"
if not defined SOURCE_COMMIT (
    echo   [!] GitHub did not return a verifiable source commit.
    echo       Installation stopped instead of downloading a mutable branch archive.
    pause
    exit /b 1
)
set "ZIP_URL=https://github.com/%REPO%/archive/%SOURCE_COMMIT%.zip"
echo   [OK] Source commit: %SOURCE_COMMIT%
echo.

for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[IO.Path]::Combine([IO.Path]::GetTempPath(),('shogun-install-'+[Guid]::NewGuid().ToString('N')))"`) do set "TEMP_ROOT=%%i"
if not defined TEMP_ROOT (
    echo   [!] A private temporary directory could not be created.
    pause
    exit /b 1
)
mkdir "%TEMP_ROOT%" >nul 2>&1
if errorlevel 1 (
    echo   [!] A private temporary directory could not be created.
    pause
    exit /b 1
)
set "ZIP_FILE=%TEMP_ROOT%\shogun-download.zip"
set "EXTRACT_DIR=%TEMP_ROOT%\extract"
set "SETUP_BACKUP=%TEMP_ROOT%\setup.json"

echo  ======================================================
echo   [+] Downloading Shogun from GitHub...
echo  ======================================================
echo.
echo       %ZIP_URL%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%ZIP_URL%', '%ZIP_FILE%')"

if not exist "%ZIP_FILE%" (
    echo   [!] Download failed. Please check your internet connection.
    call :cleanup
    pause
    exit /b 1
)
echo   [OK] Download complete.
echo.

:: -- Extract ----------------------------------------------------
echo   [+] Extracting to %INSTALL_DIR%...

if exist "%INSTALL_DIR%\configs\setup.json" (
    copy "%INSTALL_DIR%\configs\setup.json" "%SETUP_BACKUP%" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%EXTRACT_DIR%' -Force"
if errorlevel 1 (
    echo   [!] Extraction failed: the pinned archive could not be opened.
    call :cleanup
    pause
    exit /b 1
)

set "SOURCE_DIR=%EXTRACT_DIR%\Shogun-%SOURCE_COMMIT%"
if not exist "%SOURCE_DIR%\version.json" (
    echo   [!] Extraction failed: the pinned archive was incomplete.
    call :cleanup
    pause
    exit /b 1
)

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
robocopy "%SOURCE_DIR%" "%INSTALL_DIR%" /E /XD "%INSTALL_DIR%\data" "%INSTALL_DIR%\venv" "%INSTALL_DIR%\.venv" "%INSTALL_DIR%\node_modules" "%INSTALL_DIR%\frontend\node_modules" /NFL /NDL /NJH /NJS >nul 2>&1
if errorlevel 8 (
    echo   [!] Installation failed while copying the pinned archive.
    call :cleanup
    pause
    exit /b 1
)

fc /b "%SOURCE_DIR%\version.json" "%INSTALL_DIR%\version.json" >nul 2>&1
if errorlevel 1 (
    echo   [!] Installation verification failed; release provenance was not recorded.
    call :cleanup
    pause
    exit /b 1
)

if exist "%SETUP_BACKUP%" (
    if not exist "%INSTALL_DIR%\configs" mkdir "%INSTALL_DIR%\configs"
    copy "%SETUP_BACKUP%" "%INSTALL_DIR%\configs\setup.json" >nul 2>&1
)

python "%INSTALL_DIR%\scripts\write_release_metadata_evidence.py" --root "%INSTALL_DIR%" --git-sha "%SOURCE_COMMIT%" >nul 2>&1
if errorlevel 1 (
    echo   [!] Warning: release provenance could not be recorded.
) else (
    echo   [OK] Release provenance recorded.
)

call :cleanup

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

:cleanup
if defined TEMP_ROOT if exist "%TEMP_ROOT%" rmdir /s /q "%TEMP_ROOT%" >nul 2>&1
exit /b 0
