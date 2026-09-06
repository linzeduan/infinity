import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def generator(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[3] / ".claude/tools/huangge-dashboard/generate.py"
    spec = importlib.util.spec_from_file_location("macro_generator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "HERE", tmp_path)
    (tmp_path / "template.html").write_text("<script>const DATA = /*__DATA__*/null;</script>", encoding="utf-8")
    rows = [(f"{2024 + i // 12}-{i % 12 + 1:02d}-01", 100.0 + i) for i in range(30)]
    monkeypatch.setattr(module, "fetch", lambda *_args: rows)
    return module


def test_success_publishes_complete_page(generator, tmp_path):
    output = tmp_path / "dashboard.html"
    output.write_text("old page", encoding="utf-8")
    assert generator.main() == 0
    text = output.read_text(encoding="utf-8")
    payload = json.loads(text.split("const DATA = ")[1].split(";</script>")[0])
    assert len(payload["series"]) == 18
    assert payload["errors"] == []
    assert payload["generated"]
    assert not list(tmp_path.glob(".dashboard-*.tmp"))


@pytest.mark.parametrize("existing", [True, False])
@pytest.mark.parametrize("failure", ["one_series", "all_series", "template", "duplicate_marker", "missing_template", "write", "replace", "nonfinite"])
def test_failure_preserves_last_page(generator, tmp_path, monkeypatch, failure, existing):
    output = tmp_path / "dashboard.html"
    original = b"last complete page with original generation time"
    if existing:
        output.write_bytes(original)
        modified = output.stat().st_mtime_ns

    def fail(*_args, **_kwargs):
        raise OSError("simulated failure")

    if failure in {"one_series", "all_series"}:
        fetch = generator.fetch
        monkeypatch.setattr(generator, "fetch", lambda key: fail() if failure == "all_series" or key == "RSAFS" else fetch(key))
    elif failure == "template":
        (tmp_path / "template.html").write_text("no data marker", encoding="utf-8")
    elif failure == "duplicate_marker":
        (tmp_path / "template.html").write_text("/*__DATA__*/null /*__DATA__*/null", encoding="utf-8")
    elif failure == "missing_template":
        (tmp_path / "template.html").unlink()
    elif failure == "write":
        original_open = generator.tempfile.NamedTemporaryFile

        @contextmanager
        def broken_writer(*args, **kwargs):
            with original_open(*args, **kwargs) as handle:
                yield SimpleNamespace(name=handle.name, write=fail)

        monkeypatch.setattr(generator.tempfile, "NamedTemporaryFile", broken_writer)
    elif failure == "replace":
        monkeypatch.setattr(Path, "replace", fail)
    elif failure == "nonfinite":
        monkeypatch.setattr(generator, "fetch", lambda *_args: [("2025-01-01", float("nan"))] * 30)

    assert generator.main() == 1
    if existing:
        assert output.read_bytes() == original
        assert output.stat().st_mtime_ns == modified
    else:
        assert not output.exists()
    assert not list(tmp_path.glob(".dashboard-*.tmp"))
