# Infinity Research Cockpit

## 一键启动

在仓库根目录双击 `启动研究驾驶舱.cmd`。首次运行会自动安装 Python/Node 依赖并构建前端，之后会直接启动本地服务并打开浏览器；关闭命令窗口或按 `Ctrl+C` 即可停止。

Infinity 的本地只读研究驾驶舱。它直接读取当前 Obsidian Vault，把 Markdown、可提取文本的 PDF 和 DOCX 建成本地索引；`原始资料/` 与 `知识库/` 始终是唯一事实源。

## 能做什么

- 今日驾驶舱：资料对账、导航警告、预测到期、信源模型节奏、Git 状态。
- 本地全文检索：SQLite FTS5 + 中文二元词加权，搜索过程不上云。
- 只读智能体：DeepSeek 只接收最多 8 个允许上云的命中片段；回答附文件、标题、行号或 PDF 页码。
- 预测账本：筛选待验证、命中、部分命中和落空记录。
- 黄哥宏观看板：读取现有派生页面，只有用户主动操作才刷新。

受限材料、图片、扫描件与提取存疑 PDF 可以出现在本地检索结果中，但不会发送给 DeepSeek。

## 首次安装

在 PowerShell 中运行：

```powershell
cd tools/research-cockpit
powershell -NoProfile -ExecutionPolicy Bypass -File setup.ps1
```

如需智能体回答，复制配置模板并填写 Key：

```powershell
Copy-Item .env.example .env.local
notepad .env.local
```

`.env.local` 已被仓库根目录的 `.gitignore` 忽略。Key 只在 Python 服务端读取，不会注入浏览器构建产物。

## 启动

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1
```

浏览器打开 <http://127.0.0.1:8765>。服务端拒绝监听非 localhost 地址。

## 开发

后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
```

前端：

```powershell
cd frontend
npm run dev
```

Vite 会把 `/api` 代理到 `127.0.0.1:8765`。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
cd frontend
npm run build
npm run test:e2e
```

## 数据边界

- Vault：只读，不存在更新笔记、账本、Git 或执行任意 shell 的 API。
- 本地派生数据：`../../.cache/research-cockpit/cockpit.sqlite3`。
- DeepSeek：仅发送问题、脱敏检索标题和允许上云的证据片段；不记录请求正文。
- Codex：MVP 不直接调用。智能体页面可以复制带编号的证据包，手动交给 Codex 使用。
