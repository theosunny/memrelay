// shortcut: screens stay in this package; extract packages/shell-ui when a third client needs them
import { useState, type FormEvent } from "react";
import { askDesktop, join, loadFiles, loadSession, pullFiles, type Answer } from "./sync";

type Face = { id: string; name: string };

function facesOf(files: Record<string, string>): Face[] {
  const out: Face[] = [];
  for (const [path, body] of Object.entries(files)) {
    if (!path.startsWith(".memrelay/faces/") || !path.endsWith(".toml")) continue;
    const id = path.split("/").pop()?.replace(/\.toml$/, "") || "";
    const name = /name\s*=\s*"([^"]*)"/.exec(body)?.[1] || id;
    out.push({ id, name });
  }
  return out.length ? out : [{ id: "self", name: "自我" }];
}

function memoriesOf(files: Record<string, string>) {
  return Object.entries(files)
    .filter(([path]) => path.endsWith(".md") && !path.startsWith("."))
    .map(([path, body]) => ({
      path,
      title: path.split("/").pop()?.replace(/\.md$/, "") || path,
      snippet: body.replace(/\s+/g, " ").slice(0, 120),
      body,
    }));
}

export default function App() {
  const [tab, setTab] = useState<"twin" | "memory">("twin");
  const [settings, setSettings] = useState(!loadSession());
  const [server, setServer] = useState(loadSession()?.server || "http://127.0.0.1:8790");
  const [pairing, setPairing] = useState("");
  const [files, setFiles] = useState(loadFiles());
  const [faceId, setFaceId] = useState("self");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [open, setOpen] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function pair(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await join(server, pairing);
      setSettings(false);
      setFiles(await pullFiles(loadSession()!));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "配对没有成功");
    }
  }

  async function refresh() {
    const session = loadSession();
    if (!session) { setSettings(true); return; }
    setBusy(true);
    setError("");
    try {
      setFiles(await pullFiles(session));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "同步没有成功");
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    const session = loadSession();
    const q = question.trim();
    if (!session || !q) return;
    setBusy(true);
    setError("");
    try {
      setAnswer(await askDesktop(session, q, faceId));
    } catch (ex) {
      setAnswer(null);
      setError(ex instanceof Error ? ex.message : "电脑不在线，先看看记忆");
    } finally {
      setBusy(false);
    }
  }

  const faces = facesOf(files);
  const memories = memoriesOf(files);

  return (
    <div className="app">
      <header>
        <h1>忆桥分身</h1>
        <button className="gear" type="button" onClick={() => setSettings(true)}>设置</button>
      </header>
      <nav aria-label="主导航">
        <button type="button" aria-current={tab === "twin" ? "page" : undefined} onClick={() => setTab("twin")}>分身</button>
        <button type="button" aria-current={tab === "memory" ? "page" : undefined} onClick={() => setTab("memory")}>记忆</button>
      </nav>
      {error ? <p className="error" role="alert">{error}</p> : null}

      {tab === "twin" && (
        <section>
          <label htmlFor="face">当前的面</label>
          <select id="face" value={faceId} onChange={(e) => setFaceId(e.target.value)}>
            {faces.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
          <label htmlFor="question">问题</label>
          <textarea id="question" value={question} placeholder="问问你的分身" onChange={(e) => setQuestion(e.target.value)} />
          <p><button className="primary" type="button" disabled={busy || !question.trim()} onClick={() => void send()}>{busy ? "正在回答…" : "发送"}</button></p>
          {answer && (
            <article className="card">
              <p>{answer.answer}</p>
              {answer.citations?.length ? (
                <ul>{answer.citations.map((c) => <li key={c.n}>[{c.n}] {c.title}<div className="meta">{c.snippet}</div></li>)}</ul>
              ) : null}
              <p className="disclosure">{answer.disclosure}</p>
            </article>
          )}
        </section>
      )}

      {tab === "memory" && (
        <section>
          <p><button className="primary" type="button" onClick={() => void refresh()}>{busy ? "正在同步…" : "同步"}</button></p>
          {memories.length === 0 ? <p className="meta">还没有记忆。先同步一次。</p> : (
            <ul className="list">
              {memories.map((m) => (
                <li key={m.path}>
                  <button type="button" onClick={() => setOpen(m.path)}>
                    <strong>{m.title}</strong>
                    <div className="meta">{m.snippet}</div>
                  </button>
                  {open === m.path ? <pre className="card">{m.body}</pre> : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {settings && (
        <div className="dialog">
          <form role="dialog" aria-modal="true" aria-labelledby="settings-title" onSubmit={(e) => void pair(e)}>
            <h2 id="settings-title">配对</h2>
            <p className="meta">用相机扫描电脑上的二维码，或把配对内容粘贴到这里。电脑在线时才能提问；不在线时仍可看已经同步的记忆。</p>
            <label htmlFor="server">同步服务</label>
            <input id="server" value={server} onChange={(e) => setServer(e.target.value)} autoComplete="off" />
            <label htmlFor="pairing">配对内容</label>
            <textarea id="pairing" value={pairing} onChange={(e) => setPairing(e.target.value)} />
            <div className="actions">
              <button type="button" className="gear" onClick={() => setSettings(false)}>关闭</button>
              <button type="submit" className="primary">配对</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
