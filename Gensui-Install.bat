@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

:: ===============================================================
::  GENSUI - One-Click Downloader & Installer (Windows)
::
::  This is a STANDALONE file. Download it, double-click it,
::  and Gensui will be installed automatically. No git required.
::  Prerequisites (Python, Node.js) will be installed for you.
:: ===============================================================

title Gensui - Installing...

echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :      GENSUI - Agent Fleet Management One-Click Installer     :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

:: -- Configuration ----------------------------------------------
:: This is the reviewed main revision authorized for this installer release.
:: Do not replace it with a branch or tag archive: both are movable references.
set "REPO=AlphaHorizon-AI/Shogun"
set "SOURCE_SHA=0774ce5998400963541a19b78e81e97dfea0ad4e"
set "INSTALL_DIR=%USERPROFILE%\Gensui"
set "ZIP_URL=https://github.com/%REPO%/archive/%SOURCE_SHA%.zip"
set "EXIT_CODE=1"

:: -- Check and install prerequisites ----------------------------
echo  ======================================================
echo   Checking prerequisites...
echo  ======================================================
echo.

:: -- Python -----------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo   [!] Python is not installed.
    echo.
    echo   Gensui requires Python 3.10+ to run.
    echo   Please download and install it from: https://www.python.org/downloads/
    echo   Be sure to check "Add python.exe to PATH" during installation.
    echo.
    goto :cleanup
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo   [!] Unsupported Python version. Gensui requires Python 3.10 or newer.
    goto :cleanup
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do echo   [OK] Python %%v

:: -- Node.js ----------------------------------------------------
node --version >nul 2>&1
if errorlevel 1 (
    echo   [!] Node.js is not installed.
    echo.
    echo   Gensui requires Node.js 22.12 or newer, but below 25.
    echo   Please download and install it from: https://nodejs.org/
    echo.
    goto :cleanup
)
for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do set "GENSUI_NODE_VERSION=%%v"
python -c "import os; p=tuple(map(int, os.environ['GENSUI_NODE_VERSION'].lstrip('v').split('.')[:2])); raise SystemExit(0 if (22, 12) <= p < (25, 0) else 1)" >nul 2>&1
if errorlevel 1 (
    echo   [!] Unsupported Node.js !GENSUI_NODE_VERSION!. Gensui requires 22.12 or newer, but below 25.
    goto :cleanup
)
echo   [OK] Node.js !GENSUI_NODE_VERSION!
set "GENSUI_NODE_VERSION="

echo.

:: -- Private temporary workspace --------------------------------
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString('N')"`) do set "TEMP_ID=%%i"
if not defined TEMP_ID (
    echo   [!] Could not create a private installer workspace identifier.
    goto :cleanup
)
set "GENSUI_TEMP_ROOT=%TEMP%\gensui-install-!TEMP_ID!"
set "ZIP_FILE=!GENSUI_TEMP_ROOT!\source.zip"
set "EXTRACT_DIR=!GENSUI_TEMP_ROOT!\extract"
set "BACKUP_FILE=!GENSUI_TEMP_ROOT!\existing.env"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=$env:GENSUI_TEMP_ROOT; [IO.Directory]::CreateDirectory($p) | Out-Null; $id=[Security.Principal.WindowsIdentity]::GetCurrent().User; $acl=New-Object System.Security.AccessControl.DirectorySecurity; $acl.SetAccessRuleProtection($true,$false); $rule=New-Object System.Security.AccessControl.FileSystemAccessRule($id,'FullControl','ContainerInherit,ObjectInherit','None','Allow'); $acl.SetAccessRule($rule); Set-Acl -LiteralPath $p -AclObject $acl -ErrorAction Stop"
if errorlevel 1 (
    echo   [!] Could not create a private installer workspace.
    goto :cleanup
)

:: -- Download ---------------------------------------------------
echo  ======================================================
echo   [+] Downloading Gensui from GitHub...
echo  ======================================================
echo.
echo       %ZIP_URL%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri $env:ZIP_URL -OutFile $env:ZIP_FILE -ErrorAction Stop"

