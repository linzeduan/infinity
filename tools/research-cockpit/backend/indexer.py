from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .database import Database
from .models import RefreshResult
from .parsers import ParsedDocument, parse_document


SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def chinese_bigrams(text: str) -> str:
    terms: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        terms.extend(run[index : index + 2] for index in range(max(0, len(run) - 1)))
    terms.extend(re.findall(r"[A-Za-z0-9_./+-]{2,}", text.lower()))
    return " ".join(terms[:4000])


class VaultIndexer:
    def __init__(self, database: Database, settings: Settings):
        self.database = database
        self.settings = settings

    def scan_paths(self) -> list[Path]:
        paths: list[Path] = []
        for root in (self.settings.knowledge_root, self.settings.source_root):
            if not root.exists():
                continue
            paths.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and path.name != ".gitkeep"
                and path.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        return sorted(paths, key=lambda item: item.as_posix().lower())

    def _metadata(self, path: Path, parsed: ParsedDocument) -> dict[str, str]:
        relative = path.relative_to(self.settings.vault_root).as_posix()
        parts = Path(relative).parts
        document_kind = "knowledge" if parts[0] == "知识库" else "source"
        if document_kind == "knowledge":
            source = parts[1] if len(parts) > 2 else "知识库"
        else:
            source = parts[2] if len(parts) > 3 and parts[1] == "博客" else (parts[1] if len(parts) > 2 else "原始资料")
        return {"path": relative, "document_kind": document_kind, "source": source}

    def refresh(self) -> RefreshResult:
        self.database.initialize()
        paths = self.scan_paths()
        seen: set[str] = set()
        inserted = updated = unchanged = removed = chunk_count = 0
        errors: list[str] = []

        with self.database.connect() as connection:
            existing = {
                row["path"]: row
                for row in connection.execute("SELECT id, path, sha256, mtime_ns, size_bytes FROM documents")
            }

            for path in paths:
                relative = path.relative_to(self.settings.vault_root).as_posix()
                seen.add(relative)
                stat = path.stat()
                current = existing.get(relative)
                if current and current["mtime_ns"] == stat.st_mtime_ns and current["size_bytes"] == stat.st_size:
                    unchanged += 1
                    continue
                digest = sha256_file(path)
                if current and current["sha256"] == digest:
                    connection.execute(
                        "UPDATE documents SET mtime_ns=?, size_bytes=?, modified_at=? WHERE id=?",
                        (stat.st_mtime_ns, stat.st_size, datetime.fromtimestamp(stat.st_mtime).isoformat(), current["id"]),
                    )
                    unchanged += 1
                    continue
                try:
                    parsed = parse_document(path)
                except Exception as exc:
                    errors.append(f"{relative}: {type(exc).__name__}: {exc}")
                    parsed = ParsedDocument(path.stem, [], "error", False, f"提取失败：{type(exc).__name__}")

                metadata = self._metadata(path, parsed)
                now = datetime.now(timezone.utc).isoformat()
                values = (
                    parsed.title,
                    path.suffix.lower(),
                    metadata["document_kind"],
                    metadata["source"],
                    digest,
                    stat.st_mtime_ns,
                    stat.st_size,
                    parsed.extraction_status,
                    int(parsed.cloud_allowed),
                    parsed.restriction_reason,
                    datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    now,
                )
                if current:
                    document_id = current["id"]
                    connection.execute(
                        """UPDATE documents SET title=?, extension=?, document_kind=?, source=?, sha256=?,
                           mtime_ns=?, size_bytes=?, extraction_status=?, cloud_allowed=?, restriction_reason=?,
                           modified_at=?, indexed_at=? WHERE id=?""",
                        values + (document_id,),
                    )
                    old_chunk_ids = [
                        row["id"]
                        for row in connection.execute("SELECT id FROM chunks WHERE document_id=?", (document_id,))
                    ]
                    if old_chunk_ids:
                        placeholders = ",".join("?" for _ in old_chunk_ids)
                        connection.execute(f"DELETE FROM chunk_fts WHERE chunk_id IN ({placeholders})", old_chunk_ids)
                    connection.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
                    updated += 1
                else:
                    cursor = connection.execute(
                        """INSERT INTO documents(path, title, extension, document_kind, source, sha256,
                           mtime_ns, size_bytes, extraction_status, cloud_allowed, restriction_reason,
                           modified_at, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (relative,) + values,
                    )
                    document_id = int(cursor.lastrowid)
                    inserted += 1

                for chunk in parsed.chunks:
                    cursor = connection.execute(
                        """INSERT INTO chunks(document_id, ordinal, heading, page, line_start, line_end, text, cloud_allowed)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            document_id,
                            chunk.ordinal,
                            chunk.heading,
                            chunk.page,
                            chunk.line_start,
                            chunk.line_end,
                            chunk.text,
                            int(parsed.cloud_allowed),
                        ),
                    )
                    chunk_id = int(cursor.lastrowid)
                    connection.execute(
                        "INSERT INTO chunk_fts(chunk_id, text, heading, path, source, terms) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            chunk_id,
                            chunk.text,
                            chunk.heading or "",
                            relative,
                            metadata["source"],
                            chinese_bigrams(" ".join((chunk.text, chunk.heading or "", metadata["source"]))),
                        ),
                    )
                    chunk_count += 1

            stale = [row for path, row in existing.items() if path not in seen]
            for row in stale:
                chunk_ids = [item["id"] for item in connection.execute("SELECT id FROM chunks WHERE document_id=?", (row["id"],))]
                if chunk_ids:
                    placeholders = ",".join("?" for _ in chunk_ids)
                    connection.execute(f"DELETE FROM chunk_fts WHERE chunk_id IN ({placeholders})", chunk_ids)
                connection.execute("DELETE FROM documents WHERE id=?", (row["id"],))
                removed += 1

        return RefreshResult(
            scanned=len(paths),
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
            removed=removed,
            chunks=chunk_count,
            errors=errors,
        )
