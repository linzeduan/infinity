import type { ChatMeta, DashboardData, Prediction, SearchResult } from "./types";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => json<DashboardData>("/api/dashboard"),
  refreshIndex: () => json<Record<string, unknown>>("/api/index/refresh", { method: "POST" }),
  refreshMacro: () => json<Record<string, unknown>>("/api/macro/refresh", { method: "POST" }),
  search: (query: string, kind?: string) =>
    json<{ count: number; items: SearchResult[] }>(
      `/api/search?q=${encodeURIComponent(query)}${kind ? `&document_kind=${kind}` : ""}`,
    ),
  predictions: (status?: string) =>
    json<{ count: number; items: Prediction[] }>(
      `/api/predictions${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  document: (id: number) => json<Record<string, unknown>>(`/api/documents/${id}`),
};

export interface ChatCallbacks {
  onMeta: (meta: ChatMeta) => void;
  onDelta: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export async function streamChat(
  payload: { query: string; mode: string },
  callbacks: ChatCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(await response.text());
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (event === "meta") callbacks.onMeta(parsed as ChatMeta);
      if (event === "delta") callbacks.onDelta(String(parsed.content || ""));
      if (event === "done") callbacks.onDone();
      if (event === "error") callbacks.onError(String(parsed.message || "未知错误"));
    }
    if (done) break;
  }
}