if errorlevel 1 (
    echo   [!] Download failed. Please check your internet connection.
    goto :cleanup
)
if not exist "!ZIP_FILE!" (
    echo   [!] Download did not produce the expected archive.
    goto :cleanup
)
echo   [OK] Download complete.
echo.

:: -- Extract ----------------------------------------------------
echo   [+] Extracting to %INSTALL_DIR%...

if exist "%INSTALL_DIR%\.env" (
    copy /y "%INSTALL_DIR%\.env" "!BACKUP_FILE!" >nul
    if errorlevel 1 (
        echo   [!] Could not protect the existing Gensui configuration.
        goto :cleanup
    )
    set "HAD_ENV_BACKUP=1"
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "[IO.Directory]::CreateDirectory($env:EXTRACT_DIR) | Out-Null; Expand-Archive -LiteralPath $env:ZIP_FILE -DestinationPath $env:EXTRACT_DIR -Force -ErrorAction Stop"
if errorlevel 1 (
    echo   [!] The downloaded archive could not be extracted.
    goto :cleanup
)

set "SOURCE_DIR=!EXTRACT_DIR!\Shogun-%SOURCE_SHA%"
if not exist "!SOURCE_DIR!" (
    echo   [!] The archive did not contain the authorized source revision.
    goto :cleanup
)

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if errorlevel 1 (
    echo   [!] Could not create %INSTALL_DIR%.
    goto :cleanup
)
robocopy "!SOURCE_DIR!" "%INSTALL_DIR%" /E /XD "%INSTALL_DIR%\data" "%INSTALL_DIR%\venv" "%INSTALL_DIR%\.venv" "%INSTALL_DIR%\node_modules" "%INSTALL_DIR%\frontend\node_modules" /NFL /NDL /NJH /NJS >nul
set "ROBOCOPY_EXIT=!ERRORLEVEL!"
if !ROBOCOPY_EXIT! GEQ 8 (
    echo   [!] Copying the authorized source failed with code !ROBOCOPY_EXIT!.
    goto :cleanup
)

call :restore_backup
if errorlevel 1 (
    echo   [!] Could not restore the existing Gensui configuration.
    goto :cleanup
)
call :purge_temp
if errorlevel 1 (
    echo   [!] Could not securely remove the temporary installer workspace.
    goto :cleanup
)

echo   [OK] Extracted to %INSTALL_DIR%
echo.

:: -- Run installer ----------------------------------------------
echo  ======================================================
echo   [+] Running Gensui installer...
echo  ======================================================
echo.

cd /d "%INSTALL_DIR%\gensui"
if exist "install.bat" (
    call install.bat
    set "EXIT_CODE=!ERRORLEVEL!"
    if not !EXIT_CODE!==0 echo   [!] Gensui installer failed with code !EXIT_CODE!.
    goto :cleanup
) else (
    echo   [!] Error: install.bat not found in %INSTALL_DIR%
    goto :cleanup
)

:restore_backup
if not defined HAD_ENV_BACKUP exit /b 0
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /y "!BACKUP_FILE!" "%INSTALL_DIR%\.env" >nul
if errorlevel 1 exit /b 1
del /f /q "!BACKUP_FILE!" >nul 2>&1
if exist "!BACKUP_FILE!" exit /b 1
set "HAD_ENV_BACKUP="
exit /b 0

:purge_temp
if not defined GENSUI_TEMP_ROOT exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path -LiteralPath $env:GENSUI_TEMP_ROOT) { Remove-Item -LiteralPath $env:GENSUI_TEMP_ROOT -Recurse -Force -ErrorAction Stop }"
if errorlevel 1 exit /b 1
if exist "!GENSUI_TEMP_ROOT!" exit /b 1
set "GENSUI_TEMP_ROOT="
set "ZIP_FILE="
set "EXTRACT_DIR="
set "BACKUP_FILE="
exit /b 0

:cleanup
if defined HAD_ENV_BACKUP (
    call :restore_backup
    if errorlevel 1 set "EXIT_CODE=1"
)
if defined GENSUI_TEMP_ROOT (
    call :purge_temp
    if errorlevel 1 set "EXIT_CODE=1"
)
endlocal & exit /b %EXIT_CODE%
