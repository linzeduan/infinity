import { Bot, Check, Clipboard, CornerDownLeft, GitCompareArrows, SearchCheck, ShieldAlert, Square, Target } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { streamChat } from "../api";
import DocumentDrawer from "../components/DocumentDrawer";
import RichText from "../components/RichText";
import type { ChatMeta } from "../types";

const modes = [
  { id: "qa", label: "证据问答", icon: SearchCheck, desc: "回答问题并回链原文" },
  { id: "compare", label: "信源对撞", icon: GitCompareArrows, desc: "比较立场、证据与盲区" },
  { id: "audit", label: "预测审计", icon: Target, desc: "梳理时间、口径与结果" },
];

export default function AskPage() {
  const [params] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") || "");
  const [mode, setMode] = useState("qa");
  const [answer, setAnswer] = useState("");
  const [meta, setMeta] = useState<ChatMeta | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [documentId, setDocumentId] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  const ask = async () => {
    if (query.trim().length < 2 || running) return;
    setAnswer(""); setMeta(null); setError(""); setRunning(true);
    abort.current = new AbortController();
    try {
      await streamChat(
        { query: query.trim(), mode },
        {
          onMeta: setMeta,
          onDelta: (delta) => setAnswer((current) => current + delta),
          onDone: () => setRunning(false),
          onError: (message) => { setError(message); setRunning(false); },
        },
        abort.current.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError(String(err));
      setRunning(false);
    }
  };

  const stop = () => { abort.current?.abort(); setRunning(false); };
  const copyEvidence = async () => {
    const lines = [
      `研究问题：${query}`,
      "",
      "请仅使用以下本地证据回答，并保留引用编号：",
      ...(meta?.citations || []).map((citation) => `[${citation.id}] ${citation.path} · ${citation.heading || (citation.page ? `第${citation.page}页` : "正文")}\n${citation.snippet}`),
    ];
    await navigator.clipboard.writeText(lines.join("\n\n"));
    setCopied(true); setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="page ask-page">
      <header className="page-header">
        <div><span className="eyebrow">READ-ONLY AGENT</span><h1>向知识库提问</h1><p>只用库内证据作答；资料不够时，它应该诚实地闭嘴。</p></div>
      </header>

      <section className="mode-selector">
        {modes.map(({ id, label, icon: Icon, desc }) => <button key={id} className={mode === id ? "active" : ""} onClick={() => setMode(id)}><Icon size={18} /><div><strong>{label}</strong><span>{desc}</span></div></button>)}
      </section>

      <section className="ask-composer">
        <textarea value={query} onChange={(event) => setQuery(event.target.value)} placeholder="例如：黄哥对 AI CapEx 拐点的判断，后来发生了哪些修正？" onKeyDown={(event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) ask(); }} />
        <div className="composer-foot"><span>Ctrl / ⌘ + Enter 发送</span>{running ? <button className="stop-button" onClick={stop}><Square size={14} />停止</button> : <button className="primary-button" onClick={ask} disabled={query.trim().length < 2}>开始研究 <CornerDownLeft size={16} /></button>}</div>
      </section>

      {(answer || running || error || meta) && <section className="answer-layout">
        <article className="answer-panel">
          <div className="answer-head"><div className="agent-avatar"><Bot size={19} /></div><div><strong>Infinity Analyst</strong><span>{running ? "正在沿证据链阅读…" : "只读回答"}</span></div>{meta && <button className="secondary-button small" onClick={copyEvidence}>{copied ? <Check size={14} /> : <Clipboard size={14} />}{copied ? "已复制" : "复制证据包"}</button>}</div>
          {error && <div className="error-box">{error}</div>}
          {answer ? <RichText text={answer} citations={meta?.citations || []} onCitation={setDocumentId} /> : running ? <div className="thinking"><span /><span /><span /></div> : null}
        </article>
        <aside className="evidence-panel">
          <div className="panel-header"><div><span className="eyebrow">EVIDENCE</span><h2>证据抽屉</h2></div><span>{meta?.citations.length || 0}</span></div>
          {meta?.coverage_warnings.map((warning) => <div className="coverage-warning" key={warning}><ShieldAlert size={15} />{warning}</div>)}
          <div className="evidence-list">
            {meta?.citations.map((citation) => <button key={citation.id} onClick={() => setDocumentId(citation.document_id)}><span>{citation.id}</span><div><strong>{citation.title}</strong><p>{citation.snippet}</p><small>{citation.path} · {citation.page ? `P${citation.page}` : citation.line_start ? `L${citation.line_start}` : "正文"}</small></div></button>)}
            {meta?.local_only_citations.map((citation) => <button className="local-only" key={`local-${citation.id}`} onClick={() => setDocumentId(citation.document_id)}><ShieldAlert size={15} /><div><strong>{citation.title}</strong><p>仅本地可见，未发送云端</p><small>{citation.path}</small></div></button>)}
          </div>
        </aside>
      </section>}
      <DocumentDrawer documentId={documentId} onClose={() => setDocumentId(null)} />
    </div>
  );
}
