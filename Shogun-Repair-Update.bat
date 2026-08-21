@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions DisableDelayedExpansion
title Shogun - In-place Update Repair

set "REPO=AlphaHorizon-AI/Shogun"
set "BRANCH=main"
set "INSTALL_DIR=%USERPROFILE%\Shogun"
if exist "%~dp0version.json" set "INSTALL_DIR=%~dp0"
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[IO.Path]::Combine([IO.Path]::GetTempPath(),('shogun-update-'+[Guid]::NewGuid().ToString('N')))"`) do set "WORK_DIR=%%i"
if not defined WORK_DIR (
    echo  ERROR: A private temporary directory could not be created.
    pause
    exit /b 1
)
set "ZIP_FILE=%WORK_DIR%\shogun-update.zip"
set "EXTRACT_DIR=%WORK_DIR%\extract"
set "COMMIT_FILE=%WORK_DIR%\source-commit.txt"

echo.
echo  SHOGUN IN-PLACE UPDATE
echo  -----------------------
echo  Installation: %INSTALL_DIR%
echo.

if not exist "%INSTALL_DIR%\version.json" (
    echo  ERROR: Shogun was not found at "%INSTALL_DIR%".
    echo  Place this file inside the Shogun folder and run it again.
    pause
    exit /b 1
)

mkdir "%EXTRACT_DIR%" >nul 2>&1

echo  Downloading the latest update...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; try { $h=@{Accept='application/vnd.github+json';'User-Agent'='Shogun-Repair-Updater'}; $sha=(Invoke-RestMethod -UseBasicParsing -Headers $h -Uri 'https://api.github.com/repos/%REPO%/commits/%BRANCH%').sha; if(-not [regex]::IsMatch([string]$sha,'\A[0-9a-fA-F]{40}\z')){throw 'Invalid source commit'}; $sha=$sha.ToLowerInvariant(); Invoke-WebRequest -UseBasicParsing -Headers @{'User-Agent'='Shogun-Repair-Updater'} -Uri ('https://github.com/%REPO%/archive/'+$sha+'.zip') -OutFile '%ZIP_FILE%'; Add-Type -AssemblyName System.IO.Compression.FileSystem; $z=[IO.Compression.ZipFile]::OpenRead('%ZIP_FILE%'); $z.Dispose(); Set-Content -LiteralPath '%COMMIT_FILE%' -Value $sha -Encoding Ascii -NoNewline } catch { Remove-Item -LiteralPath '%ZIP_FILE%' -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '%COMMIT_FILE%' -Force -ErrorAction SilentlyContinue; exit 1 }" >nul 2>&1

if not exist "%ZIP_FILE%" (
    echo.
    echo  GitHub requires access for this update source.
    echo  Enter a fine-grained GitHub token with read access to Shogun.
    echo  The token will be hidden and is not saved by this repair tool.
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ProgressPreference='SilentlyContinue'; $s=Read-Host 'Token' -AsSecureString; $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try { $t=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b); $h=@{Authorization=('Bearer '+$t);Accept='application/vnd.github+json';'User-Agent'='Shogun-Repair-Updater'}; $sha=(Invoke-RestMethod -UseBasicParsing -Headers $h -Uri 'https://api.github.com/repos/%REPO%/commits/%BRANCH%').sha; if(-not [regex]::IsMatch([string]$sha,'\A[0-9a-fA-F]{40}\z')){throw 'Invalid source commit'}; $sha=$sha.ToLowerInvariant(); Invoke-WebRequest -UseBasicParsing -Headers $h -Uri ('https://api.github.com/repos/%REPO%/zipball/'+$sha) -OutFile '%ZIP_FILE%'; Add-Type -AssemblyName System.IO.Compression.FileSystem; $z=[IO.Compression.ZipFile]::OpenRead('%ZIP_FILE%'); $z.Dispose(); Set-Content -LiteralPath '%COMMIT_FILE%' -Value $sha -Encoding Ascii -NoNewline } catch { Remove-Item -LiteralPath '%ZIP_FILE%' -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '%COMMIT_FILE%' -Force -ErrorAction SilentlyContinue; exit 1 } finally { if($b -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)} }"
)

if not exist "%ZIP_FILE%" (
    echo  ERROR: The update could not be downloaded. Check the token and connection.
    pause
    exit /b 1
)
if not exist "%COMMIT_FILE%" (
    echo  ERROR: The update source could not be tied to a verified commit.
    pause
    exit /b 1
)
set /p "SOURCE_COMMIT="<"%COMMIT_FILE%"

echo  Extracting update...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP_FILE%' -DestinationPath '%EXTRACT_DIR%' -Force"
for /d %%D in ("%EXTRACT_DIR%\*") do if not defined SOURCE_DIR set "SOURCE_DIR=%%~fD"

if not defined SOURCE_DIR (
    echo  ERROR: The downloaded update package was empty.
    pause
    exit /b 1
)

echo  Updating application files while preserving your data and settings...
robocopy "%SOURCE_DIR%" "%INSTALL_DIR%" /E /R:2 /W:1 ^
  /XD "%INSTALL_DIR%\data" "%INSTALL_DIR%\venv" "%INSTALL_DIR%\.venv" "%INSTALL_DIR%\node_modules" "%INSTALL_DIR%\frontend\node_modules" "%INSTALL_DIR%\configs" "%INSTALL_DIR%\vault" "%INSTALL_DIR%\logs" "%INSTALL_DIR%\scratch" "%INSTALL_DIR%\.states" "%INSTALL_DIR%\.git" __pycache__ ^
  /XF .env >nul
if errorlevel 8 (
    echo  ERROR: Some application files could not be updated.
    pause
    exit /b 1
)
fc /b "%SOURCE_DIR%\version.json" "%INSTALL_DIR%\version.json" >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Installed release metadata does not match the pinned update package.
    echo  Release provenance was not recorded.
    pause
    exit /b 1
)

set "PROVENANCE_PYTHON=python"
if exist "%INSTALL_DIR%\.venv\Scripts\python.exe" set "PROVENANCE_PYTHON=%INSTALL_DIR%\.venv\Scripts\python.exe"
if exist "%INSTALL_DIR%\venv\Scripts\python.exe" set "PROVENANCE_PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe"
"%PROVENANCE_PYTHON%" "%INSTALL_DIR%\scripts\write_release_metadata_evidence.py" --root "%INSTALL_DIR%" --git-sha "%SOURCE_COMMIT%" >nul 2>&1
if errorlevel 1 (
    echo  WARNING: The update was applied, but release provenance could not be recorded.
) else (
    echo  Release provenance recorded for %SOURCE_COMMIT%.
)

echo  Refreshing dependencies in the existing environment...
if exist "%INSTALL_DIR%\.venv\Scripts\python.exe" (
    "%INSTALL_DIR%\.venv\Scripts\python.exe" -m pip install -e "%INSTALL_DIR%[office]" --disable-pip-version-check
) else if exist "%INSTALL_DIR%\venv\Scripts\python.exe" (
    "%INSTALL_DIR%\venv\Scripts\python.exe" -m pip install -e "%INSTALL_DIR%[office]" --disable-pip-version-check
)

if exist "%INSTALL_DIR%\frontend\package.json" (
    pushd "%INSTALL_DIR%\frontend"
    call npm install --silent
    call npm run build --silent
    popd
)

rmdir /s /q "%WORK_DIR%" >nul 2>&1

echo.
echo  Update complete. Your data, settings, vault, and existing environment were preserved.
echo  Restart Shogun now. Future updates can be installed from the Updates screen.
echo.
pause
