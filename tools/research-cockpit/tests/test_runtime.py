import json
import subprocess
from pathlib import Path

import pytest


RUNTIME = Path(__file__).resolve().parents[1] / "runtime.ps1"


def quoted(path):
    return "'" + str(path).replace("'", "''") + "'"


def powershell(script):
    prefix = "[Console]::OutputEncoding = [Text.UTF8Encoding]::new(); . " + quoted(RUNTIME) + "; "
    return subprocess.run(["powershell", "-NoProfile", "-Command", prefix + script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)


@pytest.fixture
def app(tmp_path):
    for folder in ["frontend/src", "frontend/dist/assets", ".cache"]:
        (tmp_path / folder).mkdir(parents=True)
    for filename, text in {
        "requirements.txt": "fastapi\n",
        "frontend/src/main.ts": "// initial\n",
        "frontend/package.json": "{}",
        "frontend/package-lock.json": "{}",
        "frontend/index.html": "<html></html>",
        "frontend/dist/index.html": '<script src="/assets/app.js"></script>',
        "frontend/dist/assets/app.js": "// built\n",
    }.items():
        (tmp_path / filename).write_text(text, encoding="utf-8")
    return tmp_path


def state(app, ready=True):
    script = "function Test-CockpitPython { return $" + str(ready).lower() + " }; "
    result = powershell(script + "Get-CockpitSetupState " + quoted(app) + " | ConvertTo-Json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def stamp(app):
    value = state(app)
    (app / ".cache/setup.json").write_text(json.dumps({"requirements": value["Requirements"], "frontend": value["Frontend"]}), encoding="utf-8")


def test_first_setup_and_unchanged_inputs(app):
    assert state(app)["NeedsFrontend"]
    stamp(app)
    assert not state(app)["NeedsFrontend"]
    assert not state(app)["NeedsPython"]


@pytest.mark.parametrize("change", ["source", "requirements", "asset", "imports", "stamp"])
def test_stale_build_and_missing_dependencies(app, change):
    stamp(app)
    if change == "source":
        (app / "frontend/src/main.ts").write_text("// changed\n", encoding="utf-8")
    elif change == "requirements":
        (app / "requirements.txt").write_text("fastapi\nhttpx\n", encoding="utf-8")
    elif change == "asset":
        (app / "frontend/dist/assets/app.js").unlink()
    elif change == "stamp":
        (app / ".cache/setup.json").write_text("invalid json", encoding="utf-8")
    value = state(app, ready=change != "imports")
    assert value["NeedsPython"] == (change in {"requirements", "imports", "stamp"})
    assert value["NeedsFrontend"] == (change in {"source", "asset", "stamp"})


def test_python_discovery_without_project_venv(app):
    result = powershell("Get-CockpitPython " + quoted(app))
    assert result.returncode == 0, result.stderr
    python = result.stdout.strip()
    version = subprocess.check_output([python, "-c", "import sys; print(sys.version_info[:2])"], text=True).strip()
    assert version == "(3, 12)"


def test_missing_python_has_actionable_error(app):
    result = powershell("function Get-Command { return $null }; Get-CockpitPython " + quoted(app))
    assert result.returncode != 0
    assert "Install Python 3.12" in result.stderr


def test_health_requires_ready_database_frontend_and_matching_vault(app):
    root = quoted(app)
    script = f"""
    function Invoke-RestMethod {{ return $script:health }}
    $script:health = @{{ status = 'ok'; database_ready = $true; frontend_ready = $true; vault_root = {root} }}
    $results = @([bool](Get-CockpitHealth 'http://localhost' {root}))
    $script:health.database_ready = $false
    $results += [bool](Get-CockpitHealth 'http://localhost' {root})
    $script:health.database_ready = $true
    $script:health.frontend_ready = $false
    $results += [bool](Get-CockpitHealth 'http://localhost' {root})
    $script:health.frontend_ready = $true
    $script:health.vault_root = 'C:\\another-vault'
    $results += [bool](Get-CockpitHealth 'http://localhost' {root})
    ConvertTo-Json -InputObject $results
    """
    result = powershell(script)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [True, False, False, False]
