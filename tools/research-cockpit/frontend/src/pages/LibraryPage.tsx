import { BookMarked, FileSearch, FileText, Search, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import DocumentDrawer from "../components/DocumentDrawer";
import type { SearchResult } from "../types";

export default function LibraryPage() {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const [documentId, setDocumentId] = useState<number | null>(null);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true); setError(""); setSearched(true);
    try { setResults((await api.search(query.trim(), kind || undefined)).items); }
    catch (err) { setError(String(err)); }
    finally { setLoading(false); }
  };

  return <div className="page library-page">
    <header className="page-header"><div><span className="eyebrow">LOCAL FULL-TEXT SEARCH</span><h1>资料检索</h1><p>索引在本机，受限材料也只在本机。搜索不需要惊动任何云。</p></div></header>
    <section className="search-box">
      <Search size={21} />
      <input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && search()} placeholder="搜索公司、人物、框架、观点或数字…" autoFocus />
      <select value={kind} onChange={(event) => setKind(event.target.value)}><option value="">全部资料</option><option value="knowledge">知识产物</option><option value="source">原始资料</option></select>
      <button className="primary-button" onClick={search} disabled={loading}>{loading ? "检索中" : "搜索"}</button>
    </section>
    {error && <div className="error-box">{error}</div>}
    {searched && <div className="result-summary"><span>找到 {results.length} 个高相关片段</span><span>BM25 · 标题加权 · 本地排序</span></div>}
    <section className="search-results">
      {results.map((result) => <button className="search-result" key={result.id} onClick={() => setDocumentId(result.document_id)}>
        <div className={`result-icon ${result.document_kind}`}>{result.document_kind === "knowledge" ? <BookMarked /> : <FileText />}</div>
        <div className="result-body">
          <div className="result-title"><span>{result.source}</span><h2>{result.title}</h2>{(!result.cloud_allowed || result.extraction_status !== "ok") && <ShieldAlert size={16} />}</div>
          {result.heading && <strong className="result-heading">{result.heading}</strong>}
          <p>{result.snippet}</p>
          <div className="result-meta"><span>{result.path}</span><span>{result.page ? `第 ${result.page} 页` : result.line_start ? `L${result.line_start}–${result.line_end}` : "正文"}</span><span>相关度 {Math.round(result.score)}</span></div>
        </div>
      </button>)}
      {searched && !loading && !results.length && <div className="empty-state large"><FileSearch size={28} /><strong>没有找到足够相关的片段</strong><p>试试更短的实体名、公司名，或去掉时间限定。</p></div>}
    </section>
    <DocumentDrawer documentId={documentId} onClose={() => setDocumentId(null)} />
  </div>;
}
