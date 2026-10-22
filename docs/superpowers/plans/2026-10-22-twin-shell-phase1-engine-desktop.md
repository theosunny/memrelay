# Twin Shell Phase 1: Faces + Local Shell API + Desktop App

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ship a human desktop shell (tray + 分身 / 记忆 / 动态) over a face-aware MemRelay engine and a 127.0.0.1 shell HTTP API, without teaching users MCP or config.toml.

**Architecture:** Keep `packages/core` as the OSS engine. Add a `Face` model (N faces on one vault). Expose a localhost-only JSON API (`shell_api.py`) for the first-party UI. Build `packages/desktop` as a Tauri 2 + React app that talks only to that API. MCP gateway stays for Cursor/千面 products and is unchanged in behavior except face-aware ceilings.

**Tech Stack:** Python 3.11+, Starlette/uvicorn (already deps), pytest, Tauri 2, React + TypeScript, Vite.

**Spec:** [2026-10-22-twin-product-shell-design.md](../specs/2026-10-22-twin-product-shell-design.md)

**Follow-up:** Phase 2 plan — E2E sync + mobile ask/browse (`2026-10-22-twin-shell-phase2-sync-mobile.md`).

## Global Constraints

- Apache-2.0; no new AGPL dependency in-tree.
- Shell API binds `127.0.0.1` only; bearer token required on every request.
- Product copy never surfaces MCP, toml, or CLI on the home screens.
- Twin answers always include disclosure + citations (existing `twin.py` guarantees).
- Never auto-send; no forget/delete tools on shell API.
- Default face id is `self` with `visibility_ceiling=private`.
- Desktop must work against an already-initialized vault (`~/MemRelay` / config).
- Prefer TDD for engine changes; desktop UI smoke can be manual + thin unit tests for API client.

## File map (create / modify)

| Path | Responsibility |
|------|----------------|
| `packages/core/src/memrelay/faces.py` | Face dataclass, load/save `vault/.memrelay/faces/*.toml`, ensure `self` |
| `packages/core/src/memrelay/shell_api.py` | Localhost Starlette JSON API for shell |
| `packages/core/src/memrelay/cli.py` | `memrelay shell-api` command |
| `packages/core/src/memrelay/twin.py` | Optional `face_id` → ceiling from Face |
| `packages/core/src/memrelay/gateway.py` | Optional `face` arg on `answer_as_me` |
| `packages/core/tests/test_faces.py` | Face load/save/default |
| `packages/core/tests/test_shell_api.py` | HTTP API tests |
| `packages/desktop/` | Tauri + React shell app |
| `docs/superpowers/specs/2026-10-22-twin-product-shell-design.md` | Already approved (read-only) |

---

### Task 1: Face model

**Files:**
- Create: `packages/core/src/memrelay/faces.py`
- Create: `packages/core/tests/test_faces.py`
- Modify: `packages/core/src/memrelay/vault.py` — treat `.memrelay` as hidden (already in `HIDDEN_FOLDERS`)

**Interfaces:**
- Consumes: `Vault.root: Path`
- Produces:
  - `@dataclass Face` with fields: `id: str`, `name: str`, `kind: str` (`"expression"` \| `"task"`), `visibility_ceiling: str`, `capabilities: list[str]`, `refusal_extra: str = ""`
  - `faces_dir(vault: Vault) -> Path`
  - `ensure_default_faces(vault: Vault) -> list[Face]`
  - `list_faces(vault: Vault) -> list[Face]`
  - `get_face(vault: Vault, face_id: str) -> Face`
  - `save_face(vault: Vault, face: Face) -> Path`

- [x] **Step 1: Write the failing test**

