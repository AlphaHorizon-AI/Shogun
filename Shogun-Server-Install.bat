@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion

title Shogun Server Mode Installer
set "REPO=AlphaHorizon-AI/Shogun"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\Shogun-Server"
set "TEMP_ROOT="
set "ENV_BACKUP="
set "TELEMETRY_MODE=ask"
set "TELEMETRY_NOTICE="
set "SHOW_SETUP_LINK="
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--telemetry=on" set "TELEMETRY_MODE=on"
if /I "%~1"=="--telemetry=off" set "TELEMETRY_MODE=off"
if /I "%~1"=="--show-setup-link" set "SHOW_SETUP_LINK=1"
for /f "tokens=1,* delims==" %%a in ("%~1") do (
  if /I "%%a"=="--accept-telemetry-notice" set "TELEMETRY_NOTICE=%%b"
)
shift
goto parse_args
:args_done
if defined CI if /I "%TELEMETRY_MODE%"=="ask" set "TELEMETRY_MODE=off"
set "INTERACTIVE_OUTPUT="
if not defined CI (
  powershell -NoProfile -Command "if([Environment]::UserInteractive -and -not [Console]::IsOutputRedirected){exit 0}; exit 1"
  if not errorlevel 1 set "INTERACTIVE_OUTPUT=1"
)
set "PRINT_SETUP_LINK=%INTERACTIVE_OUTPUT%"
if defined SHOW_SETUP_LINK set "PRINT_SETUP_LINK=1"

echo.
echo  Shogun Server mode installer
echo  ============================
echo.

docker --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is required.
  echo Download: https://docs.docker.com/desktop/install/windows-install/
  call :cleanup
  pause
  exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Compose v2 is required.
  call :cleanup
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo ERROR: Docker Desktop is not running.
  call :cleanup
  pause
  exit /b 1
)

echo [1/5] Downloading Shogun...
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[IO.Path]::Combine([IO.Path]::GetTempPath(),('shogun-server-install-'+[Guid]::NewGuid().ToString('N')))"`) do set "TEMP_ROOT=%%i"
if not defined TEMP_ROOT (
  echo ERROR: A private temporary directory could not be created.
  goto :failed
)
mkdir "%TEMP_ROOT%" >nul 2>&1
if errorlevel 1 (
  echo ERROR: A private temporary directory could not be created.
  goto :failed
)
set "ENV_BACKUP=%TEMP_ROOT%\env.server.backup"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $sha=(Invoke-RestMethod -UseBasicParsing -Headers @{'User-Agent'='Shogun-Server-Installer'} -Uri 'https://api.github.com/repos/%REPO%/commits/%BRANCH%').sha; if(-not [regex]::IsMatch([string]$sha,'\A[0-9a-fA-F]{40}\z')){exit 1}; $sha.ToLowerInvariant()" 2^>nul`) do set "SOURCE_COMMIT=%%i"
if not defined SOURCE_COMMIT (
  echo ERROR: GitHub did not return a verifiable source commit.
  echo Installation stopped instead of downloading a mutable branch archive.
  goto :failed
)
set "ARCHIVE_URL=https://github.com/%REPO%/archive/%SOURCE_COMMIT%.zip"
set "VCS_REF=%SOURCE_COMMIT%"
echo       Source commit: %SOURCE_COMMIT%
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%ARCHIVE_URL%' -OutFile '%TEMP_ROOT%\shogun.zip'"
if errorlevel 1 goto :failed
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%TEMP_ROOT%\shogun.zip' -DestinationPath '%TEMP_ROOT%\source' -Force"
if errorlevel 1 goto :failed

set "SOURCE_DIR=%TEMP_ROOT%\source\Shogun-%SOURCE_COMMIT%"
if not exist "%SOURCE_DIR%\docker-compose.server.yml" (
  echo ERROR: The downloaded archive does not contain Server mode.
  goto :failed
)

