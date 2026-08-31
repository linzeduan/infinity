@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem 从稳定快照执行同步。rebase 可能更新 sync.bat 本身；若直接运行原文件，
rem cmd.exe 会从旧字节偏移继续读取新文件，并可能把提示文字的残片当成命令。
if not defined INFINITY_SYNC_SNAPSHOT_ROOT set "INFINITY_SYNC_SNAPSHOT_ROOT=%~dp0"
if not defined INFINITY_SYNC_SNAPSHOT_FILE set "INFINITY_SYNC_SNAPSHOT_FILE=%TEMP%\infinity-sync-%RANDOM%-%RANDOM%.bat"
if not defined INFINITY_SYNC_SNAPSHOT (
    copy /y "%~f0" "%INFINITY_SYNC_SNAPSHOT_FILE%" >nul
    if errorlevel 1 (
        echo [错误] 无法创建同步脚本的临时快照。
        exit /b 1
    )
    set "INFINITY_SYNC_SNAPSHOT=1"
    call "%INFINITY_SYNC_SNAPSHOT_FILE%" %*
    if errorlevel 1 (
        del /q "%INFINITY_SYNC_SNAPSHOT_FILE%" >nul 2>&1
        exit /b 1
    )
    del /q "%INFINITY_SYNC_SNAPSHOT_FILE%" >nul 2>&1
    exit /b 0
)

chcp 65001 >nul
cd /d "%INFINITY_SYNC_SNAPSHOT_ROOT%"

set "REMOTE=origin"
set "BRANCH=main"
set "NO_PAUSE="
if /i "%~1"=="--no-pause" set "NO_PAUSE=1"
set "GIT_TERMINAL_PROMPT=0"
set "GIT_HTTP_LOW_SPEED_LIMIT=1024"
set "GIT_HTTP_LOW_SPEED_TIME=30"

echo ============================================================
echo   Infinity Git 同步
echo ============================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Git，请先安装 Git 或检查 PATH。
    goto failed
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [错误] 当前目录不是 Git 仓库：%CD%
    goto failed
)

for /f "delims=" %%B in ('git branch --show-current') do set "CURRENT_BRANCH=%%B"
if not defined CURRENT_BRANCH (
    echo [错误] 当前处于 detached HEAD，无法安全同步。
    goto failed
)
if /i not "%CURRENT_BRANCH%"=="%BRANCH%" (
    echo [错误] 当前分支是 %CURRENT_BRANCH%，本脚本只同步 %BRANCH%。
    goto failed
)

git remote get-url "%REMOTE%" >nul 2>&1
if errorlevel 1 (
    echo [错误] 未配置远端 %REMOTE%。
    goto failed
)

set "HTTP_PROXY_CONFIGURED="
for /f "delims=" %%P in ('git config --get http.proxy 2^>nul') do set "HTTP_PROXY_CONFIGURED=1"

for /f "delims=" %%P in ('git rev-parse --git-path index.lock') do set "INDEX_LOCK=%%P"
if exist "%INDEX_LOCK%" (
    echo [错误] 检测到 Git 锁文件：%INDEX_LOCK%
    echo 请先确认没有其他 Git 程序正在运行；确认后再删除残留锁文件。
    goto failed
)

for /f "delims=" %%P in ('git rev-parse --git-path MERGE_HEAD') do set "MERGE_HEAD=%%P"
for /f "delims=" %%P in ('git rev-parse --git-path CHERRY_PICK_HEAD') do set "CHERRY_PICK_HEAD=%%P"
for /f "delims=" %%P in ('git rev-parse --git-path rebase-merge') do set "REBASE_MERGE=%%P"
for /f "delims=" %%P in ('git rev-parse --git-path rebase-apply') do set "REBASE_APPLY=%%P"
if exist "%MERGE_HEAD%" goto operation_in_progress
if exist "%CHERRY_PICK_HEAD%" goto operation_in_progress
if exist "%REBASE_MERGE%" goto operation_in_progress
if exist "%REBASE_APPLY%" goto operation_in_progress