```python
# packages/core/tests/test_faces.py
from memrelay.faces import Face, ensure_default_faces, get_face, list_faces, save_face
from memrelay.vault import Vault


def test_ensure_default_self_face(tmp_path):
    v = Vault(tmp_path / "vault")
    v.init()
    faces = ensure_default_faces(v)
    assert any(f.id == "self" for f in faces)
    self_face = get_face(v, "self")
    assert self_face.visibility_ceiling == "private"
    assert "answer" in self_face.capabilities
    assert "draft" in self_face.capabilities
    assert list_faces(v)[0].id == "self"


def test_save_and_reload_face(tmp_path):
    v = Vault(tmp_path / "vault")
    v.init()
    ensure_default_faces(v)
    f = Face(
        id="work",
        name="工作",
        kind="expression",
        visibility_ceiling="work",
        capabilities=["answer", "draft"],
    )
    save_face(v, f)
    loaded = get_face(v, "work")
    assert loaded.name == "工作"
    assert loaded.visibility_ceiling == "work"
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /workspace/memrelay && uv run pytest packages/core/tests/test_faces.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'memrelay.faces'`

- [x] **Step 3: Write minimal implementation**

```python
# packages/core/src/memrelay/faces.py
"""N faces on one vault: callable persona configs (expression or task-oriented)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import tomllib
import tomlkit

from .vault import Vault

ALLOWED_CEILINGS = frozenset({"public", "friends", "work", "private"})
ALLOWED_KINDS = frozenset({"expression", "task"})


@dataclass
class Face:
    id: str
    name: str
    kind: str = "expression"
    visibility_ceiling: str = "private"
    capabilities: list[str] = field(default_factory=lambda: ["answer", "draft"])
    refusal_extra: str = ""

    def validate(self) -> None:
        if not self.id or "/" in self.id or ".." in self.id:
            raise ValueError(f"invalid face id: {self.id!r}")
        if self.kind not in ALLOWED_KINDS:
            raise ValueError(f"invalid kind: {self.kind!r}")
        if self.visibility_ceiling not in ALLOWED_CEILINGS:
            raise ValueError(f"invalid ceiling: {self.visibility_ceiling!r}")


def faces_dir(vault: Vault) -> Path:
    return vault.root / ".memrelay" / "faces"


def ensure_default_faces(vault: Vault) -> list[Face]:
    d = faces_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "self.toml"
    if not path.exists():
        save_face(
            vault,
            Face(
                id="self",
                name="自我",
                kind="expression",
                visibility_ceiling="private",
                capabilities=["answer", "draft"],
            ),
        )
    return list_faces(vault)


def list_faces(vault: Vault) -> list[Face]:
    d = faces_dir(vault)
    if not d.is_dir():
        return []
    out: list[Face] = []
    for p in sorted(d.glob("*.toml")):
        out.append(_load(p))
    return out


def get_face(vault: Vault, face_id: str) -> Face:
    p = faces_dir(vault) / f"{face_id}.toml"
    if not p.is_file():
        raise KeyError(face_id)
    return _load(p)


def save_face(vault: Vault, face: Face) -> Path:
    face.validate()
    d = faces_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{face.id}.toml"
    doc = tomlkit.document()
    for k, v in asdict(face).items():
        doc[k] = v
    p.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return p


def _load(path: Path) -> Face:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    face = Face(
        id=str(data["id"]),
        name=str(data.get("name") or data["id"]),
        kind=str(data.get("kind") or "expression"),
        visibility_ceiling=str(data.get("visibility_ceiling") or "private"),
        capabilities=list(data.get("capabilities") or ["answer", "draft"]),
        refusal_extra=str(data.get("refusal_extra") or ""),
    )
    face.validate()
    return face
```

Note: `tomlkit` is already a core dependency.

- [x] **Step 4: Run test to verify it passes**

Run: `cd /workspace/memrelay && uv run pytest packages/core/tests/test_faces.py -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add packages/core/src/memrelay/faces.py packages/core/tests/test_faces.py
git commit -s -m "feat(faces): N faces on one vault with default self"
```

---

### Task 2: Face-aware `answer_as_me`

**Files:**
- Modify: `packages/core/src/memrelay/twin.py`
- Modify: `packages/core/tests/test_twin.py` (add one test)
- Modify: `packages/core/src/memrelay/gateway.py` — pass optional `face` through

