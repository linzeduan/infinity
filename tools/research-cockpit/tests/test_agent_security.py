from backend.agent import AgentService
from backend.models import ChatRequest
from backend.providers.base import LLMProvider


class FakeSearch:
    def search(self, *_args, **_kwargs):
        base = {
            "document_id": 1,
            "title": "样本",
            "heading": "结论",
            "page": None,
            "line_start": 1,
            "line_end": 3,
            "snippet": "片段",
            "full_text": "完整证据",
            "source": "测试",
            "document_kind": "knowledge",
            "score": 90,
            "modified_at": "2026-01-01T00:00:00",
            "restriction_reason": None,
        }
        return [
            {**base, "id": "C1", "path": "知识库/a.md", "cloud_allowed": True, "extraction_status": "ok"},
            {**base, "id": "C2", "path": "知识库/private.md", "cloud_allowed": False, "extraction_status": "ok", "restriction_reason": "不外传"},
            {**base, "id": "C3", "path": "原始资料/bad.pdf", "cloud_allowed": False, "extraction_status": "suspect"},
        ]


class FakeProvider(LLMProvider):
    sent_messages = None

    @property
    def configured(self): return True
    def rewrite_query(self, query): return [query]
    def rerank(self, _query, candidates): return candidates
    def stream_answer(self, messages, reasoning=False):
        self.sent_messages = messages
        yield "【分析判断】测试回答 [S1]"


def test_blocked_content_never_reaches_provider():
    provider = FakeProvider()
    service = AgentService(FakeSearch(), provider)
    output = "".join(service.stream(ChatRequest(query="测试问题", mode="qa")))
    serialized = str(provider.sent_messages)
    assert "完整证据" in serialized
    assert "private.md" not in serialized
    assert "bad.pdf" not in serialized
    assert "blocked_chunks" in output


class UngroundedProvider(FakeProvider):
    def stream_answer(self, messages, reasoning=False):
        self.sent_messages = messages
        yield "这是一个没有引用的模型结论。"


def test_ungrounded_model_answer_is_blocked():
    service = AgentService(FakeSearch(), UngroundedProvider())
    output = "".join(service.stream(ChatRequest(query="测试问题", mode="qa")))
    assert "引用校验未通过" in output
    assert "这是一个没有引用的模型结论" not in output
