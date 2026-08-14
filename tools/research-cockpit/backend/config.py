from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = Path(os.getenv("INFINITY_VAULT_ROOT", APP_ROOT.parents[1])).resolve()
CACHE_ROOT = (VAULT_ROOT / ".cache" / "research-cockpit").resolve()
DB_PATH = CACHE_ROOT / "cockpit.sqlite3"
FRONTEND_DIST = APP_ROOT / "frontend" / "dist"
KNOWLEDGE_ROOT = VAULT_ROOT / "知识库"
SOURCE_ROOT = VAULT_ROOT / "原始资料"
MACRO_ROOT = VAULT_ROOT / ".claude" / "tools" / "huangge-dashboard"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


_load_env_file(APP_ROOT / ".env.local")
_load_env_file(VAULT_ROOT / ".env.local")


@dataclass(frozen=True)
class Settings:
    vault_root: Path = VAULT_ROOT
    cache_root: Path = CACHE_ROOT
    database_path: Path = DB_PATH
    frontend_dist: Path = FRONTEND_DIST
    knowledge_root: Path = KNOWLEDGE_ROOT
    source_root: Path = SOURCE_ROOT
    macro_root: Path = MACRO_ROOT
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_reasoning_model: str = os.getenv("DEEPSEEK_REASONING_MODEL", "deepseek-reasoner")
    host: str = os.getenv("COCKPIT_HOST", "127.0.0.1")
    port: int = int(os.getenv("COCKPIT_PORT", "8765"))

    def ensure_safe_host(self) -> None:
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError("Research Cockpit 只允许监听 localhost。")


settings = Settings()
