from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMProvider(ABC):
    @property
    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    def rewrite_query(self, query: str) -> list[str]: ...

    @abstractmethod
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]: ...

    @abstractmethod
    def stream_answer(self, messages: list[dict], reasoning: bool = False) -> Iterator[str]: ...
