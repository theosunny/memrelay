import { decryptBlob, encryptBlob } from "./fernet.mjs";

export type Session = { server: string; vaultId: string; key: string; token: string };
export type Answer = { answer?: string; disclosure?: string; citations?: { n: number; title: string; snippet: string }[]; face_id?: string };

const te = new TextEncoder();
const td = new TextDecoder();

export function parsePairing(raw: string): { vaultId: string; code: string; key: string } {
  const parts = raw.trim().split(".");
  if (parts.length !== 4 || parts[0] !== "mr1") throw new Error("配对内容不对");
  return { vaultId: parts[1], code: parts[2], key: parts[3] };
}

async function call(session: Session, path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (session.token) headers.set("Authorization", `Bearer ${session.token}`);
  return fetch(`${session.server}${path}`, { ...init, headers });
}

export async function join(server: string, pairing: string): Promise<Session> {
  const parsed = parsePairing(pairing);
  const res = await fetch(`${server.replace(/\/$/, "")}/pair/finish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pair_code: parsed.code, device_pubkey: "phone" }),
  });
  if (!res.ok) throw new Error("配对没有成功");
  const body = await res.json();
  const session = { server: server.replace(/\/$/, ""), vaultId: parsed.vaultId, key: parsed.key, token: body.device_token };
  localStorage.setItem("mobileSession", JSON.stringify(session));
  return session;
}

export function loadSession(): Session | null {
  const raw = localStorage.getItem("mobileSession");
  return raw ? JSON.parse(raw) as Session : null;
}

export async function pullFiles(session: Session): Promise<Record<string, string>> {
  const listed = await call(session, `/v1/blobs/${session.vaultId}`);
  if (!listed.ok) throw new Error("同步没有成功");
  const files: Record<string, string> = {};
  for (const item of (await listed.json()).blobs as { path_hash: string }[]) {
    const res = await call(session, `/v1/blobs/${session.vaultId}/${item.path_hash}`);
    if (!res.ok) continue;
    const token = td.decode(new Uint8Array(await res.arrayBuffer()));
    let obj: { path: string; body: string };
    try {
      obj = JSON.parse(td.decode(await decryptBlob(session.key, token))) as { path: string; body: string };
    } catch {
      throw new Error("同步没有成功");
    }
    files[obj.path] = obj.body;
  }
  localStorage.setItem("mobileFiles", JSON.stringify(files));
  return files;
}

export function loadFiles(): Record<string, string> {
  const raw = localStorage.getItem("mobileFiles");
  return raw ? JSON.parse(raw) as Record<string, string> : {};
}

export async function askDesktop(session: Session, question: string, faceId: string): Promise<Answer> {
  const token = await encryptBlob(session.key, te.encode(JSON.stringify({ question, face_id: faceId })));
  const created = await call(session, `/v1/relay/${session.vaultId}`, {
    method: "POST",
    body: token,
  });
  if (!created.ok) throw new Error("暂时连不上");
  const id = (await created.json()).id as string;
  for (let i = 0; i < 20; i++) {
    const ans = await call(session, `/v1/relay/${session.vaultId}/${id}/answer`);
    if (ans.status === 200) {
      return JSON.parse(td.decode(await decryptBlob(session.key, td.decode(new Uint8Array(await ans.arrayBuffer()))))) as Answer;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("电脑不在线，先看看记忆");
}
