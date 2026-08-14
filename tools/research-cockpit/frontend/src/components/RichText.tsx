import type { Citation } from "../types";

function Inline({ text, citations, onCitation }: { text: string; citations: Citation[]; onCitation: (id: number) => void }) {
  const parts = text.split(/(\[S\d+\])/g);
  return <>{parts.map((part, index) => {
    const match = part.match(/^\[S(\d+)\]$/);
    if (!match) return <span key={index}>{part}</span>;
    const citation = citations[Number(match[1]) - 1];
    return citation ? <button key={index} className="citation-chip" onClick={() => onCitation(citation.document_id)}>{part}</button> : <span key={index}>{part}</span>;
  })}</>;
}

export default function RichText({ text, citations, onCitation }: { text: string; citations: Citation[]; onCitation: (id: number) => void }) {
  return <div className="rich-text">{text.split("\n").map((line, index) => {
    if (line.startsWith("### ")) return <h4 key={index}><Inline text={line.slice(4)} citations={citations} onCitation={onCitation} /></h4>;
    if (line.startsWith("## ")) return <h3 key={index}><Inline text={line.slice(3)} citations={citations} onCitation={onCitation} /></h3>;
    if (line.startsWith("# ")) return <h2 key={index}><Inline text={line.slice(2)} citations={citations} onCitation={onCitation} /></h2>;
    if (line.startsWith("- ")) return <div className="bullet" key={index}><span>—</span><p><Inline text={line.slice(2)} citations={citations} onCitation={onCitation} /></p></div>;
    if (!line.trim()) return <div className="spacer-line" key={index} />;
    return <p key={index}><Inline text={line} citations={citations} onCitation={onCitation} /></p>;
  })}</div>;
}
