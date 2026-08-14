from __future__ import annotations

import json
import re
from collections.abc import Iterator

from .models import ChatRequest
from .providers.base import LLMProvider
from .search import SearchService


MODE_GUIDANCE = {
    "qa": "直接回答问题，先给核心判断，再列证据。",
    "compare": "对照不同信源的共同点、分歧、各自证据与利益位置，不要强行裁决。",
    "audit": "按时间梳理判断如何变化，核对验证条件、期限、结果与口径漂移。",
}


SYSTEM_PROMPT = """你是 Infinity 个人研究知识库的只读研究助手。
只能使用用户提供的证据片段，严禁调用常识补齐事实，严禁编造引用。
必须遵守：
1. 每个实质结论就近引用 [S1] 这类证据编号。
2. 明确区分【事实】【信源观点】【分析判断】【推测】。
3. 固定包含“反方视角或失效边界”和“未核实项”两节。
4. 涉及投资时不得承诺收益；关键数字若证据不是原始资料，说明应回原件核对。
5. 如果证据不足，直接说不足，不补猜。
"""


class AgentService:
    def __init__(self, search: SearchService, provider: LLMProvider):
        self.search = search
        self.provider = provider

    def prepare(self, request: ChatRequest) -> tuple[list[dict], list[dict], list[str]]:
        queries = self.provider.rewrite_query(request.query)
        merged: dict[str, dict] = {}
        for query in queries[:4]:
            for item in self.search.search(query, limit=16, source=request.source, document_kind=request.document_kind):
                existing = merged.get(item["id"])
                if existing is None or item["score"] > existing["score"]:
                    merged[item["id"]] = item
        candidates = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
        candidates = self.provider.rerank(request.query, candidates)
        allowed = [
            item for item in candidates if item["cloud_allowed"] and item["extraction_status"] == "ok"
        ]
        blocked = [
            item for item in candidates if not item["cloud_allowed"] or item["extraction_status"] != "ok"
        ]
        selected: list[dict] = []
        per_document: dict[int, int] = {}
        per_source: dict[str, int] = {}
        for item in allowed:
            if per_document.get(item["document_id"], 0) >= 2:
                continue
            if per_source.get(item["source"], 0) >= 4:
                continue
            selected.append(item)
            per_document[item["document_id"]] = per_document.get(item["document_id"], 0) + 1
            per_source[item["source"]] = per_source.get(item["source"], 0) + 1
            if len(selected) == 8:
                break
        warnings: list[str] = []
        if blocked:
            warnings.append(f"有 {len(blocked)} 条受限或提取存疑证据仅在本地展示，未发送云端模型。")
        if len(selected) < 3:
            warnings.append("可安全发送的证据较少，回答覆盖可能不足。")
        return selected, blocked[:6], warnings

    @staticmethod
    def citations(items: list[dict]) -> list[dict]:
        return [
            {
                "id": f"S{index}",
                "document_id": item["document_id"],
                "path": item["path"],
                "title": item["title"],
                "heading": item["heading"],
                "page": item["page"],
                "line_start": item["line_start"],
                "line_end": item["line_end"],
                "snippet": item["snippet"],
                "extraction_status": item["extraction_status"],
                "cloud_allowed": item["cloud_allowed"],
            }
            for index, item in enumerate(items, start=1)
        ]

    def stream(self, request: ChatRequest) -> Iterator[str]:
        selected, blocked, warnings = self.prepare(request)
        citations = self.citations(selected)
        blocked_citations = self.citations(blocked)
        meta = {
            "citations": citations,
            "local_only_citations": blocked_citations,
            "coverage_warnings": warnings,
            "cloud_usage": {
                "provider": "deepseek" if self.provider.configured else None,
                "sent_chunks": len(selected),
                "blocked_chunks": len(blocked),
            },
        }
        yield self._event("meta", meta)

        if not selected:
            answer = (
                "## 结论\n\n当前命中内容全部属于受限材料或提取质量存疑，未发送云端模型。"
                "请在下方本地证据中人工核对；我不会用缺失内容补猜。\n\n"
                "## 反方视角或失效边界\n\n本次结论仅代表云端安全边界，不代表知识库没有相关信息。\n\n"
                "## 未核实项\n\n受限及存疑材料尚未形成模型回答。"
            )
            yield self._event("delta", {"content": answer})
            yield self._event("done", {"ok": True})
            return
        if not self.provider.configured:
            yield self._event(
                "error",
                {"message": "尚未配置 DEEPSEEK_API_KEY。检索已完成，但不能生成云端回答。"},
            )
            return

        evidence = "\n\n".join(
            f"[S{index}] 文件：{item['path']}\n位置：{item['heading'] or ('第'+str(item['page'])+'页' if item['page'] else '正文')}\n证据：{item['full_text'][:1400]}"
            for index, item in enumerate(selected, start=1)
        )
        user_prompt = (
            f"任务模式：{MODE_GUIDANCE[request.mode]}\n"
            f"用户问题：{request.query}\n\n"
            f"证据片段：\n{evidence}"
        )
        try:
            deltas: list[str] = []
            for delta in self.provider.stream_answer(
                [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
                reasoning=request.mode in {"compare", "audit"},
            ):
                deltas.append(delta)
            if not deltas:
                yield self._event("error", {"message": "模型未返回内容。"})
                return
            answer = "".join(deltas)
            audit_errors = self._audit_answer(answer, len(citations))
            if audit_errors:
                answer = (
                    "## 引用校验未通过\n\n"
                    "模型草稿没有满足逐项引用约束，已被服务端拦截，避免展示无证据结论。"
                    "你仍可在右侧打开本地证据，或复制证据包交给 Codex。\n\n"
                    "## 反方视角或失效边界\n\n"
                    "当前只能确认检索命中，不能确认模型草稿中的结论可靠。\n\n"
                    "## 未核实项\n\n"
                    + "；".join(audit_errors)
                )
            for start in range(0, len(answer), 220):
                yield self._event("delta", {"content": answer[start : start + 220]})
            yield self._event("done", {"ok": True})
        except Exception as exc:
            yield self._event("error", {"message": f"DeepSeek 请求失败：{type(exc).__name__}"})

    @staticmethod
    def _audit_answer(answer: str, citation_count: int) -> list[str]:
        errors: list[str] = []
        references = {int(value) for value in re.findall(r"\[S(\d+)\]", answer)}
        if not references:
            errors.append("答案没有引用任何证据编号")
        unknown = sorted(value for value in references if value < 1 or value > citation_count)
        if unknown:
            errors.append("答案引用了不存在的证据编号：" + ", ".join(f"S{value}" for value in unknown))
        if not any(label in answer for label in ("【事实】", "【信源观点】", "【分析判断】", "【推测】")):
            errors.append("答案没有区分事实、信源观点、分析判断或推测")
        if "反方视角" not in answer and "失效边界" not in answer:
            errors.append("答案缺少反方视角或失效边界")
        if "未核实项" not in answer:
            errors.append("答案缺少未核实项")

        for paragraph in re.split(r"\n\s*\n", answer):
            plain = re.sub(r"[#*_>`]", "", paragraph).strip()
            if len(plain) < 24 or plain.startswith("未核实项"):
                continue
            if any(label in paragraph for label in ("【事实】", "【信源观点】", "【分析判断】", "【推测】")):
                if not re.search(r"\[S\d+\]", paragraph):
                    errors.append("存在未附引用的实质结论")
                    break
        return errors

    @staticmethod
    def _event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
