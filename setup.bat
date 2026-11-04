@echo off
cd /d "%~dp0"
if exist "%~dp0.tools\node-v22.22.3\node.exe" set "PATH=%~dp0.tools\node-v22.22.3;%PATH%"
where python >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.11 or newer and add it to PATH first.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 22.22.3 or newer first. Then reopen this window.
  pause
  exit /b 1
)
python -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto failed
pushd frontend
call npm ci --no-audit --no-fund
if errorlevel 1 (
  popd
  goto failed
)
call npm run build
if errorlevel 1 (
  popd
  goto failed
)
popd
.venv\Scripts\python.exe manage.py setup_stockroom
if errorlevel 1 goto failed
echo Setup complete. Run start.bat to open Stockroom.
pause
exit /b 0
:failed
echo Setup failed. Read the error above and the README.md guide.
pause
exit /b 1
