from pathlib import Path

from backend.config import Settings
from backend.database import Database
from backend.indexer import VaultIndexer


def make_settings(root: Path) -> Settings:
    app = root / "tools" / "research-cockpit"
    return Settings(
        vault_root=root,
        cache_root=root / ".cache" / "research-cockpit",
        database_path=root / ".cache" / "research-cockpit" / "test.sqlite3",
        frontend_dist=app / "frontend" / "dist",
        knowledge_root=root / "知识库",
        source_root=root / "原始资料",
        macro_root=root / ".claude" / "tools" / "huangge-dashboard",
        deepseek_api_key="",
        host="127.0.0.1",
        port=8765,
    )


def test_incremental_index_and_removal(tmp_path):
    settings = make_settings(tmp_path)
    settings.knowledge_root.mkdir(parents=True)
    settings.source_root.mkdir(parents=True)
    note = settings.knowledge_root / "sample.md"
    note.write_text("# 样本\n\n现金流与资本开支。", encoding="utf-8")
    database = Database(settings.database_path)
    indexer = VaultIndexer(database, settings)

    first = indexer.refresh()
    assert first.inserted == 1
    assert first.chunks == 1
    second = indexer.refresh()
    assert second.unchanged == 1

    note.unlink()
    third = indexer.refresh()
    assert third.removed == 1


def test_image_is_local_only_and_unsearchable(tmp_path):
    settings = make_settings(tmp_path)
    settings.knowledge_root.mkdir(parents=True)
    settings.source_root.mkdir(parents=True)
    (settings.source_root / "table.png").write_bytes(b"not-a-real-png")
    database = Database(settings.database_path)
    VaultIndexer(database, settings).refresh()
    with database.connect() as connection:
        row = connection.execute("SELECT extraction_status, cloud_allowed FROM documents").fetchone()
        chunks = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert row["extraction_status"] == "unsupported"
    assert row["cloud_allowed"] == 0
    assert chunks == 0
