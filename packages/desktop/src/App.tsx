import { useEffect, useState, type FormEvent } from "react";
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
  type Answer,
  type Face,
  type MemoryDetail,
  type MemoryItem,
} from "./api";

type Tab = "twin" | "memory" | "activity";

export default function App() {
  const [tab, setTab] = useState<Tab>("twin");
  const [settings, setSettings] = useState(false);
  const [base, setBase] = useState(localStorage.getItem("shellBase") || "http://127.0.0.1:8787");
  const [token, setToken] = useState(localStorage.getItem("shellToken") || "");
  const [status, setStatus] = useState("正在连接…");
  const [faces, setFaces] = useState<Face[]>([]);
  const [faceId, setFaceId] = useState("self");
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [query, setQuery] = useState("");
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [detail, setDetail] = useState<MemoryDetail | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [error, setError] = useState("");
  const [syncServer, setSyncServer] = useState("http://127.0.0.1:8790");
  const [pairCode, setPairCode] = useState("");
  const [pairing, setPairing] = useState("");
  const [syncMsg, setSyncMsg] = useState("");

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
    (async () => {
      const cfg = await loadShellConfig();
      if (gone) return;
      setBase(localStorage.getItem("shellBase") || base);
      setToken(localStorage.getItem("shellToken") || "");
      if (!cfg.ready) setSettings(true);
      setStatus(cfg.detail);
      if (localStorage.getItem("shellToken")) await refresh("twin");
      else setStatus(cfg.detail || "需要填写令牌");
    })();
    return () => {
      gone = true;
    };
    // First connection only. Later refreshes follow the visible tab.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (localStorage.getItem("shellToken")) void refresh(tab);
    // query is submitted explicitly so typing does not refetch every keystroke
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function send() {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setError("");
    try {
      setAnswer(await askTwin(q, faceId));
    } catch {
      setError("暂时连不上。请检查设置里的地址和令牌。");
    } finally {
      setAsking(false);
    }
  }

  function saveSettings(event: FormEvent) {
    event.preventDefault();
    localStorage.setItem("shellBase", base.trim() || "http://127.0.0.1:8787");
    localStorage.setItem("shellToken", token.trim());
    setSettings(false);
    void refresh(tab);
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
          <label htmlFor="question">问题</label>
          <textarea
            id="question"
            value={question}
            placeholder="问问你的分身"
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void send();
            }}
          />
          <p><button className="primary" type="button" disabled={asking || !question.trim()} onClick={() => void send()}>{asking ? "正在回答…" : "发送"}</button></p>
          {answer && (
            <article className="card">
              <p>{answer.answer}</p>
              {answer.citations?.length ? (
                <>
                  <h3 className="meta">依据</h3>
                  <ul className="list">
                    {answer.citations.map((c) => (
                      <li key={c.id}>[{c.n}] {c.title}<div className="meta">{c.snippet}</div></li>
                    ))}
                  </ul>
                </>
              ) : null}
              <p className="disclosure">{answer.disclosure}</p>
            </article>
          )}
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
            <p className="meta">第一次使用时填写本机服务的地址和令牌。</p>
            <label htmlFor="base">服务地址</label>
            <input id="base" type="text" value={base} onChange={(e) => setBase(e.target.value)} autoComplete="off" autoFocus />
            <label htmlFor="token">令牌</label>
            <input id="token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
            <h3>同步：配对码</h3>
            <label htmlFor="sync-server">同步服务</label>
            <input id="sync-server" type="text" value={syncServer} onChange={(e) => setSyncServer(e.target.value)} autoComplete="off" />
            <div className="actions">
              <button type="button" className="gear" onClick={() => void pairSync(syncServer).then((r) => {
                setPairCode(r.pair_code);
                setPairing(r.pairing);
                setSyncMsg("");
              }).catch(() => setSyncMsg("同步服务没有连上"))}>生成配对码</button>
              <button type="button" className="gear" onClick={() => void runSync().then((r) => {
                setSyncMsg(`已同步。冲突 ${r.pull.conflicts.length} 条`);
              }).catch(() => setSyncMsg("同步服务没有连上"))}>同步一次</button>
            </div>
            {pairCode ? <p>配对码 {pairCode}</p> : null}
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
