"""Offline retrieval smoke benchmark against the current Vault."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import settings
from backend.database import Database
from backend.search import SearchService


questions = json.loads((Path(__file__).parent / "benchmark_questions.json").read_text(encoding="utf-8"))
search = SearchService(Database(settings.database_path))
hits = 0
for item in questions:
    results = search.search(item["query"], limit=5)
    sources = {result["source"] for result in results}
    ok = any(expected in sources for expected in item["expected_sources"])
    hits += int(ok)
    if not ok:
        print("MISS", item["query"], "=>", ", ".join(sorted(sources)))
print(f"TOP5_SOURCE_HIT={hits}/{len(questions)}")
