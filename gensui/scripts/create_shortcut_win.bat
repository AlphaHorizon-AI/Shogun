:: ===============================================================
::  Creates a "Gensui" desktop shortcut pointing to start.bat
::  Called automatically near the end of install.bat
:: ===============================================================
@echo off
setlocal

:: Resolve the Gensui directory to a full absolute path.
pushd "%~dp0.."
set "GENSUI_DIR=%CD%"
popd

set "GENSUI_SHORTCUT_NAME=Gensui - Agent Fleet Management"
set "GENSUI_TARGET=%GENSUI_DIR%\start.bat"
set "GENSUI_ICON=%GENSUI_DIR%\frontend\public\gensui-afm-desktop.ico"

:: GENSUI_DESKTOP_DIR is an optional override used by automated checks.
:: Otherwise, ask Windows for the user's real Desktop (including redirection).
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop = $env:GENSUI_DESKTOP_DIR; "^
  "if ([string]::IsNullOrWhiteSpace($desktop)) { $desktop = [Environment]::GetFolderPath('Desktop') }; "^
  "if ([string]::IsNullOrWhiteSpace($desktop)) { throw 'Windows could not resolve the Desktop folder.' }; "^
  "$ws = New-Object -ComObject WScript.Shell; "^
  "$sc = $ws.CreateShortcut((Join-Path $desktop ($env:GENSUI_SHORTCUT_NAME + '.lnk'))); "^
  "$sc.TargetPath = $env:GENSUI_TARGET; "^
  "$sc.WorkingDirectory = $env:GENSUI_DIR; "^
  "$sc.Description = 'Launch Gensui Agent Fleet Management'; "^
  "$sc.IconLocation = $env:GENSUI_ICON + ',0'; "^
  "$sc.WindowStyle = 1; "^
  "$sc.Save()"

if %ERRORLEVEL% equ 0 (
    echo        Desktop shortcut created: "%GENSUI_SHORTCUT_NAME%"
    echo        Icon: %GENSUI_ICON%
) else (
    echo        Warning: Could not create the Gensui desktop shortcut.
)

endlocal
