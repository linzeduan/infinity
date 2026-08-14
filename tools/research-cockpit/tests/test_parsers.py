import sys
from types import SimpleNamespace

from backend.parsers import (
    normalize_deadline,
    parse_pdf,
    parse_table,
    parse_markdown,
    prediction_status,
    split_markdown_row,
)


def test_markdown_chunks_keep_heading_and_lines(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("# 标题\n\n第一段。\n\n## 反方视角\n\n第二段。", encoding="utf-8")
    document = parse_markdown(path)
    assert document.title == "标题"
    assert len(document.chunks) == 2
    assert document.chunks[1].heading == "反方视角"
    assert document.chunks[1].line_start == 5


def test_restricted_markdown_never_allows_cloud(tmp_path):
    path = tmp_path / "private.md"
    path.write_text("# 内部\n\n本材料不外传。", encoding="utf-8")
    document = parse_markdown(path)
    assert document.cloud_allowed is False
    assert "不外传" in (document.restriction_reason or "")


def test_markdown_table_preserves_escaped_pipe():
    cells = split_markdown_row(r"| 1 | A \| B | 待验证 |")
    assert cells == ["1", "A | B", "待验证"]


def test_abnormal_table_rows_are_skipped(tmp_path):
    path = tmp_path / "ledger.md"
    path.write_text(
        "| 编号 | 信源 | 判断 |\n| --- | --- | --- |\n| 损坏行 |\n| 1 | 黄哥 | 测试判断 |\n",
        encoding="utf-8",
    )
    assert parse_table(path, min_columns=3) == [["1", "黄哥", "测试判断"]]


def test_pdf_chunks_keep_page_numbers(monkeypatch, tmp_path):
    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class FakeReader:
        def __init__(self, _path):
            paragraph = "这是可定位的 PDF 正文，用于验证每一页都保留页码。" * 6
            self.pages = [FakePage(paragraph), FakePage(paragraph + "第二页")]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader))
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"fake")
    document = parse_pdf(path)
    assert document.extraction_status == "ok"
    assert [chunk.page for chunk in document.chunks] == [1, 2]


def test_deadline_normalization():
    assert normalize_deadline("2026-09-30") == ("2026-09-30", "day")
    assert normalize_deadline("2026-Q3") == ("2026-09-30", "quarter")
    assert normalize_deadline("2027 上半年") == ("2027-06-30", "half-year")
    assert normalize_deadline("2028 年底") == ("2028-12-31", "year")


def test_prediction_status_order_matters():
    assert prediction_status("◐ 部分命中") == "partial"
    assert prediction_status("✅ 命中") == "hit"
    assert prediction_status("❌ 落空") == "miss"
    assert prediction_status("待验证（出现反向证据）") == "pending"
