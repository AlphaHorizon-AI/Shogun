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

:: Create shortcut via PowerShell with fully resolved absolute paths
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; "^
  "$sc = $ws.CreateShortcut('%DESKTOP%\%SHORTCUT_NAME%.lnk'); "^
  "$sc.TargetPath = '%TARGET%'; "^
  "$sc.WorkingDirectory = '%SHOGUN_DIR%'; "^
  "$sc.Description = 'Launch the Shogun AI Agent Framework'; "^
  "$sc.WindowStyle = 1; "^
  "$sc.Save()"

if %ERRORLEVEL% equ 0 (
    echo   [OK] Desktop shortcut created: "%SHORTCUT_NAME%"
    echo        Target: %TARGET%
    echo        WorkDir: %SHOGUN_DIR%
) else (
    echo   [!] Could not create desktop shortcut. You can run start.bat manually.
)
