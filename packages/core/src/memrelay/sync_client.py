"""Push and pull encrypted vault files. The sync server only sees ciphertext.

State (key, token, cursor) stays in the data dir, which is never uploaded.
Desktop is the writer. A phone pulls and asks through the relay.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

import httpx

from .config import data_dir
from .sync_crypto import decrypt_blob, encrypt_blob, generate_vault_key
from .vault import HIDDEN_FOLDERS, Vault

_SERVER = "http://127.0.0.1:8790"


def _state_path() -> Path:
    return data_dir() / "sync" / "state.json"


def load_state() -> dict:
    path = _state_path()
    if not path.is_file():
        return {"server": _SERVER, "vault_id": "", "key": "", "token": "", "role": "desktop", "cursor": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def public_status() -> dict:
    state = load_state()
    return {
        "server": state.get("server") or _SERVER,
        "paired": bool(state.get("token") and state.get("key")),
        "vault_id": state.get("vault_id") or "",
        "role": state.get("role") or "desktop",
    }


def syncable(rel: str) -> bool:
    parts = tuple(p for p in rel.split("/") if p != "")
    if not parts or ".." in parts or rel.startswith("/") or "\\" in rel:
        return False
    if parts[0] == ".memrelay":
        return len(parts) >= 3 and parts[1] == "faces" and parts[-1].endswith(".toml")
    if parts[0] in HIDDEN_FOLDERS or parts[0].startswith("."):
        return False
    return parts[-1].endswith(".md")


def iter_sync_paths(vault: Vault) -> list[str]:
    out = []
    if not vault.root.is_dir():
        return out
    for path in sorted(vault.root.rglob("*")):
        if path.is_file() and syncable(vault.rel(path)):
            out.append(vault.rel(path))
    return out


def _key(state: dict) -> bytes:
    return state["key"].encode("ascii")


def _auth(state: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {state['token']}"}


def _open(state: dict, client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    return httpx.Client(base_url=state["server"].rstrip("/"), timeout=30), True


def _path_hash(rel: str) -> str:
    return hashlib.sha256(rel.encode()).hexdigest()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pack(rel: str, body: bytes) -> bytes:
    return json.dumps({"path": rel, "body": body.decode("utf-8")}, ensure_ascii=False).encode()


def _write(vault: Vault, rel: str, body: bytes) -> None:
    if not syncable(rel):
        raise ValueError(rel)
    dest = (vault.root / rel).resolve()
    dest.relative_to(vault.root.resolve())
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)


def _write_conflict(vault: Vault, rel: str, body: bytes) -> None:
    dest = (vault.root / ".memrelay" / "conflicts" / rel).resolve()
    dest.relative_to((vault.root / ".memrelay" / "conflicts").resolve())
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)


def pair_desktop(vault: Vault, server: str, client: httpx.Client | None = None) -> dict:
    """Create a vault key if needed, register this desktop, return the phone pairing string."""
    del vault  # the key is per device data dir, not a vault file
    state = load_state()
    state["server"] = server.rstrip("/")
    state["role"] = "desktop"
    if not state.get("key"):
        state["key"] = generate_vault_key().decode("ascii")
    if not state.get("vault_id"):
        state["vault_id"] = secrets.token_hex(16)
    http, owned = _open(state, client)
    try:
        started = http.post("/pair/start", json={"vault_id": state["vault_id"]})
        started.raise_for_status()
        code = started.json()["pair_code"]
        fin = http.post("/pair/finish", json={"pair_code": code, "device_pubkey": "desktop"})
        fin.raise_for_status()
        state["token"] = fin.json()["device_token"]
        save_state(state)
    finally:
        if owned:
            http.close()
    # shortcut: text payload stands in for a QR image, draw a QR when a library is already installed
    pairing = f"mr1.{state['vault_id']}.{code}.{state['key']}"
    return {"pair_code": code, "pairing": pairing, "vault_id": state["vault_id"]}


def pair_phone(pairing: str, server: str, client: httpx.Client | None = None) -> dict:
    parts = pairing.strip().split(".")
    if len(parts) != 4 or parts[0] != "mr1":
        raise ValueError("bad pairing")
    _, vault_id, code, key = parts
    state = {
        "server": server.rstrip("/"),
        "vault_id": vault_id,
        "key": key,
        "token": "",
        "role": "phone",
        "cursor": {},
    }
    http, owned = _open(state, client)
    try:
        fin = http.post("/pair/finish", json={"pair_code": code, "device_pubkey": "phone"})
        fin.raise_for_status()
        state["token"] = fin.json()["device_token"]
        save_state(state)
    finally:
        if owned:
            http.close()
    return {"vault_id": vault_id, "role": "phone"}


def push(vault: Vault, client: httpx.Client | None = None) -> dict:
    state = load_state()
    if state.get("role") == "phone":
        raise PermissionError("phone is browse-only")
    if not state.get("token"):
        raise RuntimeError("not paired")
    http, owned = _open(state, client)
    pushed = 0
    try:
        for rel in iter_sync_paths(vault):
            body = (vault.root / rel).read_bytes()
            digest = _sha(body)
            cur = state["cursor"].get(rel) or {}
            if cur.get("sha256") == digest:
                continue
            blob = encrypt_blob(_key(state), _pack(rel, body))
            res = http.put(
                f"/v1/blobs/{state['vault_id']}/{_path_hash(rel)}",
                content=blob,
                headers=_auth(state),
            )
            res.raise_for_status()
            state["cursor"][rel] = {"sha256": digest, "etag": res.json()["etag"]}
            pushed += 1
        save_state(state)
    finally:
        if owned:
            http.close()
    return {"pushed": pushed}


def pull(vault: Vault, client: httpx.Client | None = None) -> dict:
    state = load_state()
    if not state.get("token"):
        raise RuntimeError("not paired")
    http, owned = _open(state, client)
    pulled, conflicts = 0, []
    try:
        listed = http.get(f"/v1/blobs/{state['vault_id']}", headers=_auth(state))
        listed.raise_for_status()
        for item in listed.json()["blobs"]:
            rel_known = next((r for r, c in state["cursor"].items() if _path_hash(r) == item["path_hash"]), None)
            if rel_known and (state["cursor"][rel_known] or {}).get("etag") == item["etag"]:
                continue
            res = http.get(
                f"/v1/blobs/{state['vault_id']}/{item['path_hash']}",
                headers=_auth(state),
            )
            res.raise_for_status()
            obj = json.loads(decrypt_blob(_key(state), res.content))
            rel = str(obj["path"])
            if not syncable(rel):
                continue
            body = str(obj["body"]).encode("utf-8")
            local = vault.root / rel
            local_bytes = local.read_bytes() if local.is_file() else None
            cur = state["cursor"].get(rel) or {}
            if local_bytes is None or cur.get("sha256") == _sha(local_bytes):
                _write(vault, rel, body)
                state["cursor"][rel] = {"sha256": _sha(body), "etag": item["etag"]}
                pulled += 1
            elif local_bytes == body:
                state["cursor"][rel] = {"sha256": _sha(body), "etag": item["etag"]}
            else:
                _write_conflict(vault, rel, body)
                conflicts.append(rel)
        save_state(state)
    finally:
        if owned:
            http.close()
    return {"pulled": pulled, "conflicts": conflicts}


def _default_answer(vault: Vault, question: str, face_id: str) -> dict:
    import asyncio

    from .backends import make_backend
    from .config import Config
    from .llm import get_llm
    from .twin import answer_as_me

    cfg = Config.load()
    backend = make_backend(cfg, vault)

    async def run():
        await backend.start()
        try:
            return await answer_as_me(
                question, vault=vault, backend=backend, llm=get_llm(cfg), face_id=face_id,
            )
        finally:
            await backend.stop()

    return asyncio.run(run())


def relay_once(vault: Vault, *, answer=None, client: httpx.Client | None = None) -> int:
    state = load_state()
    if not state.get("token"):
        return 0
    http, owned = _open(state, client)
    done = 0
    try:
        pending = http.get(f"/v1/relay/{state['vault_id']}/pending", headers=_auth(state))
        pending.raise_for_status()
        for item in pending.json()["items"]:
            q = http.get(
                f"/v1/relay/{state['vault_id']}/{item['id']}/question",
                headers=_auth(state),
            )
            if q.status_code != 200:
                continue
            payload = json.loads(decrypt_blob(_key(state), q.content))
            fn = answer or _default_answer
            result = fn(vault, str(payload.get("question") or ""), str(payload.get("face_id") or "self"))
            blob = encrypt_blob(_key(state), json.dumps(result, ensure_ascii=False).encode())
            put = http.put(
                f"/v1/relay/{state['vault_id']}/{item['id']}/answer",
                content=blob,
                headers=_auth(state),
            )
            put.raise_for_status()
            done += 1
    finally:
        if owned:
            http.close()
    return done


def ask_remote(question: str, face_id: str = "self", *, client: httpx.Client | None = None,
               pump=None, tries: int = 20) -> dict:
    state = load_state()
    blob = encrypt_blob(_key(state), json.dumps({"question": question, "face_id": face_id}, ensure_ascii=False).encode())
    http, owned = _open(state, client)
    try:
        created = http.post(f"/v1/relay/{state['vault_id']}", content=blob, headers=_auth(state))
        created.raise_for_status()
        rid = created.json()["id"]
        for _ in range(tries):
            if pump:
                pump()
            ans = http.get(f"/v1/relay/{state['vault_id']}/{rid}/answer", headers=_auth(state))
            if ans.status_code == 200:
                return json.loads(decrypt_blob(_key(state), ans.content))
            if pump is None:
                time.sleep(0.25)
        raise TimeoutError("desktop offline")
    finally:
        if owned:
            http.close()


def relay_forever(vault: Vault, interval: float = 1.0) -> None:
    while True:
        try:
            relay_once(vault)
        except Exception:
            # shortcut: one bad question must not kill the desktop relay; log when a log sink exists
            pass
        time.sleep(interval)


def start_relay_thread(vault: Vault) -> None:
    threading.Thread(target=relay_forever, args=(vault,), daemon=True).start()


def conflict_paths(vault: Vault) -> list[str]:
    root = vault.root / ".memrelay" / "conflicts"
    if not root.is_dir():
        return []
    return [vault.rel(p) for p in sorted(root.rglob("*")) if p.is_file()]
