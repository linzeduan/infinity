@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    pause
    exit /b 1
)

echo ==== %date% %time% ==== >> "%~dp0refresh.log"
python "%~dp0generate.py" >> "%~dp0refresh.log" 2>&1
if errorlevel 1 (
    echo Dashboard refresh failed. See refresh.log.
    pause
    exit /b 1
)

start "" "%~dp0dashboard.html"
exit /b 0