echo [2/5] Installing files in %INSTALL_DIR%...
if exist "%INSTALL_DIR%\.env.server" (
  copy /y "%INSTALL_DIR%\.env.server" "%ENV_BACKUP%" >nul
  if errorlevel 1 (
    echo ERROR: The existing server environment could not be backed up safely.
    goto :failed
  )
)
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
robocopy "%SOURCE_DIR%" "%INSTALL_DIR%" /E /PURGE /XF .env.server /XD .git data logs vault configs >nul
if errorlevel 8 goto :failed
if exist "%ENV_BACKUP%" (
  copy /y "%ENV_BACKUP%" "%INSTALL_DIR%\.env.server" >nul
  if errorlevel 1 (
    echo ERROR: The existing server environment could not be restored.
    goto :failed
  )
  del /f /q "%ENV_BACKUP%" >nul 2>&1
  if exist "%ENV_BACKUP%" (
    echo ERROR: The temporary server environment backup could not be removed.
    goto :failed
  )
  set "ENV_BACKUP="
)

cd /d "%INSTALL_DIR%"
echo [3/5] Configuring secrets...
if not exist ".env.server" (
  copy /y ".env.server.example" ".env.server" >nul
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "POSTGRES_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "APPLICATION_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "VAULT_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "INFRASTRUCTURE_SECRET=%%i"
  for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })"`) do set "A2A_SECRET=%%i"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env.server'; $c=Get-Content -Raw -LiteralPath $p; $c=$c.Replace('change-me-postgres-password','!POSTGRES_SECRET!').Replace('change-me-to-a-random-64-char-string','!APPLICATION_SECRET!').Replace('change-me-to-an-independent-random-64-char-string','!VAULT_SECRET!').Replace('change-me-to-an-independent-infrastructure-admin-token','!INFRASTRUCTURE_SECRET!').Replace('change-me-to-an-independent-a2a-encryption-key','!A2A_SECRET!'); Set-Content -LiteralPath $p -Value $c -Encoding utf8"
  set "POSTGRES_SECRET="
  set "APPLICATION_SECRET="
  set "VAULT_SECRET="
  set "INFRASTRUCTURE_SECRET="
  set "A2A_SECRET="
) else (
  echo       Existing .env.server retained.
)

if /I "%TELEMETRY_MODE%"=="ask" (
  echo.
  echo Help improve Shogun AFM ^(optional^)
  echo Share version, OS family, Docker install type, single-user operation mode, a random
  echo installation ID, and one weekly active signal.
  echo No prompts, files, memory, messages, identities, or credentials are shared.
  echo Privacy: https://www.alphahorizon.io/shogun/telemetry-privacy/
  set /p "TELEMETRY_CHOICE=Share pseudonymous installation statistics? [y/N]: "
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
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env.server'; $c=Get-Content -Raw -LiteralPath $p; $values=@{'SHOGUN_TELEMETRY'='!TELEMETRY_MODE!';'SHOGUN_TELEMETRY_NOTICE_VERSION'='!TELEMETRY_NOTICE!';'VCS_REF'='!VCS_REF!'}; foreach($key in $values.Keys){$line=$key+'='+$values[$key]; if($c -match ('(?m)^'+[regex]::Escape($key)+'=.*$')){$c=[regex]::Replace($c,('(?m)^'+[regex]::Escape($key)+'=.*$'),$line)}else{$c=$c.TrimEnd()+[Environment]::NewLine+$line+[Environment]::NewLine}}; Set-Content -LiteralPath $p -Value $c -Encoding utf8"

set "SERVER_PORT="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$port=8000; foreach($line in [IO.File]::ReadAllLines('.env.server')){if($line.StartsWith('SHOGUN_PORT=')){[int]$candidate=0; if(-not [int]::TryParse($line.Substring(12).Trim(),[ref]$candidate) -or $candidate -lt 1 -or $candidate -gt 65535){exit 1}; $port=$candidate; break}}; $port"`) do set "SERVER_PORT=%%i"
if not defined SERVER_PORT (
  echo ERROR: SHOGUN_PORT must be an integer from 1 through 65535.
  goto :failed
)
set "SETUP_ORIGIN=http://127.0.0.1:%SERVER_PORT%"
set "HEALTH_URL=%SETUP_ORIGIN%/api/v1/health"

echo [4/5] Building and starting Shogun Server...
docker compose --env-file .env.server -f docker-compose.server.yml up -d --build
if errorlevel 1 goto :failed

echo [5/5] Waiting for The Tenshu...
for /L %%i in (1,1,90) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%HEALTH_URL%'; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
  if not errorlevel 1 goto :ready
  timeout /t 2 /nobreak >nul
)

