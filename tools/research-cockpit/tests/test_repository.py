import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.database import Database
from backend.indexer import VaultIndexer
from backend.repository import VaultRepository, ordinary_source
from backend.search import SearchService
from test_indexer import make_settings


@pytest.fixture
def repo(tmp_path):
    settings = make_settings(tmp_path)
    settings.knowledge_root.mkdir(parents=True)
    settings.source_root.mkdir(parents=True)
    database = Database(settings.database_path)
    database.initialize()
    return VaultRepository(database, settings)


def write_ledger(repo, rows):
    lines = ["| # | 来源 | 日期 | 模式 | 输出 | 字数 | 状态 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    (repo.settings.knowledge_root / "_processed.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def article(number, source="黄哥", output=None, words="100", mode="增量分析"):
    return [str(number), f"原始资料/博客/{source}/{number}.md", "2026-09-05", mode,
            output or f"{source}/2026-09-05_analysis_{number}.md", words, "✓"]


def event(number="M10", coverage="（覆盖截至 #207）", processed="2026-09-03", version="v5.1"):
    return [number, "黄哥模型刷新" + coverage, processed, "模型刷新", f"黄哥/test_model_体系.md（滚动更新 → {version}）", "—", "✓"]


def write_model(repo, marker="2026-09-03（M10）", version="v5.1"):
    path = repo.settings.knowledge_root / "黄哥/test_model_体系.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"# 模型 {version}\n\n> **刷新状态**：本次刷新 {marker}\n", encoding="utf-8")
    return path


def state(repo):
    return repo._model_states(repo.processed_rows())[0]


def test_backfilled_events_use_coverage_and_original_date(repo):
    write_model(repo)
    # 表尾先补新事件，再补旧事件，均不能把 #209 吞进覆盖范围。
    write_ledger(repo, [article(194), article(207), article(209), event(),
                        event("M9", "（覆盖截至 #194）", "2026-08-21", "v5.0")])
    result = state(repo)
    assert result["articles_since_model"] == 1
    assert result["remaining"] == 9
    assert result["due"] is False
    assert result["warnings"] == []


def test_legacy_position_and_reused_outputs(repo):
    write_model(repo, marker="2026-08-05（M8）", version="v4.0")
    duplicate = article(4, output=article(1)[4])
    weread = article(5)
    weread[1] = "原始资料/微信读书/黄哥.md"
    write_ledger(repo, [article(1), event("M8", "", "2026-08-05", "v4.0"), article(2),
                        article(3, words="0", mode="重复资料去重"), duplicate, weread, article(6, source="黄哥备份")])
    assert state(repo)["articles_since_model"] == 1
    assert state(repo)["warnings"] == []


def test_before_first_model(repo):
    write_ledger(repo, [article(1, "孟岩", output="孟岩/2026-08-07_concept_水路.md"),
                        article(2, "孟岩", output="孟岩/2026-08-08_concept_制度.md")])
    result = repo._model_states(repo.processed_rows())[1]
    assert result["articles_since_model"] == 2
    assert result["remaining"] == 1
    assert not result["has_model"]
    assert result["warnings"] == []


@pytest.mark.parametrize("mismatch", ["id", "date", "version", "missing", "marker", "coverage", "bad_coverage", "missing_event"])
def test_unverifiable_model_returns_warning(repo, mismatch):
    path = write_model(repo)
    row = event()
    if mismatch == "id":
        write_model(repo, marker="2026-09-03（M11）")
    elif mismatch == "date":
        write_model(repo, marker="2026-09-04（M10）")
    elif mismatch == "version":
        write_model(repo, version="v5.10")
    elif mismatch == "missing":
        path.unlink()
    elif mismatch == "marker":
        path.write_text("# 无刷新标记", encoding="utf-8")
    elif mismatch == "coverage":
        row = event(coverage="（覆盖截至 #999）")
    elif mismatch == "bad_coverage":
        row = event(coverage="（覆盖截至 #不明）")
    write_ledger(repo, [article(207)] + ([] if mismatch == "missing_event" else [row]))
    assert state(repo)["warnings"]


def test_weread_excluded_only_from_reconciliation(repo):
    root = repo.settings.source_root
    for folder in ["微信读书", "微信读书备份", "博客/黄哥"]:
        (root / folder).mkdir(parents=True)
        (root / folder / "book.md").write_text("# 阅读样本\n\n独特检索词测试。", encoding="utf-8")
    legacy = article(1)
    legacy[1] = "原始资料/微信读书/deleted.md"
    write_ledger(repo, [legacy])
    VaultIndexer(repo.database, repo.settings).refresh()
    result = repo.dashboard()
    assert result["health"]["source_files"] == 3
    assert result["changes"]["unprocessed"] == ["原始资料/博客/黄哥/book.md", "原始资料/微信读书备份/book.md"]
    assert result["changes"]["missing_or_moved"] == []
    hits = SearchService(repo.database).search("独特检索词", source="微信读书")
    assert any(hit["path"] == "原始资料/微信读书/book.md" for hit in hits)
    assert not ordinary_source("原始资料\\微信读书\\nested\\note.md")
    assert ordinary_source("原始资料/博客/微信读书/note.md")


@pytest.mark.parametrize("outcome", ["success", "failure", "timeout", "launch_error"])
def test_macro_api_keeps_contract_and_uses_current_python(repo, monkeypatch, outcome):
    repo.settings.macro_root.mkdir(parents=True)
    (repo.settings.macro_root / "generate.py").touch()

    def run(args, **kwargs):
        assert args[0] == sys.executable
        assert kwargs["shell"] is False
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args, 120)
        if outcome == "launch_error":
            raise OSError("cannot start")
        return SimpleNamespace(returncode=int(outcome == "failure"), stdout="result", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    result = repo.refresh_macro()
    assert set(result) == {"ok", "output", "status"}
    assert result["ok"] is (outcome == "success")
    assert result["output"]


def test_powershell_validator_obeys_directory_boundary(repo):
    root = repo.settings.vault_root
    knowledge = repo.settings.knowledge_root
    write_ledger(repo, [])
    (knowledge / "目录.md").write_text("[预测追踪表](预测追踪表.md)\n", encoding="utf-8")
    (knowledge / "预测追踪表.md").write_text("# 预测\n", encoding="utf-8")
    for folder, filename in [("微信读书/nested", "reading.md"), ("微信读书备份", "ordinary.md")]:
        path = repo.settings.source_root / folder / filename
        path.parent.mkdir(parents=True)
        path.write_text("# note\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[3] / "scripts/validate_repository.ps1"
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                             "-RepositoryRoot", str(root)], capture_output=True, check=False)
    output = result.stdout.decode("utf-8", errors="replace")
    assert result.returncode == 0, result.stderr
    assert "0 errors, 1 warnings" in output
    assert "ordinary.md" in output
    assert "reading.md" not in output
    assert "Source files (excluding .gitkeep): 2" in output


