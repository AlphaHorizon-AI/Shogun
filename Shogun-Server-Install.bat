@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

title Shogun Server Mode Installer
set "REPO=AlphaHorizon-AI/Shogun"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\Shogun-Server"
set "ARCHIVE_URL=https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip"
set "TEMP_ROOT=%TEMP%\shogun-server-install"
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
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "POSTGRES_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "APPLICATION_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "VAULT_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "INFRASTRUCTURE_SECRET=%%i"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env.server'; $c=Get-Content -Raw -LiteralPath $p; $c=$c.Replace('change-me-postgres-password','!POSTGRES_SECRET!').Replace('change-me-to-a-random-64-char-string','!APPLICATION_SECRET!').Replace('change-me-to-an-independent-random-64-char-string','!VAULT_SECRET!').Replace('change-me-to-an-independent-infrastructure-admin-token','!INFRASTRUCTURE_SECRET!'); Set-Content -LiteralPath $p -Value $c -Encoding utf8"
) else (
  echo       Existing .env.server retained.
)

if /I "%TELEMETRY_MODE%"=="ask" (
  echo.
  echo Help improve Shogun AFM ^(optional^)
  echo Share version, OS family, Docker install type, Team Mode, a random
  echo installation ID, and one weekly active signal.
  echo No prompts, files, memory, messages, identities, or credentials are shared.
  echo Privacy: https://www.alphahorizon.io/shogun/telemetry-privacy/
  set /p "TELEMETRY_CHOICE=Share anonymous installation statistics? [y/N]: "
  if /I "!TELEMETRY_CHOICE!"=="y" (
    set "TELEMETRY_MODE=on"
    set "TELEMETRY_NOTICE=1.0"
  ) else (
    set "TELEMETRY_MODE=off"
  )
)
if /I "%TELEMETRY_MODE%"=="on" if not "%TELEMETRY_NOTICE%"=="1.0" (
  echo Telemetry remains disabled: notice version 1.0 was not explicitly accepted.
  set "TELEMETRY_MODE=off"
  set "TELEMETRY_NOTICE="
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env.server'; $c=Get-Content -Raw -LiteralPath $p; $values=@{'SHOGUN_TELEMETRY'='!TELEMETRY_MODE!';'SHOGUN_TELEMETRY_NOTICE_VERSION'='!TELEMETRY_NOTICE!'}; foreach($key in $values.Keys){$line=$key+'='+$values[$key]; if($c -match ('(?m)^'+[regex]::Escape($key)+'=.*$')){$c=[regex]::Replace($c,('(?m)^'+[regex]::Escape($key)+'=.*$'),$line)}else{$c=$c.TrimEnd()+[Environment]::NewLine+$line+[Environment]::NewLine}}; Set-Content -LiteralPath $p -Value $c -Encoding utf8"

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
