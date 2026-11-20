@echo off
setlocal
cd /d "%~dp0"
set "VENV_PYTHON=.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" set "VENV_PYTHON=.venv\bin\python.exe"
if exist ".venv-windows\Scripts\python.exe" set "VENV_PYTHON=.venv-windows\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
 echo Run setup.bat first.
 pause
 exit /b 1
)
"%VENV_PYTHON%" backend\manage.py migrate --check
if errorlevel 1 (
 echo Run setup.bat to update the database before starting Stockroom.
 pause
 exit /b 1
)
echo Open http://127.0.0.1:8000 and keep this window open.
"%VENV_PYTHON%" backend\manage.py run_stockroom 127.0.0.1:8000 --noreload
pause
