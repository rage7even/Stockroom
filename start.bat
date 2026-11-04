@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist frontend\dist\stockroom\browser\index.html (
  echo Frontend build is missing. Run setup.bat first.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8000 in your browser.
echo Keep this window open. Stop the server with Ctrl+C.
.venv\Scripts\python.exe manage.py run_stockroom 127.0.0.1:8000 --noreload
pause
