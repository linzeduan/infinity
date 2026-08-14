from __future__ import annotations

import json
import re
from collections.abc import Iterator

import httpx

from ..config import Settings
from .base import LLMProvider


class DeepSeekProvider(LLMProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

    def _complete(self, messages: list[dict], model: str | None = None, max_tokens: int = 900) -> str:
        if not self.configured:
            return ""
        response = httpx.post(
            f"{self.settings.deepseek_base_url}/chat/completions",
            headers=self.headers,
            json={
                "model": model or self.settings.deepseek_model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def rewrite_query(self, query: str) -> list[str]:
        if not self.configured:
            return [query]
        prompt = (
            "把用户的中文研究问题改写为最多3个适合本地全文检索的短查询。"
            "只返回 JSON：{\"queries\":[\"...\"]}，不得加入知识或答案。\n问题：" + query
        )
        try:
            content = self._complete([{"role": "user", "content": prompt}], max_tokens=250)
            match = re.search(r"\{.*\}", content, re.S)
            data = json.loads(match.group(0) if match else content)
            queries = [str(item).strip() for item in data.get("queries", []) if str(item).strip()]
            return [query] + [item for item in queries if item != query][:3]
        except Exception:
            return [query]

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        if not self.configured or len(candidates) < 2:
            return candidates
        safe_candidates = [item for item in candidates if item["cloud_allowed"] and item["extraction_status"] == "ok"][:15]
        if not safe_candidates:
            return candidates
        payload = [
            {"id": item["id"], "title": item["title"], "heading": item["heading"], "snippet": item["snippet"][:260]}
            for item in safe_candidates
        ]
        prompt = (
            "按回答研究问题的相关性给候选证据排序。只返回 JSON："
            "{\"ids\":[\"C1\",\"C2\"]}。不得扩写或引用候选外信息。\n"
            f"问题：{query}\n候选：{json.dumps(payload, ensure_ascii=False)}"
        )
        try:
            content = self._complete([{"role": "user", "content": prompt}], max_tokens=350)
            match = re.search(r"\{.*\}", content, re.S)
            data = json.loads(match.group(0) if match else content)
            order = {item_id: index for index, item_id in enumerate(data.get("ids", []))}
            safe_sorted = sorted(safe_candidates, key=lambda item: order.get(item["id"], 9999))
            blocked = [item for item in candidates if item not in safe_candidates]
            return safe_sorted + blocked
        except Exception:
            return candidates

    def stream_answer(self, messages: list[dict], reasoning: bool = False) -> Iterator[str]:
        model = self.settings.deepseek_reasoning_model if reasoning else self.settings.deepseek_model
        with httpx.stream(
            "POST",
            f"{self.settings.deepseek_base_url}/chat/completions",
            headers=self.headers,
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 3000,
                "stream": True,
            },
            timeout=120,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
                if delta:
                    yield delta
