@echo off
cd /d "d:\Abandon\无限进步"

echo.
echo [1/3] Pulling remote updates...
git pull origin main

echo.
echo [2/3] Committing local changes...
git add .
git commit -m "sync: auto sync [%date%]" || echo No changes to commit

echo.
echo [3/3] Pushing to Github...
git push origin main

echo.
echo Sync completed at %time%
echo.
pause