echo [1/6] 校验知识库...
call "%INFINITY_SYNC_SNAPSHOT_ROOT%validate.bat"
if errorlevel 1 (
    echo [错误] 仓库校验未通过，未执行提交、拉取或推送。
    goto failed
)

echo.
echo [2/6] 检查本地变更...
git update-index -q --refresh
set "HAS_CHANGES="
for /f "delims=" %%S in ('git status --porcelain') do set "HAS_CHANGES=1"

if not defined HAS_CHANGES goto no_local_changes

echo 检测到以下本地变更：
git status --short
echo.
echo 正在清理微信读书导出产生的非法尾随空白...
powershell -NoProfile -ExecutionPolicy Bypass -File "%INFINITY_SYNC_SNAPSHOT_ROOT%scripts\normalize_weread_whitespace.ps1"
if errorlevel 1 (
    echo [错误] 微信读书导出空白清理失败。
    goto failed
)
echo.
echo 正在自动暂存以上全部变更并继续同步...

git add -A -- .
if errorlevel 1 (
    echo [错误] 暂存本地变更失败。
    goto failed
)

git diff --cached --quiet
if not errorlevel 1 goto no_local_changes

powershell -NoProfile -ExecutionPolicy Bypass -File "%INFINITY_SYNC_SNAPSHOT_ROOT%scripts\check_whitespace.ps1" -Mode Staged
if errorlevel 1 goto staged_whitespace_failed

echo.
echo [3/6] 提交本地变更...
git diff --cached --stat
echo.
git commit -m "sync: %COMPUTERNAME% [%date% %time%]"
if errorlevel 1 (
    echo [错误] 提交失败。变更仍保留在暂存区，没有拉取或推送。
    goto failed
)
goto fetch_remote

:no_local_changes
echo 没有需要提交的本地变更。

:fetch_remote
echo.
echo [4/6] 获取远端更新（最长等待 120 秒）...
call :fetch_with_timeout
set "FETCH_EXIT=%ERRORLEVEL%"
if "%FETCH_EXIT%"=="0" goto fetch_succeeded
if defined HTTP_PROXY_CONFIGURED goto retry_fetch_without_proxy
goto fetch_failed

:retry_fetch_without_proxy
echo 当前 Git 代理连接失败，自动改用直连重试一次...
call :fetch_direct_with_timeout
set "FETCH_EXIT=%ERRORLEVEL%"
if "%FETCH_EXIT%"=="0" (
    set "BYPASS_PROXY=1"
    goto fetch_succeeded
)

:fetch_failed
if "%FETCH_EXIT%"=="124" echo [错误] 获取远端超过 120 秒，已自动终止，避免脚本一直卡住。
echo [错误] 获取远端失败。本地内容未丢失，也没有执行推送。
echo 请检查网络、代理和 GitHub 登录状态后重试。
goto failed

:fetch_succeeded
echo.
echo [5/6] 整合远端更新...
git rebase "%REMOTE%/%BRANCH%"
if errorlevel 1 (
    echo 检测到冲突，正在自动撤销本次 rebase...
    git rebase --abort
    echo [错误] 本地与远端存在冲突。已尽量恢复到同步前的本地提交状态。
    echo 请手动处理冲突后重试。
    goto failed
)

