from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    extension TEXT NOT NULL,
    document_kind TEXT NOT NULL,
    source TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    mtime_ns INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    extraction_status TEXT NOT NULL,
    cloud_allowed INTEGER NOT NULL DEFAULT 1,
    restriction_reason TEXT,
    modified_at TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    heading TEXT,
    page INTEGER,
    line_start INTEGER,
    line_end INTEGER,
    text TEXT NOT NULL,
    cloud_allowed INTEGER NOT NULL DEFAULT 1,
    UNIQUE(document_id, ordinal)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    chunk_id UNINDEXED,
    text,
    heading,
    path,
    source,
    terms,
    tokenize='unicode61 remove_diacritics 2'
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_kind ON documents(document_kind);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ready(self) -> bool:
        if not self.path.exists():
            return False
        try:
            with self.connect() as connection:
                connection.execute("SELECT 1 FROM documents LIMIT 1")
            return True
        except sqlite3.Error:
            return False