**Interfaces:**
- Consumes: `get_face(vault, face_id)`, existing `answer_as_me(..., ceiling=...)`
- Produces: `answer_as_me(..., face_id: str | None = None)` uses face ceiling when `face_id` set; response includes `"face_id"`

- [x] **Step 1: Write the failing test**

```python
# append to packages/core/tests/test_twin.py
import pytest
from memrelay.faces import Face, ensure_default_faces, save_face
from memrelay.twin import answer_as_me


@pytest.mark.asyncio
async def test_answer_uses_face_ceiling(vault, backend_local):
    """work face must not see private-only notes."""
    ensure_default_faces(vault)
    save_face(vault, Face(id="work", name="工作", kind="expression",
                          visibility_ceiling="work", capabilities=["answer"]))
    # assume fixture writes a private preference; if not, write one:
    from memrelay.schema import Note, MemoryType, Status, Visibility, Sensitivity
    from pathlib import Path
    n = Note(title="secret pref", type=MemoryType.preference, body="我只私下喜欢抹茶",
             status=Status.active, visibility=Visibility.private,
             sensitivity=Sensitivity.normal, confidence=0.9,
             source_agent="test", source_channel="test")
    p = vault.folder_for("preference")
    p.mkdir(parents=True, exist_ok=True)
    (p / "secret.md").write_text(n.to_markdown(), encoding="utf-8")
    res = await answer_as_me("我喜欢什么？", vault=vault, backend=backend_local, face_id="work")
    assert res["face_id"] == "work"
    # Either unknown or answer that does not cite the private note id
    if res["citations"]:
        assert all("secret" not in c["id"] for c in res["citations"])
```

Adapt fixture names to match `test_twin.py` (`vault`, backend). If existing tests use a different harness, mirror that harness exactly.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/test_twin.py::test_answer_uses_face_ceiling -v`  
Expected: FAIL (`face_id` unexpected kwarg)

- [x] **Step 3: Minimal implementation**

In `answer_as_me`, add `face_id: str | None = None`. When set:

```python
from .faces import get_face
# after today = ...
if face_id:
    face = get_face(vault, face_id)
    if "answer" not in face.capabilities:
        audit("answer_as_me", question, [], True, {"face_id": face_id})
        return {**base, "answer": "这个面不能回答。 / This face cannot answer.",
                "citations": [], "confidence": 0.0, "refused": True,
                "face_id": face_id, "mode": "policy"}
    ceiling = face.visibility_ceiling
# ... existing logic ...
# every return dict includes "face_id": face_id
```

In `gateway.py` `answer_as_me` tool, add optional `face: str | None = None` and pass `face_id=face`.

- [x] **Step 4: Run tests**

Run: `uv run pytest packages/core/tests/test_twin.py packages/core/tests/test_faces.py -q`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add packages/core/src/memrelay/twin.py packages/core/src/memrelay/gateway.py packages/core/tests/test_twin.py
git commit -s -m "feat(twin): answer_as_me respects face visibility ceiling"
```

---

### Task 3: Local shell HTTP API

**Files:**
- Create: `packages/core/src/memrelay/shell_api.py`
- Create: `packages/core/tests/test_shell_api.py`
- Modify: `packages/core/src/memrelay/cli.py` — add `shell-api` command

**Interfaces:**
- Consumes: `Config`, `Vault`, `make_backend`, `get_llm`, `list_faces`, `ensure_default_faces`, `answer_as_me`, `weekly_auto_digest`, vault markdown listing
- Produces: `build_shell_app(cfg, token) -> Starlette` with routes below; `serve_shell_api(port=8787)`

Routes (all JSON, `Authorization: Bearer <token>`):

