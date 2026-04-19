:: ===============================================================
::  Creates a "Shogun" desktop shortcut pointing to start.bat
::  Called automatically at the end of install.bat
:: ===============================================================
@echo off
setlocal

:: Calculate the Shogun root directory (one level up from this script's location)
set "SHOGUN_DIR=%~dp0.."
set "SHORTCUT_NAME=Shogun - The Tenshu"
set "DESKTOP=%USERPROFILE%\Desktop"
set "TARGET=%SHOGUN_DIR%\start.bat"
set "ICON=%SHOGUN_DIR%\frontend\public\shogun-logo.ico"

:: Create shortcut via PowerShell (flattened command to avoid parser crashes)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%DESKTOP%\%SHORTCUT_NAME%.lnk'); $sc.TargetPath = '%TARGET%'; $sc.WorkingDirectory = '%SHOGUN_DIR%'; $sc.Description = 'Launch the Shogun AI Agent Framework'; $sc.WindowStyle = 1; $sc.Save()"

if %ERRORLEVEL% equ 0 (
    echo   [OK] Desktop shortcut created: "%SHORTCUT_NAME%"
) else (
    echo   [!] Could not create desktop shortcut. You can run start.bat manually.
)
