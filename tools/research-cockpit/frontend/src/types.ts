export type ExtractionStatus = "ok" | "suspect" | "unsupported" | "error";

export interface Citation {
  id: string;
  document_id: number;
  path: string;
  title: string;
  heading?: string | null;
  page?: number | null;
  line_start?: number | null;
  line_end?: number | null;
  snippet: string;
  extraction_status: ExtractionStatus;
  cloud_allowed: boolean;
}

export interface SearchResult extends Citation {
  source: string;
  document_kind: "knowledge" | "source";
  score: number;
  modified_at: string;
  restriction_reason?: string | null;
}

export interface Prediction {
  number: number;
  recorded_at: string;
  source: string;
  claim: string;
  verification: string;
  deadline_raw: string;
  deadline: string | null;
  deadline_precision: string;
  result: string;
  status: "pending" | "hit" | "miss" | "partial" | "unknown";
  origin: string;
}

export interface DashboardData {
  generated_at: string;
  health: {
    source_files: number;
    knowledge_markdown: number;
    indexed_documents: number;
    indexed_chunks: number;
    ledger_rows: number;
    latest_ledger: number;
    prediction_rows: number;
    latest_prediction: number;
    navigation_warnings: string[];
    git_dirty: boolean;
    git_changes: string[];
    extraction: Record<string, number>;
  };
  changes: {
    unprocessed: string[];
    missing_or_moved: string[];
    recent: Array<{
      id: number;
      path: string;
      title: string;
      source: string;
      document_kind: string;
      extraction_status: ExtractionStatus;
      modified_at: string;
    }>;
  };
  prediction_queue: {
    overdue: Prediction[];
    due_soon: Prediction[];
    recently_resolved: Prediction[];
    source_stats: Array<Record<string, string | number>>;
  };
  models: Array<{
    source: string;
    has_model: boolean;
    last_model: string | null;
    articles_since_model: number;
    threshold: number;
    remaining: number;
    due: boolean;
    warnings: string[];
  }>;
  macro: {
    available: boolean;
    generated: string | null;
    warnings: Array<{ key: string; status: string; reason: string }>;
    errors: string[];
  };
}

export interface ChatMeta {
  citations: Citation[];
  local_only_citations: Citation[];
  coverage_warnings: string[];
  cloud_usage: {
    provider: string | null;
    sent_chunks: number;
    blocked_chunks: number;
  };
}