echo ERROR: Shogun did not become healthy in time.
docker compose --env-file .env.server -f docker-compose.server.yml ps
goto :failed

:ready
call :cleanup
if errorlevel 1 (
  echo ERROR: Shogun started, but temporary installer data could not be removed.
  echo Delete the reported temporary directory before considering installation complete.
  pause
  exit /b 1
)
echo.
echo Shogun Server is ready at %SETUP_ORIGIN%.
echo Connect to Shogun through The Tenshu or Telegram.
echo.
if defined PRINT_SETUP_LINK (
  set "SETUP_URL="
  for /f "usebackq delims=" %%i in (`docker compose --env-file .env.server -f docker-compose.server.yml exec -T shogun python -m shogun.setup_link --origin "%SETUP_ORIGIN%" 2^>nul`) do set "SETUP_URL=%%i"
  if not defined SETUP_URL (
    echo ERROR: Shogun started, but a secure Primary Admin setup link could not be created.
    echo Run the private-terminal command documented in README.md from %INSTALL_DIR%.
    pause
    exit /b 1
  )
  echo Private Primary Admin bootstrap link ^(treat the fragment as a credential^):
  echo !SETUP_URL!
  echo The browser removes the fragment before the first API request.
  if defined INTERACTIVE_OUTPUT start "" "!SETUP_URL!"
  set "SETUP_URL="
) else (
  echo The credential-bearing setup link was withheld because output is redirected.
  echo From a private operator terminal in %INSTALL_DIR%, run:
  echo docker compose --env-file .env.server -f docker-compose.server.yml exec -T shogun python -m shogun.setup_link --origin %SETUP_ORIGIN%
)
pause
exit /b 0

:failed
call :cleanup
echo.
echo Installation failed. Review the error above.
pause
exit /b 1

:cleanup
set "CLEANUP_FAILED="
if defined ENV_BACKUP if exist "%ENV_BACKUP%" del /f /q "%ENV_BACKUP%" >nul 2>&1
if defined TEMP_ROOT if exist "%TEMP_ROOT%" (
  set "SHOGUN_SERVER_INSTALL_CLEANUP_ROOT=%TEMP_ROOT%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=[IO.Path]::GetFullPath($env:SHOGUN_SERVER_INSTALL_CLEANUP_ROOT); $temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar); $parent=[IO.Path]::GetFullPath([IO.Path]::GetDirectoryName($root)).TrimEnd([IO.Path]::DirectorySeparatorChar); $leaf=[IO.Path]::GetFileName($root); if(-not [String]::Equals($parent,$temp,[StringComparison]::OrdinalIgnoreCase) -or $leaf -notmatch '\Ashogun-server-install-[0-9a-fA-F]{32}\z'){exit 2}; Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction Stop" >nul 2>&1
  set "SHOGUN_SERVER_INSTALL_CLEANUP_ROOT="
)
if defined TEMP_ROOT if exist "%TEMP_ROOT%" set "CLEANUP_FAILED=1"
if defined CLEANUP_FAILED (
  echo WARNING: Temporary installer data remains at "%TEMP_ROOT%".
  echo Remove that directory before retrying or continuing.
  set "ENV_BACKUP="
  exit /b 1
)
set "ENV_BACKUP="
set "TEMP_ROOT="
exit /b 0
