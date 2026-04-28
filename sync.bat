@echo off
cd /d "d:\Abandon\infinity"

echo [1/3] 拉取云端最新进度...
git pull origin main
if %errorlevel% neq 0 (
    echo ❌ 拉取失败，请检查网络或冲突！
    pause
    exit /b
)

echo [2/3] 保存本地改动...
git add --force .
git commit -m "sync: %COMPUTERNAME% [%date% %time%]" || echo 无新改动，跳过提交

echo [3/3] 推送到云端...
git push origin main
if %errorlevel% neq 0 (
    echo ❌ 推送失败！
    pause
    exit /b
)

echo ✅ 同步完成 %time%
pause