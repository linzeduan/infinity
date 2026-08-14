from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agent import AgentService
from .config import settings
from .database import Database
from .indexer import VaultIndexer
from .models import ChatRequest, HealthResponse, RefreshResult
from .providers import DeepSeekProvider
from .repository import VaultRepository
from .search import SearchService


settings.ensure_safe_host()
database = Database(settings.database_path)
database.initialize()
indexer = VaultIndexer(database, settings)
repository = VaultRepository(database, settings)
search_service = SearchService(database)
provider = DeepSeekProvider(settings)
agent_service = AgentService(search_service, provider)

app = FastAPI(
    title="Infinity Research Cockpit",
    version="0.1.0",
    description="面向 Obsidian Vault 的本地只读研究驾驶舱。",
)


@app.on_event("startup")
def startup_index() -> None:
    indexer.refresh()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        vault_root=str(settings.vault_root),
        database_ready=database.ready(),
        frontend_ready=(settings.frontend_dist / "index.html").exists(),
        deepseek_configured=provider.configured,
    )


@app.get("/api/dashboard")
def dashboard() -> dict:
    return repository.dashboard()


@app.post("/api/index/refresh", response_model=RefreshResult)
def refresh_index() -> RefreshResult:
    return indexer.refresh()


@app.get("/api/search")
def search(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=20, ge=1, le=50),
    source: str | None = None,
    document_kind: str | None = None,
) -> dict:
    items = search_service.search(q, limit=limit, source=source, document_kind=document_kind)
    for item in items:
        item.pop("full_text", None)
    return {"query": q, "count": len(items), "items": items}


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        agent_service.stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/predictions")
def predictions(status: str | None = None, source: str | None = None) -> dict:
    items = repository.predictions()
    if status:
        items = [item for item in items if item["status"] == status]
    if source:
        items = [item for item in items if item["source"] == source]
    return {"count": len(items), "items": items}


@app.get("/api/documents/{document_id}")
def document(document_id: int) -> dict:
    result = repository.document(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return result


def _resolved_document_path(document_id: int) -> Path:
    result = repository.document(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    path = (settings.vault_root / result["path"]).resolve()
    allowed_roots = (settings.knowledge_root.resolve(), settings.source_root.resolve())
    if not any(path.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="路径不在允许的只读根目录中")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="原文件不存在")
    return path


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: int) -> FileResponse:
    path = _resolved_document_path(document_id)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name, content_disposition_type="inline")


@app.post("/api/macro/refresh")
def refresh_macro() -> dict:
    return repository.refresh_macro()


@app.get("/api/macro/page")
def macro_page() -> FileResponse:
    path = settings.macro_root / "dashboard.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="宏观看板尚未生成")
    return FileResponse(path, media_type="text/html")


assets = settings.frontend_dist / "assets"
if assets.exists():
    app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.get("/{full_path:path}", response_class=HTMLResponse)
def spa(full_path: str):
    index = settings.frontend_dist / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<h1>Infinity Research Cockpit</h1><p>前端尚未构建。请在 frontend 目录运行 npm install && npm run build。</p>",
        status_code=503,
    )