call "%INFINITY_SYNC_SNAPSHOT_ROOT%validate.bat"
if errorlevel 1 (
    echo [错误] 整合远端更新后校验未通过，因此没有推送。
    goto failed
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%INFINITY_SYNC_SNAPSHOT_ROOT%scripts\check_whitespace.ps1" -Mode Range -Range "%REMOTE%/%BRANCH%..HEAD"
if errorlevel 1 goto outgoing_whitespace_failed

echo.
echo [6/6] 推送本地提交...
for /f "delims=" %%N in ('git rev-list --count "%REMOTE%/%BRANCH%"..HEAD') do set "AHEAD_COUNT=%%N"
if "%AHEAD_COUNT%"=="0" (
    echo 本地与远端已经一致，无需推送。
    goto success
)

if defined BYPASS_PROXY (
    call :push_direct_with_timeout
) else (
    call :push_with_timeout
)
set "PUSH_EXIT=%ERRORLEVEL%"
if "%PUSH_EXIT%"=="124" (
    echo [错误] 推送超过 120 秒，已自动终止。请先检查远端状态，再重新运行。
    goto failed
)
if not "%PUSH_EXIT%"=="0" (
    echo [错误] 推送失败，但本地提交均已保留。
    echo 远端若刚好被其他设备更新，请直接重新运行本脚本。
    goto failed
)

:success
echo.
echo [同步状态] 同步成功
git status --short --branch
call :pause_if_needed
exit /b 0

:operation_in_progress
echo [错误] 仓库中存在尚未完成的 merge、rebase 或 cherry-pick。
echo 请先完成或中止该操作，再运行同步脚本。
goto failed

:staged_whitespace_failed
echo [错误] 暂存内容存在非法空白字符，尚未创建提交。
echo [提示] 微信读书导出已在暂存前自动清理；若仍失败，请根据上方文件和行号处理其他来源的空白问题。
goto failed

:outgoing_whitespace_failed
echo [错误] 待推送内容存在空白字符错误，因此没有推送。
goto failed

:failed
echo.
echo [同步状态] 同步失败
git status --short --branch 2>nul
call :pause_if_needed
exit /b 1

:pause_if_needed
if defined NO_PAUSE exit /b 0
echo.
echo 按任意键关闭窗口；命令行调用可加 --no-pause 跳过等待。
pause >nul
exit /b 0

:fetch_with_timeout
powershell -NoProfile -Command "$p = Start-Process -FilePath 'git.exe' -ArgumentList @('-c','http.lowSpeedLimit=1024','-c','http.lowSpeedTime=30','fetch','--prune','--no-tags','%REMOTE%','+refs/heads/%BRANCH%:refs/remotes/%REMOTE%/%BRANCH%') -NoNewWindow -PassThru; if (-not $p.WaitForExit(120000)) { taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null; exit 124 }; exit $p.ExitCode"
exit /b %ERRORLEVEL%

:fetch_direct_with_timeout
powershell -NoProfile -Command "$p = Start-Process -FilePath 'git.exe' -ArgumentList @('-c','http.proxy=','-c','http.lowSpeedLimit=1024','-c','http.lowSpeedTime=30','fetch','--prune','--no-tags','%REMOTE%','+refs/heads/%BRANCH%:refs/remotes/%REMOTE%/%BRANCH%') -NoNewWindow -PassThru; if (-not $p.WaitForExit(120000)) { taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null; exit 124 }; exit $p.ExitCode"
exit /b %ERRORLEVEL%

:push_with_timeout
powershell -NoProfile -Command "$p = Start-Process -FilePath 'git.exe' -ArgumentList @('-c','http.version=HTTP/1.1','-c','http.postBuffer=10485760','-c','http.maxRequests=1','push','%REMOTE%','HEAD:%BRANCH%') -NoNewWindow -PassThru; if (-not $p.WaitForExit(120000)) { taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null; exit 124 }; exit $p.ExitCode"
exit /b %ERRORLEVEL%

:push_direct_with_timeout
powershell -NoProfile -Command "$p = Start-Process -FilePath 'git.exe' -ArgumentList @('-c','http.proxy=','-c','https.proxy=','-c','http.version=HTTP/1.1','-c','http.postBuffer=10485760','-c','http.maxRequests=1','push','%REMOTE%','HEAD:%BRANCH%') -NoNewWindow -PassThru; if (-not $p.WaitForExit(120000)) { taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null; exit 124 }; exit $p.ExitCode"
exit /b %ERRORLEVEL%
