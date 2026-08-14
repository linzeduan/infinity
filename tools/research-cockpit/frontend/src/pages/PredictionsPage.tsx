import { CalendarClock, CheckCircle2, CircleDashed, Search, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Prediction } from "../types";

const statuses = [
  { id: "", label: "全部" },
  { id: "pending", label: "待验证" },
  { id: "hit", label: "命中" },
  { id: "partial", label: "部分命中" },
  { id: "miss", label: "落空" },
];

export default function PredictionsPage() {
  const [items, setItems] = useState<Prediction[]>([]);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  useEffect(() => { setLoading(true); api.predictions(status || undefined).then((data) => setItems(data.items)).finally(() => setLoading(false)); }, [status]);
  const filtered = useMemo(() => items.filter((item) => !query || `${item.source}${item.claim}${item.origin}`.toLowerCase().includes(query.toLowerCase())), [items, query]);

  return <div className="page predictions-page">
    <header className="page-header"><div><span className="eyebrow">PREDICTION LEDGER</span><h1>让判断接受时间。</h1><p>这里只记录可证伪的判断。命中不是勋章，落空也不是事故报告。</p></div></header>
    <section className="prediction-toolbar">
      <div className="status-tabs">{statuses.map((item) => <button key={item.id} className={status === item.id ? "active" : ""} onClick={() => setStatus(item.id)}>{item.label}</button>)}</div>
      <label><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="筛选信源或判断" /></label>
    </section>
    <div className="prediction-count">{loading ? "正在读取预测账本…" : `${filtered.length} 条记录`}</div>
    <section className="prediction-table">
      <div className="prediction-table-head"><span>状态</span><span>判断与信源</span><span>验证期限</span><span>编号</span></div>
      {filtered.map((item) => <button key={item.number} className={`prediction-row ${expanded === item.number ? "expanded" : ""}`} onClick={() => setExpanded(expanded === item.number ? null : item.number)}>
        <span className={`prediction-status ${item.status}`}>{item.status === "hit" ? <CheckCircle2 /> : item.status === "miss" ? <XCircle /> : item.status === "pending" ? <CircleDashed /> : <CalendarClock />}{statusLabel(item.status)}</span>
        <span className="prediction-claim"><strong>{item.source}</strong><p>{item.claim}</p>{expanded === item.number && <div className="prediction-detail"><b>验证条件</b><p>{item.verification}</p><b>当前结果</b><p>{item.result}</p><b>出处</b><p>{item.origin}</p></div>}</span>
        <span className="prediction-deadline"><strong>{item.deadline || "未规范化"}</strong><small>{item.deadline_raw}</small></span>
        <span className="prediction-number">#{item.number}</span>
      </button>)}
    </section>
  </div>;
}

function statusLabel(status: Prediction["status"]) {
  return { pending: "待验证", hit: "命中", miss: "落空", partial: "部分命中", unknown: "未分类" }[status];
}
