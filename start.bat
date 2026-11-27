@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions EnableDelayedExpansion
title Shogun AgentFlow
cd /d "%~dp0"

set "PYTHON_EXE="
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

set "SHOGUN_LAUNCHER_MANAGED=true"
:run_shogun
"%PYTHON_EXE%" -m shogun %*
set "SHOGUN_EXIT_CODE=!ERRORLEVEL!"

if exist ".states\restart-requested" (
    del /q ".states\restart-requested" >nul 2>&1
    timeout /t 2 /nobreak >nul
    goto run_shogun
)

if exist ".states\shutdown-requested" (
    del /q ".states\shutdown-requested" >nul 2>&1
    exit /b 0
)

exit /b !SHOGUN_EXIT_CODE!
