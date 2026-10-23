import json
from datetime import datetime

from starlette.testclient import TestClient

from memrelay.config import Config
from memrelay.faces import ensure_default_faces
from memrelay.schema import Note
from memrelay.shell_api import build_shell_app, load_or_create_token
from memrelay.vault import Vault

H = {"Authorization": "Bearer test-token"}


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMRELAY_HOME", str(tmp_path / "home"))
    cfg = Config(vault=tmp_path / "vault", backend="local")
    Vault(cfg.vault).init()
    ensure_default_faces(Vault(cfg.vault))
    app = build_shell_app(cfg, token="test-token")
    return TestClient(app)


def test_health_requires_token(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/v1/health").status_code == 401
    r = c.get("/v1/health", headers=H)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert c.get("/v1/health", headers={**H, "host": "evil.example"}).status_code == 403
    pre = c.options("/v1/health")
    assert pre.status_code == 204
    assert pre.headers["access-control-allow-origin"] == "*"


def test_list_faces(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/v1/faces", headers=H)
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()["faces"]]
    assert "self" in ids


def test_memories_skip_hidden_and_activity_has_no_cli(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    vault = Vault(tmp_path / "vault")
    note = Note(title="常住上海", type="fact", body="我常住上海", status="active", visibility="work")
    (vault.root / "facts").mkdir(exist_ok=True)
    (vault.root / "facts" / "sh.md").write_text(note.to_markdown(), encoding="utf-8")
    (vault.root / "inbox").mkdir(exist_ok=True)
    (vault.root / "inbox" / "secret.md").write_text(note.to_markdown(), encoding="utf-8")

    listed = c.get("/v1/memories", headers=H, params={"q": "上海"})
    assert listed.status_code == 200
    ids = [i["id"] for i in listed.json()["items"]]
    assert "facts/sh.md" in ids
    assert all(not i.startswith("inbox/") for i in ids)

    one = c.get("/v1/memories/facts/sh.md", headers=H)
    assert one.status_code == 200 and "上海" in one.json()["body"]
    assert c.get("/v1/memories/../secrets.md", headers=H).status_code in (404, 400)
    assert c.delete("/v1/memories/facts/sh.md", headers=H).status_code == 405

    log = tmp_path / "home" / "data" / "state"
    log.mkdir(parents=True)
    (log / "auto-applied.jsonl").write_text(json.dumps({
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "title": "常住上海",
        "dest": "facts/sh.md",
        "source_agent": "cursor",
        "source_channel": "mcp",
        "confidence": 0.8,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    (tmp_path / "vault" / ".memrelay" / "conflicts").mkdir(parents=True)
    (tmp_path / "vault" / ".memrelay" / "conflicts" / "tea.md").write_text("other", encoding="utf-8")
    act = c.get("/v1/activity", headers=H).json()
    assert "常住上海" in act["digest"] and act["items"]
    assert any(x.endswith("tea.md") for x in act["conflicts"])
    low = act["digest"].lower()
    assert "memrelay" not in low and "mcp" not in low and "review.mode" not in low


def test_ask_self_returns_disclosure(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    vault = Vault(tmp_path / "vault")
    note = Note(title="常住城市", type="fact", body="我常住上海", status="active", visibility="work",
                confidence=0.9)
    (vault.root / "facts" / "sh.md").write_text(note.to_markdown(), encoding="utf-8")
    r = c.post("/v1/twin/ask", headers=H, json={"question": "我常住哪个城市？"})
    assert r.status_code == 200
    body = r.json()
    assert body["face_id"] == "self" and body["disclosure"] and "上海" in body["answer"]
    assert body["citations"]


def test_ask_reports_backend_down(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    async def down(_app, _cfg):
        return None

    monkeypatch.setattr("memrelay.shell_api._backend", down)
    r = c.post("/v1/twin/ask", headers=H, json={"question": "你好"})
    assert r.status_code == 503 and r.json()["error"] == "backend_unavailable"


def test_shell_api_help():
    from typer.testing import CliRunner

    from memrelay.cli import app

    out = CliRunner().invoke(app, ["shell-api", "--help"])
    assert out.exit_code == 0
    assert "127.0.0.1" in out.stdout


def test_token_file_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMRELAY_HOME", str(tmp_path / "home"))
    path, token = load_or_create_token()
    assert path.is_file() and token and path.read_text(encoding="utf-8").strip() == token
    again, same = load_or_create_token()
    assert again == path and same == token
