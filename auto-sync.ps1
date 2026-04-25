# 自动同步脚本 - PowerShell版本
# 保存位置：d:\Abandon\无限进步\auto-sync.ps1

$projectPath = "d:\Abandon\无限进步"
$logPath = "$projectPath\sync-log.txt"

Set-Location $projectPath

# 记录日志
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logPath -Value "[$timestamp] 开始同步..."

try {
    # 拉取
    git pull origin main 2>&1 | Tee-Object -FilePath $logPath -Append

    # 提交
    git add .
    git commit -m "sync: 自动同步 [$timestamp]" 2>&1 | Tee-Object -FilePath $logPath -Append

    # 推送
    git push origin main 2>&1 | Tee-Object -FilePath $logPath -Append

    Add-Content -Path $logPath -Value "[$timestamp] 同步成功!"
} catch {
    Add-Content -Path $logPath -Value "[$timestamp] 错误: $_"
}
