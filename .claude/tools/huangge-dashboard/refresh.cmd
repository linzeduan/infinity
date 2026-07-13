@echo off
rem HuangGe dashboard daily refresh: fetch FRED data, rebuild HTML, open in browser
cd /d "D:\Abandon\infinity\.claude\tools\huangge-dashboard"
set PYTHONIOENCODING=utf-8
echo ==== %date% %time% ==== >> refresh.log
"C:\Users\29443\AppData\Local\Programs\Python\Python312\python.exe" generate.py >> refresh.log 2>&1
start "" "D:\Abandon\infinity\.claude\tools\huangge-dashboard\dashboard.html"
