@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [1/5] Validating repository...
call "%~dp0validate.bat"
if errorlevel 1 goto failed

echo [2/5] Checking the working tree...
git update-index -q --refresh
git diff --quiet
if errorlevel 1 goto unstaged

for /f "delims=" %%F in ('git ls-files --others --exclude-standard') do goto untracked

git diff --cached --quiet
if not errorlevel 1 goto pull

echo [3/5] Reviewing and committing staged changes...
git diff --cached --stat
echo.
git commit -m "sync: FATE [%date% %time%]"
if errorlevel 1 (
    echo Commit failed. Nothing was pulled or pushed.
    goto failed
)

:pull
echo [4/5] Pulling committed changes from origin/main...
git pull --rebase origin main
if errorlevel 1 (
    echo Pull failed. Resolve the conflict manually, then retry.
    goto failed
)

echo [5/5] Pushing local commits to origin/main...
git push origin main
if errorlevel 1 (
    echo Push failed.
    goto failed
)

echo Sync completed.
echo.
echo [同步状态] 同步成功
pause
exit /b 0

:unstaged
echo Sync stopped: tracked files have unstaged changes.
echo Review and stage only the intended files, then retry.
git status --short
goto failed

:untracked
echo Sync stopped: untracked files are present.
echo Review, stage, delete, or ignore them explicitly, then retry.
git status --short
goto failed

:failed
echo.
echo [同步状态] 同步失败
pause
exit /b 1
