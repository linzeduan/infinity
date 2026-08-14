from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

from .config import Settings
from .database import Database
from .parsers import normalize_deadline, parse_table, prediction_status


SOURCE_PATH_RE = re.compile(r"原始资料/[^|`\r\n]+?\.(?:md|pdf|png|jpg|jpeg|docx)", re.I)


class VaultRepository:
    def __init__(self, database: Database, settings: Settings):
        self.database = database
        self.settings = settings

    def predictions(self) -> list[dict]:
        path = self.settings.knowledge_root / "预测追踪表.md"
        items: list[dict] = []
        if not path.exists():
            return items
        for cells in parse_table(path, 8):
            if not cells or not re.fullmatch(r"\d+", cells[0]):
                continue
            deadline, precision = normalize_deadline(cells[5])
            items.append(
                {
                    "number": int(cells[0]),
                    "recorded_at": cells[1],
                    "source": cells[2],
                    "claim": cells[3],
                    "verification": cells[4],
                    "deadline_raw": cells[5],
                    "deadline": deadline,
                    "deadline_precision": precision,
                    "result": cells[6],
                    "status": prediction_status(cells[6]),
                    "origin": cells[7],
                }
            )
        return items

    def processed_rows(self) -> list[dict]:
        path = self.settings.knowledge_root / "_processed.md"
        rows: list[dict] = []
        if not path.exists():
            return rows
        for position, cells in enumerate(parse_table(path, 7)):
            if not cells:
                continue
            rows.append(
                {
                    "id": cells[0],
                    "source_path": cells[1],
                    "processed_at": cells[2],
                    "mode": cells[3],
                    "output": cells[4],
                    "words": cells[5],
                    "status": cells[6],
                    "position": position,
                }
            )
        return rows

    def _ledger_source_paths(self, rows: list[dict]) -> set[str]:
        paths: set[str] = set()
        for row in rows:
            if "已删除" in row["status"]:
                continue
            for match in SOURCE_PATH_RE.findall(row["source_path"]):
                paths.add(match.replace("\\", "/").strip())
        return paths

    def _actual_source_paths(self) -> set[str]:
        return {
            path.relative_to(self.settings.vault_root).as_posix()
            for path in self.settings.source_root.rglob("*")
            if path.is_file() and path.name != ".gitkeep"
        }

    def _navigation_warnings(self) -> list[str]:
        index_path = self.settings.knowledge_root / "目录.md"
        if not index_path.exists():
            return ["知识库/目录.md 不存在"]
        text = index_path.read_text(encoding="utf-8-sig", errors="replace")
        links: set[str] = set()
        for target in re.findall(r"\]\(([^)#?]+\.md)(?:#[^)]*)?\)", text):
            links.add(unquote(target).replace("\\", "/").lstrip("./"))
        warnings: list[str] = []
        for path in self.settings.knowledge_root.rglob("*.md"):
            relative = path.relative_to(self.settings.knowledge_root).as_posix()
            if relative in {"_processed.md", "目录.md"}:
                continue
            if relative not in links and path.name not in {Path(link).name for link in links}:
                warnings.append(f"目录未覆盖：知识库/{relative}")
        return warnings

    def _model_states(self, rows: list[dict]) -> list[dict]:
        configs = {
            "黄哥": {"first": 10, "refresh": 10},
            "孟岩": {"first": 3, "refresh": 5},
        }
        states: list[dict] = []
        for source, thresholds in configs.items():
            source_rows = [
                row
                for row in rows
                if source in row["source_path"] or source in row["output"] or source in row["mode"]
            ]
            model_rows = [
                row
                for row in source_rows
                if "_model_" in row["output"] or "综合模型" in row["mode"] or "模型刷新" in row["mode"]
            ]
            last_model = max(model_rows, key=lambda row: row["position"]) if model_rows else None
            after_position = last_model["position"] if last_model else -1
            articles_after = sum(
                1
                for row in source_rows
                if row["position"] > after_position
                and re.fullmatch(r"\d+", row["id"])
                and "原始资料/" in row["source_path"]
            )
            threshold = thresholds["refresh"] if last_model else thresholds["first"]
            states.append(
                {
                    "source": source,
                    "has_model": bool(last_model),
                    "last_model": last_model["output"] if last_model else None,
                    "articles_since_model": articles_after,
                    "threshold": threshold,
                    "remaining": max(0, threshold - articles_after),
                    "due": articles_after >= threshold,
                }
            )
        return states

    def macro_status(self) -> dict:
        dashboard = self.settings.macro_root / "dashboard.html"
        if not dashboard.exists():
            return {"available": False, "generated": None, "warnings": [], "errors": []}
        try:
            text = dashboard.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"const DATA = (\{.*?\});\s*\n", text, re.S)
            if not match:
                return {"available": True, "generated": None, "warnings": [], "errors": ["未识别嵌入数据"]}
            data = json.loads(match.group(1))
            warnings = [
                {"key": key, "status": item.get("status"), "reason": item.get("reason", "")}
                for key, item in data.get("series", {}).items()
                if item.get("status") in {"warn", "alert"}
            ]
            return {
                "available": True,
                "generated": data.get("generated"),
                "warnings": warnings,
                "errors": data.get("errors", []),
            }
        except Exception as exc:
            return {"available": True, "generated": None, "warnings": [], "errors": [str(exc)]}

    def refresh_macro(self) -> dict:
        generator = self.settings.macro_root / "generate.py"
        if not generator.exists():
            return {"ok": False, "output": "宏观看板生成器不存在", "status": self.macro_status()}
        try:
            result = subprocess.run(
                ["python", str(generator)],
                cwd=self.settings.macro_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
                shell=False,
            )
            output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
            return {"ok": result.returncode == 0, "output": output[-5000:], "status": self.macro_status()}
        except subprocess.TimeoutExpired:
            return {"ok": False, "output": "刷新超过 120 秒，已停止；最后可用页面未删除。", "status": self.macro_status()}

    def document(self, document_id: int) -> dict | None:
        with self.database.connect() as connection:
            document = connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if not document:
                return None
            chunks = connection.execute(
                "SELECT ordinal, heading, page, line_start, line_end, text FROM chunks WHERE document_id=? ORDER BY ordinal",
                (document_id,),
            ).fetchall()
        return {**dict(document), "chunks": [dict(chunk) for chunk in chunks]}

    def dashboard(self) -> dict:
        today = date.today()
        predictions = self.predictions()
        rows = self.processed_rows()
        actual_sources = self._actual_source_paths()
        ledger_sources = self._ledger_source_paths(rows)
        unprocessed = sorted(actual_sources - ledger_sources)
        missing = sorted(ledger_sources - actual_sources)

        pending = [item for item in predictions if item["status"] == "pending"]
        overdue: list[dict] = []
        due_soon: list[dict] = []
        for item in pending:
            if not item["deadline"]:
                continue
            deadline = date.fromisoformat(item["deadline"])
            if deadline < today:
                overdue.append(item)
            elif deadline <= today + timedelta(days=30):
                due_soon.append(item)

        stats: dict[str, Counter] = defaultdict(Counter)
        for item in predictions:
            stats[item["source"]][item["status"]] += 1
        source_stats = [
            {"source": source, **dict(counter), "total": sum(counter.values())}
            for source, counter in sorted(stats.items(), key=lambda pair: -sum(pair[1].values()))
        ]

        with self.database.connect() as connection:
            document_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunk_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            extraction = {
                row["extraction_status"]: row["count"]
                for row in connection.execute(
                    "SELECT extraction_status, COUNT(*) AS count FROM documents GROUP BY extraction_status"
                )
            }
            recent = [
                dict(row)
                for row in connection.execute(
                    """SELECT id, path, title, source, document_kind, extraction_status, modified_at
                       FROM documents ORDER BY modified_at DESC LIMIT 12"""
                )
            ]

        git_result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.settings.vault_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=False,
        )
        git_lines = [line for line in git_result.stdout.splitlines() if line.strip()]
        navigation_warnings = self._navigation_warnings()
        numeric_rows = [row for row in rows if re.fullmatch(r"\d+", row["id"])]

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "health": {
                "source_files": len(actual_sources),
                "knowledge_markdown": sum(1 for _ in self.settings.knowledge_root.rglob("*.md")),
                "indexed_documents": document_count,
                "indexed_chunks": chunk_count,
                "ledger_rows": len(numeric_rows),
                "latest_ledger": max((int(row["id"]) for row in numeric_rows), default=0),
                "prediction_rows": len(predictions),
                "latest_prediction": max((item["number"] for item in predictions), default=0),
                "navigation_warnings": navigation_warnings,
                "git_dirty": bool(git_lines),
                "git_changes": git_lines,
                "extraction": extraction,
            },
            "changes": {
                "unprocessed": unprocessed,
                "missing_or_moved": missing,
                "recent": recent,
            },
            "prediction_queue": {
                "overdue": sorted(overdue, key=lambda item: item["deadline"] or ""),
                "due_soon": sorted(due_soon, key=lambda item: item["deadline"] or ""),
                "recently_resolved": [item for item in reversed(predictions) if item["status"] != "pending"][:8],
                "source_stats": source_stats,
            },
            "models": self._model_states(rows),
            "macro": self.macro_status(),
        }
