import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import QRCode from "qrcode";
import urls from "../../website/urls.json";
import { ModelGate, type ModelSave } from "./ModelGate";
import { ChatThread } from "./ChatThread";
import { SettingsDialog } from "./SettingsDialog";
import { failTwin, finishTwin, markPending, parseTranscript, pushUser, serializeTranscript, type ChatMessage } from "./chat";
import { COPY } from "./errors";
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
  const [localSync, setLocalSync] = useState(LOCAL_SYNC);
  const [version, setVersion] = useState("0.2.0");
  const [modelProvider, setModelProvider] = useState("deepseek");
  const [modelName, setModelName] = useState("");
  const [pairCode, setPairCode] = useState("");
  const [pairing, setPairing] = useState("");
  const [qr, setQr] = useState("");
  const [syncMsg, setSyncMsg] = useState("");
  const [gate, setGate] = useState<Gate>("loading");
  const [gateError, setGateError] = useState("");
  const [shellReady, setShellReady] = useState(true);

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
      setError(COPY.sidecarDown);
    }
  }

  async function absorbShell(cfg: { ready: boolean; detail: string }) {
    setBase(localStorage.getItem("shellBase") || base);
    setToken(localStorage.getItem("shellToken") || "");
    setShellReady(cfg.ready);
    if (!cfg.ready) {
      setError("");
      setStatus("");
      return;
    }
    setStatus(cfg.detail);
    try {
      const raw = await invoke<string>("read_transcript");
      setMessages(parseTranscript(raw));
    } catch {
      setMessages([]);
    }
    if (localStorage.getItem("shellToken")) await refresh("twin");
    else setStatus(cfg.detail || "需要填写令牌");
  }

  function retryShell() {
    void loadShellConfig().then((cfg) => absorbShell(cfg));
  }

  useEffect(() => {
    let gone = false;
    void invoke<{ configured: boolean; provider: string; model: string }>("model_status")
      .then((status) => {
        if (gone) return;
        if (status.provider) setModelProvider(status.provider);
        setModelName(status.model || "");
        setGate(status.configured ? "ready" : "needed");
      })
      .catch(() => {
        if (!gone) setGate("needed");
      });
    return () => {
      gone = true;
    };
  }, []);

  useEffect(() => {
    let gone = false;
    void import("@tauri-apps/api/app")
      .then((mod) => mod.getVersion())
      .then((value) => {
        if (!gone && value) setVersion(value);
      })
      .catch(() => {
        if (!gone) setVersion("0.2.0");
      });
    return () => {
      gone = true;
    };
  }, []);

  useEffect(() => {
    if (gate !== "ready") return;
    let gone = false;
    void loadShellConfig().then((cfg) => {
      if (!gone) return absorbShell(cfg);
    });
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
    if (gate !== "ready" || !shellReady) return;
    if (localStorage.getItem("shellToken")) void refresh(tab);
    // query is submitted explicitly so typing does not refetch every keystroke
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, gate, shellReady]);

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
      const failed = failTwin(pending, COPY.modelRejected);
      setMessages(failed);
      await persist(failed);
    } finally {
      setAsking(false);
    }
  }

  function closeSettings() {
    localStorage.setItem("shellBase", base.trim() || "http://127.0.0.1:8787");
    localStorage.setItem("shellToken", token.trim());
    const chosen = syncServer.trim() || initialSync();
    setSyncServer(chosen);
    localStorage.setItem("syncServer", chosen);
    setSettings(false);
    if (shellReady) void refresh(tab);
  }

  async function onSaveModel(input: { provider: string; apiKey: string; model: string }) {
    try {
      await invoke("save_model", input);
      setModelProvider(input.provider);
      setModelName(input.model);
      setSyncMsg("");
    } catch (err) {
      const text = typeof err === "string" ? err : "没有保存";
      const leaks = text.includes("8787") || text.includes("127.0.0.1:8787") || Boolean(input.apiKey && text.includes(input.apiKey));
      setSyncMsg(leaks ? "没有保存" : text);
    }
  }

  async function onPair() {
    const chosen = syncServer.trim() || initialSync();
    setSyncServer(chosen);
    localStorage.setItem("syncServer", chosen);
    try {
      const paired = await pairSync(chosen);
      setPairCode(paired.pair_code);
      setPairing(paired.pairing);
      setSyncMsg("");
    } catch {
      setSyncMsg(COPY.syncFailed);
      return;
    }
    try {
      await runSync();
    } catch {
      setSyncMsg(COPY.syncFailed);
    }
  }

  async function onUseLocal() {
    try {
      await invoke("use_local_sync");
      const chosen = localSync.trim() || LOCAL_SYNC;
      setLocalSync(chosen);
      setSyncServer(chosen);
      localStorage.setItem("syncServer", chosen);
      setSyncMsg("");
    } catch {
      setSyncMsg(COPY.sidecarDown);
    }
  }

  async function onSyncOnce() {
    try {
      await runSync();
      setSyncMsg("");
    } catch {
      setSyncMsg(COPY.syncFailed);
    }
  }

  async function onOpenData() {
    try {
      await invoke("open_data_dir");
      setSyncMsg("");
    } catch {
      setSyncMsg("没有打开数据目录");
    }
  }

  const distribution = (import.meta.env as { VITE_DISTRIBUTION?: string }).VITE_DISTRIBUTION === "notarized"
    ? "已公证"
    : "开发构建";

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
      {!shellReady ? <p role="status">{COPY.sidecarDown}</p> : null}
      {!shellReady ? <button type="button" onClick={retryShell}>{COPY.retry}</button> : null}
      {shellReady && status && !error ? <p className="meta">{status}</p> : null}
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
          <ChatThread
            messages={messages}
            draft={draft}
            onDraft={setDraft}
            onSend={(text) => { void send(text); }}
            disabled={asking}
            onOpenModel={() => setSettings(true)}
          />
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
          {memories.length === 0 ? <p className="meta">{query.trim() ? "没有找到记忆。" : COPY.memoryEmpty}</p> : (
            <ul className="list">
              {memories.map((m) => (
                <li key={m.id}>
                  <button type="button" onClick={() => void getMemory(m.id).then(setDetail).catch(() => setError(COPY.sidecarDown))}>
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
          <article className="card"><pre>{activity?.digest || COPY.activityEmpty}</pre></article>
          {activity?.conflicts?.length ? (
            <article className="card">
              <h3>需要你看一眼</h3>
              <ul>{activity.conflicts.map((c) => <li key={c}>{c}</li>)}</ul>
            </article>
          ) : null}
        </section>
      )}

      {settings && (
        <SettingsDialog
          version={version}
          distribution={distribution}
          provider={modelProvider}
          model={modelName}
          syncServer={syncServer}
          base={base}
          token={token}
          localSync={localSync}
          pairCode={pairCode}
          pairing={pairing}
          qr={qr}
          syncMsg={syncMsg}
          onClose={closeSettings}
          onSaveModel={(input) => { void onSaveModel(input); }}
          onPair={() => { void onPair(); }}
          onUseLocal={() => { void onUseLocal(); }}
          onSyncOnce={() => { void onSyncOnce(); }}
          onOpenData={() => { void onOpenData(); }}
          onBase={setBase}
          onToken={setToken}
          onLocalSync={setLocalSync}
        />
      )}
    </div>
  );
}