| Method | Path | Body / query | Response |
|--------|------|--------------|----------|
| GET | `/v1/health` | — | `{ok: true, version: "..."}` |
| GET | `/v1/faces` | — | `{faces: Face[]}` |
| POST | `/v1/twin/ask` | `{question, face_id?}` | `answer_as_me` dict |
| GET | `/v1/memories` | `q?`, `type?`, `limit?` | `{items: [{id,title,type,snippet,status}]}` |
| GET | `/v1/memories/{id}` | id = vault-relative path url-encoded | full note JSON |
| GET | `/v1/activity` | `days?=7` | `{digest: str, items: [...]}` from auto-applied log |

- [x] **Step 1: Write failing API tests** using Starlette `TestClient`

```python
# packages/core/tests/test_shell_api.py
from starlette.testclient import TestClient
from memrelay.config import Config
from memrelay.shell_api import build_shell_app
from memrelay.vault import Vault
from memrelay.faces import ensure_default_faces


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMRELAY_HOME", str(tmp_path / "home"))
    cfg = Config(vault=tmp_path / "vault")
    Vault(cfg.vault).init()
    ensure_default_faces(Vault(cfg.vault))
    app = build_shell_app(cfg, token="test-token")
    return TestClient(app)


def test_health_requires_token(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/v1/health").status_code == 401
    r = c.get("/v1/health", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_list_faces(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/v1/faces", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()["faces"]]
    assert "self" in ids
```

- [x] **Step 2: Run — expect FAIL missing module**

Run: `uv run pytest packages/core/tests/test_shell_api.py -v`

- [x] **Step 3: Implement `shell_api.py`**

Key rules in implementation:

- Host guard: reject if Host not localhost (same as `web.py`)
- Token: `Authorization: Bearer` compared with `secrets.compare_digest`
- Bind only via uvicorn `host="127.0.0.1"` in serve helper
- `/v1/memories` without backend search: walk vault folders excluding `HIDDEN_FOLDERS`, filter by substring in title/body; mark this as FTS-lite for v1 (Basic Memory search can be added as enhancement in same file if `make_backend` starts cleanly)
- Prefer starting backend for ask; if backend start fails, return 503 JSON `{error: "backend_unavailable"}`

CLI:

```python
@app.command("shell-api")
def shell_api_cmd(
    port: int = typer.Option(8787, "--port"),
    token_file: Path | None = typer.Option(None, "--token-file"),
):
    """Local JSON API for the desktop/mobile shell (127.0.0.1 only)."""
    from .shell_api import serve_shell_api
    serve_shell_api(port=port, token_file=token_file)
```

Write token to `data_dir()/shell-api.token` with mode 0600; print path once.

- [x] **Step 4: Run tests**

Run: `uv run pytest packages/core/tests/test_shell_api.py packages/core/tests/test_faces.py -q`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add packages/core/src/memrelay/shell_api.py packages/core/tests/test_shell_api.py packages/core/src/memrelay/cli.py
git commit -s -m "feat(shell-api): localhost JSON API for twin product shell"
```

---

### Task 4: Desktop app scaffold (Tauri 2 + React)

**Files:**
- Replace placeholder: `packages/desktop/README.md`
- Create Tauri+Vite+React app under `packages/desktop/` (standard `npm create tauri-app` layout):
  - `packages/desktop/src-tauri/`
  - `packages/desktop/src/` (React)
  - `packages/desktop/package.json`

**Interfaces:**
- Consumes: shell API at `http://127.0.0.1:8787` with token from env `MEMRELAY_SHELL_TOKEN` or file
- Produces: runnable `npm run tauri dev` showing three nav items: 分身 / 记忆 / 动态

- [x] **Step 1: Scaffold**

```bash
cd /workspace/memrelay/packages/desktop
# If empty aside from README, scaffold manually to avoid interactive prompts:
# create package.json, vite.config.ts, index.html, src/main.tsx, src/App.tsx,
# src-tauri/tauri.conf.json with productName "忆桥分身", identifier "io.memrelay.shell"
```

`App.tsx` must have three tabs with Chinese labels only (no MCP strings).

- [x] **Step 2: API client module**

