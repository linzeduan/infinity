from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    id: str
    document_id: int
    path: str
    title: str
    heading: str | None = None
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    snippet: str
    extraction_status: str
    cloud_allowed: bool


class SearchResult(Citation):
    source: str
    document_kind: str
    score: float
    modified_at: str
    restriction_reason: str | None = None


class ChatRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    mode: Literal["qa", "compare", "audit"] = "qa"
    source: str | None = None
    document_kind: str | None = None


class RefreshResult(BaseModel):
    scanned: int
    inserted: int
    updated: int
    unchanged: int
    removed: int
    chunks: int
    errors: list[str]


class HealthResponse(BaseModel):
    status: str
    vault_root: str
    database_ready: bool
    frontend_ready: bool
    deepseek_configured: bool
    read_only_vault: bool = True