def run_validator(repo):
    script = Path(__file__).resolve().parents[3] / "scripts/validate_repository.ps1"
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                             "-RepositoryRoot", str(repo.settings.vault_root)], capture_output=True, check=False)
    return result.returncode, result.stdout.decode("utf-8", errors="replace")


def test_bidirectional_validation_uses_fields_and_full_paths(repo):
    knowledge = repo.settings.knowledge_root
    source = repo.settings.source_root / "博客/黄哥/new.md"
    source.parent.mkdir(parents=True)
    source.write_text("# 新资料\n", encoding="utf-8")
    (knowledge / "a").mkdir()
    (knowledge / "b").mkdir()
    for folder in ("a", "b"):
        (knowledge / folder / "same.md").write_text("# 同名文件\n", encoding="utf-8")
    (knowledge / "预测追踪表.md").write_text("# 预测\n", encoding="utf-8")
    (knowledge / "目录.md").write_text("[a](a/same.md)\n[b](b/missing.md)\n[预测](预测追踪表.md)\n", encoding="utf-8")
    row = article(1, output="a/same.md / b/absent.md")
    # 出现在备注里不等于来源字段已登记。
    row[-1] = "✓ 提到 原始资料/博客/黄哥/new.md"
    write_ledger(repo, [row])
    code, output = run_validator(repo)
    assert code == 1
    assert "Ledger source missing or moved (#1)" in output
    assert "Source file is not present" in output and "new.md" in output
    assert "Ledger output missing (#1): b/absent.md" in output
    assert "Index link target does not exist: b/missing.md" in output
    assert "b\\same.md" in output
    assert len(repo._navigation_warnings()) == 2
    assert len(repo._ledger_output_warnings(repo.processed_rows())) == 1


def test_deleted_source_keeps_output_and_encoded_navigation(repo):
    knowledge = repo.settings.knowledge_root
    (knowledge / "space note.md").write_text("# 笔记\n", encoding="utf-8")
    (knowledge / "second.md").write_text("# 第二篇\n", encoding="utf-8")
    (knowledge / "预测追踪表.md").write_text("# 预测\n", encoding="utf-8")
    (knowledge / "目录.md").write_text("[一](space%20note.md#标题)\n[二](second.md)\n[预测](预测追踪表.md)\n", encoding="utf-8")
    row = article(1, output="space note.md / second.md")
    row[-1] = "已删除（原始资料删除，输出保留）"
    write_ledger(repo, [row])
    code, output = run_validator(repo)
    assert code == 0, output
    assert "0 warnings" in output
    assert repo._navigation_warnings() == []
    assert repo._ledger_output_warnings(repo.processed_rows()) == []
    (knowledge / "second.md").unlink()
    code, output = run_validator(repo)
    assert code == 1
    assert "Ledger output missing" in output
