@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\validate_repository.ps1"
set "VALIDATE_EXIT=%ERRORLEVEL%"
exit /b %VALIDATE_EXIT%
