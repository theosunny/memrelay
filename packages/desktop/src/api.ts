export type Face = { id: string; name: string; kind: string; visibility_ceiling: string };

export type Citation = { n: number; id: string; title: string; snippet: string };

export type Answer = {
  answer: string;
  citations: Citation[];
  disclosure: string;
  confidence: number;
  refused: boolean;
  face_id: string | null;
};

export type MemoryItem = { id: string; title: string; type: string; snippet: string; status: string };

export type MemoryDetail = MemoryItem & {
  body?: string;
  confidence?: number;
  visibility?: string;
  source_agent?: string;
};

export type Activity = { digest: string; items: { ts?: string; title?: string; dest?: string }[] };

const base = () => localStorage.getItem("shellBase") || "http://127.0.0.1:8787";
const token = () => localStorage.getItem("shellToken") || "";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token()}`);
  headers.set("Content-Type", "application/json");
  const r = await fetch(`${base()}${path}`, { ...init, headers });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const getFaces = () => api<{ faces: Face[] }>("/v1/faces");
export const askTwin = (question: string, face_id = "self") =>
  api<Answer>("/v1/twin/ask", { method: "POST", body: JSON.stringify({ question, face_id }) });
export const listMemories = (q = "") =>
  api<{ items: MemoryItem[] }>(`/v1/memories?q=${encodeURIComponent(q)}`);
export const getMemory = (id: string) => api<MemoryDetail>(`/v1/memories/${id.split("/").map(encodeURIComponent).join("/")}`);
export const getActivity = () => api<Activity>("/v1/activity");

// shortcut: no JS test runner in this package, add a client test when one already exists
export async function loadShellConfig(): Promise<{ ready: boolean; detail: string }> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const cfg = await invoke<{ base: string; token: string; ready: boolean; detail: string }>("shell_config");
    if (cfg.base) localStorage.setItem("shellBase", cfg.base);
    if (cfg.token) localStorage.setItem("shellToken", cfg.token);
    return { ready: cfg.ready, detail: cfg.detail || "" };
  } catch {
    return { ready: Boolean(token()), detail: token() ? "" : "需要填写令牌" };
  }
}
