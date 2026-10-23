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

set "UPDATE_PYTHON="
if exist "%INSTALL_DIR%\venv\Scripts\python.exe" set "UPDATE_PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe"
if exist "%INSTALL_DIR%\.venv\Scripts\python.exe" set "UPDATE_PYTHON=%INSTALL_DIR%\.venv\Scripts\python.exe"
if not defined UPDATE_PYTHON (
    echo  ERROR: The application virtual environment could not be identified.
    exit /b 1
)
if not exist "%SOURCE_DIR%\shogun\security_maintenance.py" (
    echo  ERROR: This release lacks the authenticated security bootstrap. Nothing was applied.
    exit /b 1
)
echo  Stop Shogun before continuing this operator-assisted update.
"%UPDATE_PYTHON%" "%SOURCE_DIR%\shogun\security_maintenance.py" bootstrap
if errorlevel 1 exit /b 1
"%UPDATE_PYTHON%" "%SOURCE_DIR%\scripts\apply_prepared_update.py" --root "%INSTALL_DIR%" --source "%SOURCE_DIR%" --git-sha "%SOURCE_COMMIT%"
if errorlevel 1 (
    echo  ERROR: Update preparation or installation failed. No success is being reported.
    echo  Keep the downloaded source for diagnosis; review the reported recovery status.
    pause
    exit /b 1
)
powershell -NoProfile -Command "$root=[IO.Path]::GetFullPath($env:WORK_DIR); $parent=[IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')+'\'; if($root.StartsWith($parent,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($root) -match '\Ashogun-update-[0-9a-f]{32}\z'){Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction Stop}else{exit 1}"
if errorlevel 1 echo  WARNING: Temporary update files remain in the reported working directory.

echo.
echo  Application files installed. Existing data, settings, vault, and logs were preserved.
echo  Restart Shogun through its original launcher and verify activation.
echo.
pause
