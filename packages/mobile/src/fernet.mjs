// Fernet (AES-128-CBC + HMAC-SHA256), same tokens as cryptography.fernet.

function b64urlToBytes(s) {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function bytesToB64url(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_");
}

function concat(parts) {
  const n = parts.reduce((sum, p) => sum + p.length, 0);
  const out = new Uint8Array(n);
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

async function keys(keyB64) {
  const raw = b64urlToBytes(keyB64);
  const signing = await crypto.subtle.importKey("raw", raw.slice(0, 16), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
  const encryption = await crypto.subtle.importKey("raw", raw.slice(16), { name: "AES-CBC" }, false, ["encrypt", "decrypt"]);
  return { signing, encryption };
}

export async function encryptBlob(keyB64, plaintext) {
  const { signing, encryption } = await keys(keyB64);
  const iv = crypto.getRandomValues(new Uint8Array(16));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-CBC", iv }, encryption, plaintext));
  const ts = new Uint8Array(8);
  new DataView(ts.buffer).setUint32(4, Math.floor(Date.now() / 1000));
  const signed = concat([new Uint8Array([0x80]), ts, iv, ct]);
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", signing, signed));
  return bytesToB64url(concat([signed, mac]));
}

export async function decryptBlob(keyB64, token) {
  const { signing, encryption } = await keys(keyB64);
  const data = b64urlToBytes(token);
  if (data[0] !== 0x80 || data.length < 57) throw new Error("bad blob");
  const signed = data.slice(0, data.length - 32);
  const mac = data.slice(data.length - 32);
  const ok = await crypto.subtle.verify("HMAC", signing, mac, signed);
  if (!ok) throw new Error("bad blob");
  const iv = signed.slice(9, 25);
  const ct = signed.slice(25);
  return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-CBC", iv }, encryption, ct));
}
