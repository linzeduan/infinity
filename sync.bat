@echo off
cd /d "d:\Abandon\infinity"

echo [1/3] Saving local changes...
git add --force .
git commit -m "sync: auto sync [%date% %time%]" || echo No changes to commit

echo [2/3] Pulling remote updates...
git pull origin main --rebase

echo [3/3] Pushing to Github...
git push origin main

echo Sync completed at %time%