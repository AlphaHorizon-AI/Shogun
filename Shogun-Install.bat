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
set "NEED_RESTART=0"

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

    winget --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo   [+] Installing Python automatically via winget...
        echo       This may take a minute. A UAC prompt may appear - click Yes.
        echo.
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        if !ERRORLEVEL! equ 0 (
            echo.
            echo   [OK] Python installed successfully.
            set "NEED_RESTART=1"
        ) else (
            echo   [!] Automatic install failed. Trying direct download...
            call :python_manual
        )
    ) else (
        call :python_manual
    )
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

    winget --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo   [+] Installing Node.js automatically via winget...
        echo       This may take a minute.
        echo.
        winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
        if !ERRORLEVEL! equ 0 (
            echo.
            echo   [OK] Node.js installed successfully.
            set "NEED_RESTART=1"
        ) else (
            echo   [!] Automatic install failed. Trying direct download...
            call :node_manual
        )
    ) else (
        call :node_manual
    )
) else (
    for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do (
        echo   [OK] Node.js %%v
    )
)

:: -- Restart check ----------------------------------------------
if %NEED_RESTART% equ 1 (
    echo.
    echo  ======================================================
    echo   Prerequisites were just installed.
    echo   The installer needs to restart to pick them up.
    echo  ======================================================
    echo.
    echo   This window will close and reopen automatically.
    echo.
    timeout /t 5 /nobreak >nul
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b 0
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

:: -- Subroutines ------------------------------------------------

:python_manual
echo   [+] Downloading Python installer...
set "PY_INSTALLER=%TEMP%\python-installer.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe', '%PY_INSTALLER%')"

if exist "%PY_INSTALLER%" (
    echo   [+] Running Python installer (this may take a few minutes)...
    echo       Please follow the installer. Make sure to check 'Add Python to PATH'.
    echo.
    start /wait "" "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    if !ERRORLEVEL! equ 0 (
        echo   [OK] Python installed successfully.
        set "NEED_RESTART=1"
        del "%PY_INSTALLER%" >nul 2>&1
    ) else (
        echo   [!] Python installation failed.
        pause
        exit /b 1
    )
) else (
    echo   [!] Could not download Python.
    pause
    exit /b 1
)
goto :eof

:node_manual
echo   [+] Downloading Node.js installer...
set "NODE_INSTALLER=%TEMP%\nodejs-installer.msi"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://nodejs.org/dist/v22.12.0/node-v22.12.0-x64.msi', '%NODE_INSTALLER%')"

if exist "%NODE_INSTALLER%" (
    echo   [+] Running Node.js installer...
    echo.
    start /wait "" msiexec /i "%NODE_INSTALLER%" /qn
    if !ERRORLEVEL! equ 0 (
        echo   [OK] Node.js installed successfully.
        set "NEED_RESTART=1"
        del "%NODE_INSTALLER%" >nul 2>&1
    ) else (
        echo   [!] Node.js installation failed.
        pause
        exit /b 1
    )
) else (
    echo   [!] Could not download Node.js.
    pause
    exit /b 1
)
goto :eof