```typescript
// packages/desktop/src/api.ts
export type Face = { id: string; name: string; kind: string; visibility_ceiling: string };

const base = () => localStorage.getItem("shellBase") || "http://127.0.0.1:8787";
const token = () => localStorage.getItem("shellToken") || "";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${base()}${path}`, {
    ...init,
    headers: {
      "Authorization": `Bearer ${token()}`,
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const getFaces = () => api<{ faces: Face[] }>("/v1/faces");
export const askTwin = (question: string, face_id = "self") =>
  api<any>("/v1/twin/ask", { method: "POST", body: JSON.stringify({ question, face_id }) });
export const listMemories = (q = "") =>
  api<{ items: any[] }>(`/v1/memories?q=${encodeURIComponent(q)}`);
export const getActivity = () => api<{ digest: string; items: any[] }>("/v1/activity");
```

- [x] **Step 3: Wire three screens**

- 分身: textarea + send → `askTwin`; show answer, citations, disclosure  
- 记忆: search box → `listMemories`; list titles  
- 动态: `getActivity` digest  

Settings gear (secondary): paste token + base URL (first-run only).

- [x] **Step 4: Manual smoke**

```bash
# terminal A
memrelay shell-api --port 8787
# copy token from data dir into desktop settings
# terminal B
cd packages/desktop && npm install && npm run tauri dev
```

Expected: ask a question; see cited answer; memories list non-empty if vault has notes.

- [x] **Step 5: Commit**

```bash
git add packages/desktop
git commit -s -m "feat(desktop): 忆桥分身 shell with 分身/记忆/动态"
```

---

### Task 5: Autostart shell-api with desktop (dev path)

**Files:**
- Modify: `packages/desktop/src-tauri/src/lib.rs` (or `main.rs`) — on app start, spawn `memrelay shell-api` if health check fails
- Modify: `packages/desktop/README.md` — human install steps (Chinese + English)

- [x] **Step 1: Document spawn contract in README**

Desktop looks for `memrelay` on PATH; runs `memrelay shell-api --port 8787 --token-file <app_data>/shell-api.token`.

- [x] **Step 2: Implement sidecar spawn + health poll** (Rust `Command`, poll `/v1/health`)

- [x] **Step 3: Manual test cold start without pre-running API**

Expected: app opens, API comes up, 分身 works.

- [x] **Step 4: Commit**

```bash
git commit -s -m "feat(desktop): spawn local shell-api on launch"
```

---

### Task 6: Phase 1 verification gate

- [x] **Step 1: Engine tests**

Run: `cd /workspace/memrelay && uv run pytest packages/core/tests -q`  
Expected: all PASS

- [x] **Step 2: Spec coverage check**

Confirm Phase 1 hits: faces model, desktop three entries, self face chat with citations, memory browse, activity digest, OSS engine still MCP-compatible. Sync + mobile left to Phase 2.

- [x] **Step 3: Commit docs touch if needed**

Update `packages/desktop/README.md` status from “planned” to “Phase 1 scaffold”.

```bash
git commit -s -m "docs(desktop): Phase 1 shell status"
```

---

## Phase 1 done when

1. `uv run pytest packages/core/tests -q` green.  
2. Desktop shows 分身 / 记忆 / 动态 with Chinese UI.  
3. Asking on 自我 face returns disclosure + citations from the real vault.  
4. MCP `answer_as_me` still works (optional `face` arg).


## Spec coverage (Phase 1 self-review)

| Spec requirement | Task |
|------------------|------|
| OSS engine + N faces model | Task 1–2 |
| Desktop 分身 / 记忆 / 动态 | Task 4–5 |
| Self face chat + citations/disclosure | Task 2–4 (twin guarantees) |
| Memory browse/search | Task 3 `/v1/memories` + Task 4 |
| Activity / auto digest | Task 3 `/v1/activity` + Task 4 |
| MCP still works for 千面 | Task 2 gateway optional `face` |
| Quiet auto-capture | Already in engine; unchanged Phase 1 |
| Built-in E2E sync | **Phase 2** |
| Mobile ask+browse | **Phase 2** |
| 办事面 skill runtime | Out of scope (spec later) |
