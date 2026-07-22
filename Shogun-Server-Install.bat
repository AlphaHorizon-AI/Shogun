@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

title Shogun Server Mode Installer
set "REPO=AlphaHorizon-AI/Shogun"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\Shogun-Server"
set "ARCHIVE_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "TEMP_ROOT=%TEMP%\shogun-server-install"

echo.
echo  Shogun Server mode installer
echo  ============================
echo.

docker --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is required.
  echo Download: https://docs.docker.com/desktop/install/windows-install/
  pause
  exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Compose v2 is required.
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is not running.
  pause
  exit /b 1
)

echo [1/5] Downloading Shogun...
if exist "%TEMP_ROOT%" rmdir /s /q "%TEMP_ROOT%"
mkdir "%TEMP_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%ARCHIVE_URL%' -OutFile '%TEMP_ROOT%\shogun.zip'"
if errorlevel 1 goto :failed
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%TEMP_ROOT%\shogun.zip' -DestinationPath '%TEMP_ROOT%\source' -Force"
if errorlevel 1 goto :failed

set "SOURCE_DIR=%TEMP_ROOT%\source\Shogun-%BRANCH%"
if not exist "%SOURCE_DIR%\docker-compose.server.yml" (
  echo ERROR: The downloaded archive does not contain Server mode.
  goto :failed
)

echo [2/5] Installing files in %INSTALL_DIR%...
if exist "%INSTALL_DIR%\.env.server" copy /y "%INSTALL_DIR%\.env.server" "%TEMP_ROOT%\env.server.backup" >nul
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
robocopy "%SOURCE_DIR%" "%INSTALL_DIR%" /E /PURGE /XF .env.server /XD .git data logs vault configs >nul
if errorlevel 8 goto :failed
if exist "%TEMP_ROOT%\env.server.backup" copy /y "%TEMP_ROOT%\env.server.backup" "%INSTALL_DIR%\.env.server" >nul

cd /d "%INSTALL_DIR%"
echo [3/5] Configuring secrets...
if not exist ".env.server" (
  copy /y ".env.server.example" ".env.server" >nul
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "-join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })"`) do set "POSTGRES_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "-join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })"`) do set "APPLICATION_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "-join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })"`) do set "VAULT_SECRET=%%i"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env.server'; $c=Get-Content -Raw -LiteralPath $p; $c=$c.Replace('change-me-postgres-password','!POSTGRES_SECRET!').Replace('change-me-to-a-random-64-char-string','!APPLICATION_SECRET!').Replace('change-me-to-an-independent-random-64-char-string','!VAULT_SECRET!'); Set-Content -LiteralPath $p -Value $c -Encoding utf8"
) else (
  echo       Existing .env.server retained.
)

echo [4/5] Building and starting Shogun Server...
docker compose --env-file .env.server -f docker-compose.server.yml up -d --build
if errorlevel 1 goto :failed

echo [5/5] Waiting for The Tenshu...
for /L %%i in (1,1,90) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8000/api/v1/health'; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
  if not errorlevel 1 goto :ready
  timeout /t 2 /nobreak >nul
)

echo ERROR: Shogun did not become healthy in time.
docker compose --env-file .env.server -f docker-compose.server.yml ps
goto :failed

:ready
if exist "%TEMP_ROOT%" rmdir /s /q "%TEMP_ROOT%"
echo.
echo Shogun Server is ready: http://127.0.0.1:8000/setup
echo Team members should connect through Telegram or Microsoft Teams.
echo.
start "" "http://127.0.0.1:8000/setup"
pause
exit /b 0

:failed
echo.
echo Installation failed. Review the error above.
pause
exit /b 1
