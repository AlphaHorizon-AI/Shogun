@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title Shogun - Uninstaller

echo.
echo  ======================================================
echo   SHOGUN AI Framework - Uninstaller
echo  ======================================================
echo.
echo   This will completely remove Shogun, including:
echo    - All virtual environments
echo    - Database files, memories, and keys
echo    - Desktop shortcuts
echo    - The entirety of this folder
echo.
echo   [!] WARNING: Please ensure that Shogun is NOT running
echo       before proceeding. Close any other black terminal
echo       windows that might be running the server!
echo.

set /p CONFIRM="  Are you absolutely sure? (Type Y to confirm, any other key to cancel): "
if /i "%CONFIRM%" neq "Y" (
    echo   Uninstall cancelled.
    pause
    exit /b 0
)

echo.
echo   [+] Removing Desktop shortcut...
if exist "%USERPROFILE%\Desktop\Shogun - The Tenshu.lnk" (
    del "%USERPROFILE%\Desktop\Shogun - The Tenshu.lnk" >nul 2>&1
    echo       Shortcut removed.
)

echo   [+] Scheduling folder deletion...
set "SELF_DIR=%~dp0"
:: Remove trailing backslash for cleaner output
if "%SELF_DIR:~-1%"=="\" set "SELF_DIR=%SELF_DIR:~0,-1%"

set "TEMP_UNINSTALL=%TEMP%\shogun_uninstall.bat"

:: Create the temporary script to delete this folder
echo @echo off > "%TEMP_UNINSTALL%"
echo echo. >> "%TEMP_UNINSTALL%"
echo echo  [+] Waiting for Shogun Uninstaller to close... >> "%TEMP_UNINSTALL%"
echo timeout /t 2 /nobreak ^>nul >> "%TEMP_UNINSTALL%"
echo echo  [+] Deleting "%SELF_DIR%"... >> "%TEMP_UNINSTALL%"
echo rmdir /s /q "%SELF_DIR%" >> "%TEMP_UNINSTALL%"
echo echo  [OK] Shogun has been completely uninstalled. >> "%TEMP_UNINSTALL%"
echo echo. >> "%TEMP_UNINSTALL%"
echo echo  You may now close this window. >> "%TEMP_UNINSTALL%"
echo pause >> "%TEMP_UNINSTALL%"
echo del "%%~f0" >> "%TEMP_UNINSTALL%"

echo   [OK] Ready. This window will now close and the deletion will finish in the background.
timeout /t 3 /nobreak >nul

:: Launch the temp script in a new window so the user sees the final output, and exit this one to release the lock
start "" cmd /c "%TEMP_UNINSTALL%"
exit
