import { useEffect, useState, type FormEvent } from "react";
import { invoke } from "@tauri-apps/api/core";
import QRCode from "qrcode";
import urls from "../../website/urls.json";
import { ModelGate, type ModelSave } from "./ModelGate";
import { ChatThread } from "./ChatThread";
import { failTwin, finishTwin, markPending, parseTranscript, pushUser, serializeTranscript, type ChatMessage } from "./chat";
import {
  askTwin,
  getActivity,
  getFaces,
  getMemory,
  listMemories,
  loadShellConfig,
  pairSync,
  runSync,
  type Activity,
  type Face,
  type MemoryDetail,
  type MemoryItem,
} from "./api";

type Tab = "twin" | "memory" | "activity";

const LOCAL_SYNC = "http://127.0.0.1:8790";
type Gate = "loading" | "needed" | "ready";

function initialSync(): string {
  const saved = localStorage.getItem("syncServer");
  if (saved === null) return urls.sync;
  return saved.trim() || LOCAL_SYNC;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("twin");
  const [settings, setSettings] = useState(false);
  const [base, setBase] = useState(localStorage.getItem("shellBase") || "http://127.0.0.1:8787");
  const [token, setToken] = useState(localStorage.getItem("shellToken") || "");
  const [status, setStatus] = useState("正在连接…");
  const [faces, setFaces] = useState<Face[]>([]);
  const [faceId, setFaceId] = useState("self");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState(false);
  const [query, setQuery] = useState("");
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [detail, setDetail] = useState<MemoryDetail | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [error, setError] = useState("");
  const [syncServer, setSyncServer] = useState(initialSync);
  const [pairCode, setPairCode] = useState("");
  const [pairing, setPairing] = useState("");
  const [qr, setQr] = useState("");
  const [syncMsg, setSyncMsg] = useState("");
  const [gate, setGate] = useState<Gate>("loading");
  const [gateError, setGateError] = useState("");

  useEffect(() => {
    if (!pairing) { setQr(""); return; }
    let gone = false;
    void QRCode.toDataURL(pairing, { margin: 1, width: 192 }).then((url) => {
      if (!gone) setQr(url);
    }).catch(() => { if (!gone) setQr(""); });
    return () => { gone = true; };
  }, [pairing]);

  async function refresh(which: Tab = tab) {
    setError("");
    try {
      if (which === "twin") {
        const res = await getFaces();
        setFaces(res.faces);
        if (!res.faces.some((f) => f.id === faceId) && res.faces[0]) setFaceId(res.faces[0].id);
      } else if (which === "memory") {
        setMemories((await listMemories(query)).items);
        setDetail(null);
      } else {
        setActivity(await getActivity());
      }
      setStatus("");
    } catch {
      setError("暂时连不上。请检查设置里的地址和令牌。");
    }
  }

  useEffect(() => {
    let gone = false;
    void invoke<{ configured: boolean }>("model_status")
      .then((status) => {
        if (!gone) setGate(status.configured ? "ready" : "needed");
      })
      .catch(() => {
        if (!gone) setGate("needed");
      });
    return () => {
      gone = true;
    };
  }, []);

  useEffect(() => {
    if (gate !== "ready") return;
    let gone = false;
    (async () => {
      const cfg = await loadShellConfig();
      if (gone) return;
      setBase(localStorage.getItem("shellBase") || base);
      setToken(localStorage.getItem("shellToken") || "");
      setStatus(cfg.detail);
      try {
        const raw = await invoke<string>("read_transcript");
        if (!gone) setMessages(parseTranscript(raw));
      } catch {
        if (!gone) setMessages([]);
      }
      if (localStorage.getItem("shellToken")) await refresh("twin");
      else setStatus(cfg.detail || "需要填写令牌");
    })();
    return () => {
      gone = true;
    };
    // First connection only. Later refreshes follow the visible tab.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gate]);

  async function saveModel(input: ModelSave) {
    setGateError("");
    try {
      await invoke("save_model", {
        provider: input.provider,
        apiKey: input.apiKey,
        model: input.model,
      });
    } catch (err) {
      const text = typeof err === "string" ? err : "没有保存";
      setGateError(input.apiKey && text.includes(input.apiKey) ? "没有保存" : text);
      return;
    }
    setGate("ready");
  }

  useEffect(() => {
    if (gate !== "ready") return;
    if (localStorage.getItem("shellToken")) void refresh(tab);
    // query is submitted explicitly so typing does not refetch every keystroke
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, gate]);

  async function persist(next: ChatMessage[]) {
    try {
      await invoke("write_transcript", { body: serializeTranscript(next) });
    } catch {
      // The thread stays on screen. A failed write does not show a path.
    }
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q || asking) return;
    setAsking(true);
    setDraft("");
    setError("");
    const pending = markPending(pushUser(messages, q));
    setMessages(pending);
    try {
      const done = finishTwin(pending, await askTwin(q, faceId));
      setMessages(done);
      await persist(done);
    } catch {
      const failed = failTwin(pending);
      setMessages(failed);
      await persist(failed);
    } finally {
      setAsking(false);
    }
  }

  function saveSettings(event: FormEvent) {
    event.preventDefault();
    localStorage.setItem("shellBase", base.trim() || "http://127.0.0.1:8787");
    localStorage.setItem("shellToken", token.trim());
    const chosen = syncServer.trim() || LOCAL_SYNC;
    setSyncServer(chosen);
    localStorage.setItem("syncServer", chosen);
    setSettings(false);
    void refresh(tab);
  }

  if (gate !== "ready") {
    return (
      <div className="app">
        {gate === "needed" ? (
          <>
            <ModelGate onSave={(input) => { void saveModel(input); }} />
            {gateError ? <p className="error" role="alert">{gateError}</p> : null}
          </>
        ) : (
          <p className="meta">正在连接…</p>
        )}
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <h1>忆桥分身</h1>
        <button className="gear" type="button" onClick={() => setSettings(true)}>设置</button>
      </header>
      <nav aria-label="主导航">
        {(["twin", "memory", "activity"] as const).map((id) => (
          <button key={id} type="button" aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>
            {id === "twin" ? "分身" : id === "memory" ? "记忆" : "动态"}
          </button>
        ))}
      </nav>
      {status && !error ? <p className="meta">{status}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}

      {tab === "twin" && (
        <section aria-labelledby="twin-title">
          <h2 id="twin-title" className="meta">分身</h2>
          <label htmlFor="face">当前的面</label>
          <select id="face" value={faceId} onChange={(e) => setFaceId(e.target.value)}>
            {(faces.length ? faces : [{ id: "self", name: "自我", kind: "expression", visibility_ceiling: "private" }]).map((f) => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
          <ChatThread messages={messages} draft={draft} onDraft={setDraft} onSend={(text) => { void send(text); }} disabled={asking} />
        </section>
      )}

      {tab === "memory" && (
        <section aria-labelledby="memory-title">
          <h2 id="memory-title" className="meta">记忆</h2>
          <form onSubmit={(e) => { e.preventDefault(); void refresh("memory"); }}>
            <label htmlFor="q">搜索</label>
            <div className="row">
              <input id="q" type="text" value={query} placeholder="搜索记忆" onChange={(e) => setQuery(e.target.value)} />
              <button className="primary" type="submit">搜索</button>
            </div>
          </form>
          {/* shortcut: no timeline or type filter yet, add them when a long vault is hard to scan */}
          {memories.length === 0 ? <p className="meta">没有找到记忆。</p> : (
            <ul className="list">
              {memories.map((m) => (
                <li key={m.id}>
                  <button type="button" onClick={() => void getMemory(m.id).then(setDetail).catch(() => setError("暂时连不上。请检查设置里的地址和令牌。"))}>
                    <strong>{m.title}</strong> <span className="meta">{m.type}</span>
                    <div className="meta">{m.snippet}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {detail && (
            <article className="card">
              <h3>{detail.title}</h3>
              <p className="meta">{detail.type} · {detail.visibility || ""} · {detail.source_agent || ""}</p>
              <pre>{detail.body}</pre>
            </article>
          )}
        </section>
      )}

      {tab === "activity" && (
        <section aria-labelledby="activity-title">
          <h2 id="activity-title" className="meta">动态</h2>
          <article className="card"><pre>{activity?.digest || "过去几天没有自动写入的记忆。"}</pre></article>
          {activity?.conflicts?.length ? (
            <article className="card">
              <h3>需要你看一眼</h3>
              <ul>{activity.conflicts.map((c) => <li key={c}>{c}</li>)}</ul>
            </article>
          ) : null}
        </section>
      )}

      {settings && (
        <div className="dialog" role="presentation">
          <form role="dialog" aria-modal="true" aria-labelledby="settings-title" onSubmit={saveSettings}
            onKeyDown={(e) => {
              if (e.key === "Escape") { setSettings(false); return; }
              if (e.key !== "Tab") return;
              const items = [...e.currentTarget.querySelectorAll<HTMLElement>("input, textarea, button")].filter((el) => !el.hasAttribute("disabled"));
              const first = items[0];
              const last = items[items.length - 1];
              if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
              else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
            }}>
            <h2 id="settings-title">设置</h2>
            {status ? <p role="status">{status}</p> : <p className="meta">第一次使用时填写本机服务的地址和令牌。</p>}
            <label htmlFor="base">服务地址</label>
            <input id="base" type="text" value={base} onChange={(e) => setBase(e.target.value)} autoComplete="off" autoFocus />
            <label htmlFor="token">令牌</label>
            <input id="token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
            <h3>同步：配对码</h3>
            <label htmlFor="sync-server">同步服务</label>
            <input id="sync-server" type="text" value={syncServer} onChange={(e) => setSyncServer(e.target.value)} autoComplete="off" />
            <p className="meta">官方同步地址，部署后再生效。本机则填 http://127.0.0.1:8790。改地址后重新生成配对码。钥匙只留在设备上。</p>
            <div className="actions">
              <button type="button" className="gear" onClick={() => { setSyncServer(LOCAL_SYNC); localStorage.setItem("syncServer", LOCAL_SYNC); }}>使用本机</button>
              <button type="button" className="gear" onClick={() => {
                const chosen = syncServer.trim() || LOCAL_SYNC;
                setSyncServer(chosen);
                localStorage.setItem("syncServer", chosen);
                void pairSync(chosen).then((r) => {
                  setPairCode(r.pair_code);
                  setPairing(r.pairing);
                  setSyncMsg("");
                }).catch(() => setSyncMsg("同步服务没有连上"));
              }}>生成配对码</button>
              <button type="button" className="gear" onClick={() => void runSync().then((r) => {
                setSyncMsg(`已同步。冲突 ${r.pull.conflicts.length} 条`);
              }).catch(() => setSyncMsg("同步服务没有连上"))}>同步一次</button>
            </div>
            {pairCode ? <p>配对码 {pairCode}</p> : null}
            {qr ? <img className="qr" alt="配对二维码" src={qr} width={192} height={192} /> : null}
            {qr ? <p className="meta">用手机相机扫描。扫不到就粘贴下面的文字。</p> : null}
            {pairing ? <textarea readOnly value={pairing} aria-label="配对内容" /> : null}
            {syncMsg ? <p className="meta">{syncMsg}</p> : null}
            <div className="actions">
              <button type="button" className="gear" onClick={() => setSettings(false)}>关闭</button>
              <button type="submit" className="primary">保存</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
