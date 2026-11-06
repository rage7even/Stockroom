@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
if exist ".venv\bin\python.exe" goto install

py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
 py -3 -m venv .venv
) else (
 python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
 if errorlevel 1 goto no_python
 python -m venv .venv
)
if errorlevel 1 goto failed

:install
set "VENV_PYTHON=.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" set "VENV_PYTHON=.venv\bin\python.exe"
"%VENV_PYTHON%" -m pip install -r backend\requirements.txt
if errorlevel 1 goto failed
"%VENV_PYTHON%" backend\manage.py migrate
if errorlevel 1 goto failed
"%VENV_PYTHON%" backend\manage.py seed
if errorlevel 1 goto failed
echo Ready. Run start.bat, then open http://127.0.0.1:8000
pause
exit /b 0
:no_python
echo Python 3.11 or newer was not found via py or python.
pause
exit /b 1
:failed
echo Setup failed. Check Python installation and the error above.
pause
exit /b 1
