import { ExternalLink, FileText, ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";

interface Chunk {
  ordinal: number;
  heading?: string | null;
  page?: number | null;
  line_start?: number | null;
  line_end?: number | null;
  text: string;
}

interface DocumentData {
  id: number;
  title: string;
  path: string;
  source: string;
  extraction_status: string;
  cloud_allowed: number;
  restriction_reason?: string | null;
  chunks: Chunk[];
}

export default function DocumentDrawer({ documentId, onClose }: { documentId: number | null; onClose: () => void }) {
  const [document, setDocument] = useState<DocumentData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!documentId) return;
    setDocument(null);
    setError("");
    api.document(documentId).then((value) => setDocument(value as unknown as DocumentData)).catch((err) => setError(String(err)));
  }, [documentId]);
  if (!documentId) return null;
  return (
    <>
      <button className="drawer-scrim" onClick={onClose} aria-label="关闭文档" />
      <aside className="document-drawer">
        <header>
          <div><span className="eyebrow">本地原文预览</span><h2>{document?.title || "正在读取…"}</h2></div>
          <button className="icon-button" onClick={onClose}><X size={20} /></button>
        </header>
        {error && <div className="error-box">{error}</div>}
        {document && (
          <>
            <div className="document-meta">
              <span><FileText size={14} />{document.path}</span>
              {(!document.cloud_allowed || document.extraction_status !== "ok") && (
                <span className="restricted"><ShieldAlert size={14} />{document.restriction_reason || "仅本地可见"}</span>
              )}
            </div>
            <a className="secondary-button full" href={`/api/documents/${document.id}/file`} target="_blank" rel="noreferrer">
              <ExternalLink size={15} /> 打开原文件
            </a>
            <div className="document-content">
              {document.chunks.map((chunk) => (
                <section key={chunk.ordinal}>
                  {chunk.heading && <h3>{chunk.heading}</h3>}
                  <span className="location-tag">
                    {chunk.page ? `第 ${chunk.page} 页` : chunk.line_start ? `L${chunk.line_start}–${chunk.line_end}` : "正文"}
                  </span>
                  <pre>{chunk.text}</pre>
                </section>
              ))}
              {!document.chunks.length && <div className="empty-state">该文件没有可安全预览的文本。</div>}
            </div>
          </>
        )}
      </aside>
    </>
  );
}
