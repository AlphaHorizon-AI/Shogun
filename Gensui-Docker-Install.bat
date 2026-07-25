@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ===============================================================
::  GENSUI - One-Click Docker Downloader & Installer (Windows)
::
::  This is a STANDALONE file. Download it, double-click it,
::  and Gensui will be deployed via Docker Desktop automatically.
::  Prerequisites: Docker Desktop
:: ===============================================================

title Gensui Server - Docker Installer

echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :      GENSUI - Agent Fleet Management                     :
echo  :      One-Click Docker Installer                          :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

:: -- Configuration ----------------------------------------------
set "REPO=AlphaHorizon-AI/Shogun"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\Gensui-Server"
set "ZIP_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "ZIP_FILE=%TEMP%\gensui-docker-download.zip"

:: ══════════════════════════════════════════════════════════════
echo  ======================================================
echo   [1/6] Checking prerequisites...
echo  ======================================================
echo.

docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Docker is not installed.
    echo.
    echo   Gensui server requires Docker Desktop.
    echo   Please download and install it from: https://docs.docker.com/desktop/install/windows/
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=1-3 delims=," %%a in ('docker --version') do (
        echo   [OK] %%a
    )
)

docker compose version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [!] Docker Compose is not installed.
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=1-4 delims= " %%a in ('docker compose version') do (
        echo   [OK] %%a %%b %%c %%d
    )
)
echo.

:: ══════════════════════════════════════════════════════════════
echo  ======================================================
echo   [2/6] Downloading Gensui from GitHub...
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

:: ══════════════════════════════════════════════════════════════
echo  ======================================================
echo   [3/6] Extracting to %INSTALL_DIR%...
echo  ======================================================
echo.

if exist "%INSTALL_DIR%\.env" (
    copy "%INSTALL_DIR%\.env" "%TEMP%\gensui_docker_setup_backup.env" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TEMP%\gensui-docker-extract' -Force"

if exist "%TEMP%\gensui-docker-extract\Shogun-%BRANCH%\gensui" (
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    robocopy "%TEMP%\gensui-docker-extract\Shogun-%BRANCH%\gensui" "%INSTALL_DIR%" /E /XD data certs /NFL /NDL /NJH /NJS >nul 2>&1
)

if exist "%TEMP%\gensui_docker_setup_backup.env" (
    copy "%TEMP%\gensui_docker_setup_backup.env" "%INSTALL_DIR%\.env" >nul 2>&1
    del "%TEMP%\gensui_docker_setup_backup.env" >nul 2>&1
)

del "%ZIP_FILE%" >nul 2>&1
rmdir /s /q "%TEMP%\gensui-docker-extract" >nul 2>&1

echo   [OK] Extracted to %INSTALL_DIR%
echo.

:: ══════════════════════════════════════════════════════════════
echo  ======================================================
echo   [4/6] Configuring environment...
echo  ======================================================
echo.

cd /d "%INSTALL_DIR%"

if not exist ".env" (
    copy ".env.example" ".env" >nul 2>&1
    :: Generate random JWT secret using PowerShell
    for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 48; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b).Replace('=', '').Replace('+', '').Replace('/', '')"`) do set JWT_SECRET=%%i
    for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b).Replace('=', '').Replace('+', '').Replace('/', '')"`) do set ADMIN_SECRET=%%i
    powershell -NoProfile -Command "$c=Get-Content -Raw .env; $c=$c.Replace('change-me-to-a-random-64-char-string','%JWT_SECRET%').Replace('change-me-to-a-random-admin-password','%ADMIN_SECRET%'); Set-Content -Encoding Ascii .env $c"
    echo   [OK] .env created with secure random JWT and admin secrets.
    echo   [i] The generated admin password is stored in %INSTALL_DIR%\.env.
) else (
    echo   [OK] .env already exists — keeping existing config.
)
echo.

:: ══════════════════════════════════════════════════════════════
echo  ======================================================
echo   [5/6] TLS Setup (HTTPS)...
echo  ======================================================
echo.

set "USE_TLS=false"
set "PROFILE=default"

set /p ENABLE_HTTPS="Do you want to enable HTTPS with Nginx? (y/n) [n]: "
if /i "%ENABLE_HTTPS%"=="y" (
    set "USE_TLS=true"
    set "PROFILE=server"
    if not exist "certs" mkdir certs
    
    if not exist "certs\gensui.crt" (
        echo.
        echo No TLS certificates found in .\certs\
        set /p GEN_CERT="Would you like to generate a self-signed certificate now? (Y/n): "
        if /i not "!GEN_CERT!"=="n" (
            echo   Generating self-signed certificate...
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout certs\gensui.key -out certs\gensui.crt -subj "/C=US/ST=State/L=City/O=Shogun/CN=localhost" >nul 2>&1
            if !ERRORLEVEL! neq 0 (
                echo   [!] openssl is not installed or not in PATH. Could not generate cert.
                echo   [!] Please place 'gensui.crt' and 'gensui.key' in %INSTALL_DIR%\certs\ before continuing.
                pause
            ) else (
                echo   [OK] Generated self-signed certs in .\certs\
            )
        ) else (
            echo   [!] Please place 'gensui.crt' and 'gensui.key' in %INSTALL_DIR%\certs\ before continuing.
            pause
        )
    ) else (
        echo   [OK] TLS certificates found in .\certs\
    )
) else (
    echo   HTTPS setup skipped. Proceeding with basic HTTP setup.
)
echo.

:: ══════════════════════════════════════════════════════════════
echo  ======================================================
echo   [6/6] Launching Gensui with Docker Compose...
echo  ======================================================
echo.

if "%USE_TLS%"=="true" (
    echo   Running: docker compose --profile server up -d
    docker compose --profile server up -d
) else (
    echo   Running: docker compose up -d
    docker compose up -d
)

echo.
echo  +----------------------------------------------------------+
echo  :                                                          :
echo  :   Docker deployment complete!                            :
echo  :                                                          :
if "%USE_TLS%"=="true" (
    echo  :   Gensui is starting at https://localhost                :
) else (
    echo  :   Gensui is starting at http://localhost:8787            :
)
echo  :   API docs at http(s)://localhost(:8787)/docs            :
echo  :                                                          :
echo  :   Admin: admin@gensui.local                              :
echo  :   Password: stored in the protected .env file            :
echo  :                                                          :
echo  :   To stop: docker compose down                           :
echo  :                                                          :
echo  +----------------------------------------------------------+
echo.

pause
