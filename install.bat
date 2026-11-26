@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  python -m venv .venv || exit /b 1
)
call ".venv\Scripts\activate.bat"
pip install -e . || exit /b 1
pushd frontend
call npm install || exit /b 1
call npm run build || exit /b 1
popd
echo.
echo Install complete. Run start.bat or "python -m shogun" to launch Shogun AgentFlow.
