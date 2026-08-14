import { AlertTriangle, ArrowRight, BookOpen, Check, Clock3, Database, FileWarning, RefreshCw, Sparkles, Target } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import DocumentDrawer from "../components/DocumentDrawer";
import type { DashboardData } from "../types";

const quickPrompts = [
  "今天的知识库有哪些值得关注的新变化？",
  "比较黄哥和浪淘沙最近的市场判断",
  "梳理 AI 资本开支观点的演化",
  "找出当前核心判断的反方证据",
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [documentId, setDocumentId] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    api.dashboard().then(setData).catch((err) => setError(String(err))).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const refresh = async () => {
    setRefreshing(true);
    setError("");
    try {
      await api.refreshIndex();
      setData(await api.dashboard());
    } catch (err) {
      setError(String(err));
    } finally {
      setRefreshing(false);
    }
  };

  const dateLabel = useMemo(() => new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(new Date()), []);
  if (loading && !data) return <div className="page-loader"><span /><p>正在读取你的研究系统…</p></div>;

  return (
    <div className="page dashboard-page">
      <header className="page-header hero-header">
        <div>
          <span className="eyebrow">{dateLabel} · 本地研究系统</span>
          <h1>今天，先看全局。</h1>
          <p>资料、预测和模型状态已经摊在桌面上。先处理异常，再进入观点。</p>
        </div>
        <button className="primary-button" onClick={refresh} disabled={refreshing}>
          <RefreshCw size={16} className={refreshing ? "spin" : ""} />
          {refreshing ? "正在重建索引" : "刷新本地索引"}
        </button>
      </header>
      {error && <div className="error-box">{error}</div>}

      {data && (
        <>
          <section className="metric-grid">
            <Metric icon={<Database />} label="原始资料" value={data.health.source_files} note={`${data.health.indexed_documents} 份已进入本地索引`} tone="lime" />
            <Metric icon={<BookOpen />} label="知识产物" value={data.health.knowledge_markdown} note={`${data.health.indexed_chunks.toLocaleString()} 个可检索片段`} tone="cyan" />
            <Metric icon={<Target />} label="预测账本" value={data.health.prediction_rows} note={`${data.prediction_queue.overdue.length} 条已到期未验证`} tone="amber" />
            <Metric icon={<FileWarning />} label="系统提醒" value={data.health.navigation_warnings.length + data.changes.unprocessed.length + data.changes.missing_or_moved.length} note={data.health.git_dirty ? "工作区存在未提交变化" : "Git 工作区干净"} tone="rose" />
          </section>

          <section className="dashboard-grid">
            <div className="panel span-7">
              <PanelHeader eyebrow="TODAY'S QUEUE" title="今日变化" action={<span className={`status-dot ${data.changes.unprocessed.length ? "warn" : "ok"}`}>{data.changes.unprocessed.length ? `${data.changes.unprocessed.length} 待处理` : "已对账"}</span>} />
              {(data.changes.unprocessed.length > 0 || data.changes.missing_or_moved.length > 0) && (
                <div className="alert-strip"><AlertTriangle size={17} /><span>发现 {data.changes.unprocessed.length} 个未处理文件、{data.changes.missing_or_moved.length} 个路径漂移。</span></div>
              )}
              <div className="recent-list">
                {data.changes.recent.slice(0, 7).map((item) => (
                  <button key={item.id} onClick={() => setDocumentId(item.id)}>
                    <span className={`doc-kicker ${item.document_kind}`}>{item.document_kind === "knowledge" ? "知识" : "原文"}</span>
                    <div><strong>{item.title}</strong><span>{item.source} · {new Date(item.modified_at).toLocaleDateString("zh-CN")}</span></div>
                    <ArrowRight size={16} />
                  </button>
                ))}
              </div>
            </div>

            <div className="panel span-5">
              <PanelHeader eyebrow="FALSIFIABLE" title="预测验证队列" action={<button className="text-button" onClick={() => navigate("/predictions")}>查看全部 <ArrowRight size={14} /></button>} />
              <div className="queue-summary">
                <div><span className="queue-number danger">{data.prediction_queue.overdue.length}</span><p>已逾期</p></div>
                <div><span className="queue-number warning">{data.prediction_queue.due_soon.length}</span><p>30 天内到期</p></div>
                <div><span className="queue-number calm">{data.prediction_queue.recently_resolved.length}</span><p>最近结案</p></div>
              </div>
              <div className="deadline-list">
                {[...data.prediction_queue.overdue, ...data.prediction_queue.due_soon].slice(0, 4).map((item) => (
                  <div key={item.number}>
                    <span className="prediction-index">#{item.number}</span>
                    <p>{item.claim}</p>
                    <span><Clock3 size={13} /> {item.deadline || item.deadline_raw}</span>
                  </div>
                ))}
                {!data.prediction_queue.overdue.length && !data.prediction_queue.due_soon.length && <div className="empty-state compact"><Check size={18} />近 30 天没有待验证预测。</div>}
              </div>
            </div>

            <div className="panel span-5">
              <PanelHeader eyebrow="SOURCE MODELS" title="信源模型节奏" />
              <div className="model-list">
                {data.models.map((model) => {
                  const progress = Math.min(100, Math.round((model.articles_since_model / model.threshold) * 100));
                  return <div key={model.source}>
                    <div className="model-head"><strong>{model.source}</strong><span>{model.due ? "应刷新" : `还差 ${model.remaining} 篇`}</span></div>
                    <div className="progress"><span style={{ width: `${progress}%` }} /></div>
                    <p>自上次模型后 {model.articles_since_model} / {model.threshold} 篇</p>
                  </div>;
                })}
              </div>
            </div>

            <div className="panel span-7 prompt-panel">
              <PanelHeader eyebrow="ASK THE VAULT" title="从一个好问题开始" action={<Sparkles size={19} />} />
              <div className="prompt-grid">
                {quickPrompts.map((prompt, index) => (
                  <button key={prompt} onClick={() => navigate(`/ask?q=${encodeURIComponent(prompt)}`)}><span>0{index + 1}</span>{prompt}<ArrowRight size={15} /></button>
                ))}
              </div>
            </div>

            <div className="panel span-12 macro-panel">
              <div>
                <span className="eyebrow">MACRO SIGNALS</span>
                <h2>黄哥宏观指标看板</h2>
                <p>{data.macro.available ? `数据生成于 ${data.macro.generated || "未知时间"}，当前 ${data.macro.warnings.length} 项关注/预警。` : "尚未生成本地宏观看板。"}</p>
              </div>
              <div className="macro-actions">
                {data.macro.warnings.slice(0, 3).map((warning) => <span key={warning.key} className={`macro-pill ${warning.status}`}>{warning.key}</span>)}
                {data.macro.available && <a className="secondary-button" href="/api/macro/page" target="_blank" rel="noreferrer">打开看板 <ArrowRight size={15} /></a>}
              </div>
            </div>
          </section>
        </>
      )}
      <DocumentDrawer documentId={documentId} onClose={() => setDocumentId(null)} />
    </div>
  );
}

function Metric({ icon, label, value, note, tone }: { icon: React.ReactNode; label: string; value: number; note: string; tone: string }) {
  return <div className={`metric-card ${tone}`}><div className="metric-icon">{icon}</div><div><span>{label}</span><strong>{value.toLocaleString()}</strong><p>{note}</p></div></div>;
}

function PanelHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) {
  return <div className="panel-header"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>{action && <div>{action}</div>}</div>;
}
