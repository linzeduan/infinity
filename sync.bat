@echo off
cd /d "d:\Abandon\infinity"

echo [1/3] Saving local changes...
git add .
git commit -m "sync: %COMPUTERNAME% [%date% %time%]" || echo Nothing to commit, skipping

echo [2/3] Pulling from remote...
git pull --rebase origin main
if %errorlevel% neq 0 (
    echo Pull failed - possible conflicts. Resolve manually and retry.
    pause
    exit /b
)

echo [3/3] Pushing to remote...
git push origin main
if %errorlevel% neq 0 (
    echo Push failed.
    pause
    exit /b
)

echo Sync completed: %time%
pause
