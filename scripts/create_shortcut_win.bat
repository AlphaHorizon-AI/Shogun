:: ===============================================================
::  Creates a "Shogun" desktop shortcut pointing to start.bat
::  Called automatically at the end of install.bat
:: ===============================================================
@echo off
setlocal

:: Resolve the Shogun root directory to a FULL ABSOLUTE path
:: (one level up from this script's location)
pushd "%~dp0.."
set "SHOGUN_DIR=%CD%"
popd

set "SHORTCUT_NAME=Shogun - The Tenshu"
set "DESKTOP=%USERPROFILE%\Desktop"
set "TARGET=%SHOGUN_DIR%\start.bat"

:: Find the icon file (absolute path)
set "ICON=%SHOGUN_DIR%\frontend\public\shogun.ico"
if not exist "%ICON%" set "ICON=%SHOGUN_DIR%\frontend\public\shogun-logo.ico"
if not exist "%ICON%" set "ICON="

:: Create shortcut via PowerShell with fully resolved absolute paths
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; "^
  "$sc = $ws.CreateShortcut('%DESKTOP%\%SHORTCUT_NAME%.lnk'); "^
  "$sc.TargetPath = '%TARGET%'; "^
  "$sc.WorkingDirectory = '%SHOGUN_DIR%'; "^
  "$sc.Description = 'Launch the Shogun AI Agent Framework'; "^
  "$sc.WindowStyle = 1; "^
  "if ('%ICON%' -ne '') { $sc.IconLocation = '%ICON%,0' }; "^
  "$sc.Save()"

if %ERRORLEVEL% equ 0 (
    echo   [OK] Desktop shortcut created: "%SHORTCUT_NAME%"
    echo        Target: %TARGET%
    echo        WorkDir: %SHOGUN_DIR%
    if defined ICON echo        Icon: %ICON%
) else (
    echo   [!] Could not create desktop shortcut. You can run start.bat manually.
)
