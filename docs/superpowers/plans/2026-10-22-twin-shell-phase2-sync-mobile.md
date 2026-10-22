# Twin Shell Phase 2: E2E Sync + Mobile Ask/Browse

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Built-in end-to-end encrypted sync of vault + faces between desktop and phone; mobile app that can ask the twin and browse memories.

**Architecture:** Sync service stores only ciphertext blobs keyed by vault-id. Devices hold keys. Desktop remains primary writer for capture; mobile is ask+browse first. Conflict → `needs_attention` style conflict files under `.memrelay/conflicts/`. Depends on Phase 1 shell API + faces.

**Tech Stack:** Rust or Python sync server (prefer Python FastAPI in `packages/sync` for one language with core), libsodium/age for E2E, React Native or Tauri mobile (prefer **PWA + Capacitor** for speed unless native push is required—default Capacitor iOS/Android wrapping the same React UI package `packages/shell-ui`).

**Spec:** [2026-10-22-twin-product-shell-design.md](../specs/2026-10-22-twin-product-shell-design.md)  
**Prerequisite:** Phase 1 plan complete.

## Global Constraints

- Zero-knowledge: server cannot read memory plaintext.
- Sync vault files + `.memrelay/faces/*` only; never sync `data_dir()` capture cursors.
- Pairing via short code or QR; no forced email if pairing works.
- Mobile v1: 分身 + 记忆 only (no capture, no 动态 required).
- Same face ceilings enforced via shell API / engine.

## File map

| Path | Responsibility |
|------|----------------|
| `packages/sync/` | Sync server + protocol docs |
| `packages/sync/protocol.md` | Blob format, pairing, conflict rules |
| `packages/core/src/memrelay/sync_client.py` | Encrypt, push/pull, conflict detect |
| `packages/shell-ui/` | Shared React screens (optional extract from desktop) |
| `packages/mobile/` | Capacitor wrapper |

---

### Task 1: Sync protocol doc + blob format tests

**Files:**
- Create: `packages/sync/protocol.md`
- Create: `packages/core/src/memrelay/sync_crypto.py`
- Create: `packages/core/tests/test_sync_crypto.py`

**Interfaces:**
- Produces: `generate_vault_key() -> bytes`, `encrypt_blob(key, plaintext: bytes) -> bytes`, `decrypt_blob(key, blob: bytes) -> bytes`

- [ ] **Step 1: Write failing roundtrip test**

```python
from memrelay.sync_crypto import generate_vault_key, encrypt_blob, decrypt_blob

def test_encrypt_roundtrip():
    key = generate_vault_key()
    pt = b"# note\nhello 杭州"
    blob = encrypt_blob(key, pt)
    assert blob != pt
    assert decrypt_blob(key, blob) == pt
```

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Implement with `cryptography.Fernet` or `nacl.secret`** (add dependency explicitly in `packages/core/pyproject.toml`)

- [ ] **Step 4: Tests pass + commit**

```bash
git commit -s -m "feat(sync): E2E blob crypto helpers"
```

---

### Task 2: Sync server MVP

**Files:**
- Create: `packages/sync/pyproject.toml`, `packages/sync/src/memrelay_sync/app.py`
- Create: `packages/sync/tests/test_app.py`

**Interfaces:**
- `POST /pair/start` → `{pair_code, vault_id}`  
- `POST /pair/finish` `{pair_code, device_pubkey}` → `{device_token}`  
- `PUT /v1/blobs/{vault_id}/{path_hash}` Authorization device token; body ciphertext  
- `GET /v1/blobs/{vault_id}` → list of path_hash + etag  
- `GET /v1/blobs/{vault_id}/{path_hash}` → ciphertext  

Server stores opaque bytes only.

- [ ] **Step 1–5:** TDD list/put/get; commit `feat(sync): zero-knowledge blob server MVP`

---

### Task 3: Desktop sync client

**Files:**
- Create: `packages/core/src/memrelay/sync_client.py`
- Modify: desktop Settings → “同步：配对码”
- CLI: `memrelay sync push` / `memrelay sync pull`

- [ ] Push changed files since last cursor; pull remote; on hash conflict write `.memrelay/conflicts/<path>.md` and surface in 动态.

- [ ] Commit `feat(sync): desktop push/pull client`

---

### Task 4: Mobile ask + browse

**Files:**
- Create: `packages/mobile/` Capacitor app reusing `packages/desktop/src` screens 分身 + 记忆 (or shared `shell-ui`)
- Point API base to: local shell-api via sync’d vault **or** remote read-replica endpoint that still decrypts only on device then answers via on-device engine

**Mobile answering strategy (v1 decision locked here):**  
Ship **on-device engine** if Python mobile is too heavy; otherwise mobile only **browses decrypted files** and **asks** through a user-approved relay to the desktop shell-api while desktop is online. Default for v1: **relay ask to paired desktop** when online; offline browse-only.

- [ ] Implement relay ask: mobile → sync server message queue → desktop worker → answer → response queue (ciphertext).  
- [ ] Commit `feat(mobile): ask+browse via paired desktop relay`

---

### Task 5: Phase 2 verification

- [ ] Two devices: desktop edits preference → phone sees it after pull.  
- [ ] Phone ask returns disclosure + citations while desktop online.  
- [ ] Server disk contains no plaintext Chinese memory body (spot-check).  
- [ ] `uv run pytest packages/core/tests packages/sync/tests -q` green.

---

## Phase 2 done when

Spec success criteria 2–4 satisfied: phone shows same memories; Cursor still works; digest/conflicts visible on desktop.
