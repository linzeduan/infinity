from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from .database import Database
from .indexer import chinese_bigrams


def _search_tokens(query: str) -> list[str]:
    terms = chinese_bigrams(query).split()
    terms.extend(re.findall(r"[A-Za-z0-9_./+-]{2,}", query.lower()))
    unique: list[str] = []
    for term in terms:
        if term not in unique:
            unique.append(term)
    return unique[:24]


def _snippet(text: str, query: str, limit: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    needles = [token for token in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", query) if token]
    positions = [compact.lower().find(token.lower()) for token in needles]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - limit // 3)
    end = min(len(compact), start + limit)
    return ("…" if start else "") + compact[start:end] + ("…" if end < len(compact) else "")


class SearchService:
    def __init__(self, database: Database):
        self.database = database

    def search(
        self,
        query: str,
        limit: int = 20,
        source: str | None = None,
        document_kind: str | None = None,
    ) -> list[dict]:
        tokens = _search_tokens(query)
        rows = []
        if tokens:
            expression = " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
            conditions = ["chunk_fts MATCH ?"]
            params: list[object] = [expression]
            if source:
                conditions.append("d.source = ?")
                params.append(source)
            if document_kind:
                conditions.append("d.document_kind = ?")
                params.append(document_kind)
            params.append(max(limit * 4, 40))
            sql = f"""
                SELECT c.id AS chunk_id, c.document_id, c.heading, c.page, c.line_start, c.line_end,
                       c.text, c.cloud_allowed, d.path, d.title, d.source, d.document_kind,
                       d.extraction_status, d.restriction_reason, d.modified_at,
                       bm25(chunk_fts, 0.0, 1.0, 3.2, 1.8, 1.6, 2.4) AS rank
                FROM chunk_fts
                JOIN chunks c ON c.id = CAST(chunk_fts.chunk_id AS INTEGER)
                JOIN documents d ON d.id = c.document_id
                WHERE {' AND '.join(conditions)}
                ORDER BY rank
                LIMIT ?
            """
            try:
                with self.database.connect() as connection:
                    rows = connection.execute(sql, params).fetchall()
            except Exception:
                rows = []

        if not rows:
            conditions = ["(c.text LIKE ? OR c.heading LIKE ? OR d.title LIKE ?)"]
            like = f"%{query[:100]}%"
            params = [like, like, like]
            if source:
                conditions.append("d.source = ?")
                params.append(source)
            if document_kind:
                conditions.append("d.document_kind = ?")
                params.append(document_kind)
            params.append(max(limit * 3, 30))
            with self.database.connect() as connection:
                rows = connection.execute(
                    f"""SELECT c.id AS chunk_id, c.document_id, c.heading, c.page, c.line_start, c.line_end,
                               c.text, c.cloud_allowed, d.path, d.title, d.source, d.document_kind,
                               d.extraction_status, d.restriction_reason, d.modified_at, 20.0 AS rank
                        FROM chunks c JOIN documents d ON d.id=c.document_id
                        WHERE {' AND '.join(conditions)} ORDER BY d.modified_at DESC LIMIT ?""",
                    params,
                ).fetchall()

        per_document: Counter[int] = Counter()
        results: list[dict] = []
        query_lower = query.lower()
        for row in rows:
            document_id = int(row["document_id"])
            if per_document[document_id] >= 2:
                continue
            per_document[document_id] += 1
            raw_rank = float(row["rank"])
            score = 100.0 / (1.0 + abs(raw_rank))
            if query_lower in (row["title"] or "").lower():
                score += 24
            if query_lower in (row["heading"] or "").lower():
                score += 16
            try:
                age_days = max(0, (datetime.now() - datetime.fromisoformat(row["modified_at"])).days)
                score += max(0, 6 - age_days / 30)
            except ValueError:
                pass
            results.append(
                {
                    "id": f"C{row['chunk_id']}",
                    "document_id": document_id,
                    "path": row["path"],
                    "title": row["title"],
                    "heading": row["heading"],
                    "page": row["page"],
                    "line_start": row["line_start"],
                    "line_end": row["line_end"],
                    "snippet": _snippet(row["text"], query),
                    "full_text": row["text"],
                    "extraction_status": row["extraction_status"],
                    "cloud_allowed": bool(row["cloud_allowed"]),
                    "source": row["source"],
                    "document_kind": row["document_kind"],
                    "score": round(score, 3),
                    "modified_at": row["modified_at"],
                    "restriction_reason": row["restriction_reason"],
                }
            )
            if len(results) >= limit:
                break
        return sorted(results, key=lambda item: item["score"], reverse=True)
