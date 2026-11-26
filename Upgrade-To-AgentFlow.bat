@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions
title Shogun - Upgrade Yellow Label to Bare-Bones AgentFlow

set "SOURCE_DIR=%~dp0"
if "%SOURCE_DIR:~-1%"=="\" set "SOURCE_DIR=%SOURCE_DIR:~0,-1%"

set "TARGET_DIR=%~1"
if "%TARGET_DIR%"=="" (
    echo.
    echo  SHOGUN YELLOW LABEL -^> BARE-BONES AGENTFLOW UPGRADE
    echo  ----------------------------------------------------
    echo  Preserves data/shogun.db ^(AgentFlows, profiles, providers^),
    echo  data/workspace/ ^(all folders and files^), configs/, vault/, and .env.
    echo.
    set /p "TARGET_DIR=Enter path to existing Yellow Label folder (e.g. %USERPROFILE%\Shogun): "
)

if "%TARGET_DIR%"=="" (
    echo  Cancelled.
    exit /b 1
)

set "PY=%SOURCE_DIR%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo  Stop the target Shogun instance before upgrading!
echo  Target: %TARGET_DIR%
echo.
"%PY%" "%SOURCE_DIR%\scripts\upgrade_yellow_label.py" --target "%TARGET_DIR%"
if errorlevel 1 (
    echo.
    echo  Upgrade failed. Existing user data was not touched.
    pause
    exit /b 1
)
echo.
pause
