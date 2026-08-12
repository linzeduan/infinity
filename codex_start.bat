@echo off
setlocal
cd /d "%~dp0"
where codex >nul 2>nul
if errorlevel 1 (
    echo Codex CLI was not found on PATH. Open this folder in the Codex desktop app instead.
    pause
    exit /b 1
)
codex
