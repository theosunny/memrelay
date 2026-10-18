import json
import zipfile

import pytest
from typer.testing import CliRunner

from memrelay import importers
from memrelay.cli import app
from memrelay.extract.stub import StubExtractor
from memrelay.vault import Vault

CHATGPT = [{
    "title": "跑步", "conversation_id": "c1", "create_time": 1700000000.0,
    "mapping": {
        "root": {"id": "root", "message": None, "children": ["a"]},
        "a": {"id": "a", "message": {"id": "a", "author": {"role": "system"}, "create_time": 1,
                                       "content": {"content_type": "text", "parts": ["sys"]},
                                       "metadata": {"is_visually_hidden_from_conversation": True}}},
        "b": {"id": "b", "message": {"id": "b", "author": {"role": "user"}, "create_time": 2,
                                       "content": {"content_type": "text", "parts": ["我喜欢早起跑步"]}}},
        "c": {"id": "c", "message": {"id": "c", "author": {"role": "assistant"}, "create_time": 3,
                                       "content": {"content_type": "text", "parts": ["好的"]}}},
        "d": {"id": "d", "message": {"id": "d", "author": {"role": "user"}, "create_time": 4,
                                       "content": {"content_type": "multimodal_text",
                                                   "parts": [{"asset_pointer": "x"}, "I prefer dark mode"]}}},
    },
}]
CLAUDE = [{
    "uuid": "u1", "name": "咖啡", "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:01:00Z",
    "chat_messages": [
        {"uuid": "m1", "sender": "human", "text": "我习惯喝美式咖啡", "created_at": "2025-01-01T00:00:01Z"},
        {"uuid": "m2", "sender": "assistant", "text": "", "created_at": "2025-01-01T00:00:02Z", "content": [{"type": "text", "text": "了解"}]},
    ],
}]


def make_zip(path, data, inner="conversations.json"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(inner, json.dumps(data, ensure_ascii=False))
        z.writestr("user.json", "{}")
    return path


def test_detect_and_messages(tmp_path):
    p = make_zip(tmp_path / "chatgpt-export.zip", CHATGPT)
    kind, data = importers.load(p)
    assert kind == "chatgpt"
    msgs = list(importers.iter_messages(kind, data, p.name))
    assert [(m.role, m.text) for m in msgs] == [("user", "我喜欢早起跑步"), ("assistant", "好的"),
                                               ("user", "I prefer dark mode")]
    assert msgs[0].source_ref == "chatgpt-export.zip#c1/b" and msgs[0].timestamp.startswith("1970")
    (tmp_path / "cl").mkdir()
    (tmp_path / "cl" / "conversations.json").write_text(json.dumps(CLAUDE), encoding="utf-8")
    kind, data = importers.load(tmp_path / "cl" / "conversations.json")
    assert kind == "claude"
    assert [(m.role, m.text) for m in importers.iter_messages(kind, data, "x")] == [
        ("user", "我习惯喝美式咖啡"), ("assistant", "了解")]


def test_not_exports(tmp_path):
    make_zip(tmp_path / "other.zip", {"a": 1})
    (tmp_path / "bad.zip").write_bytes(b"nope")
    with zipfile.ZipFile(tmp_path / "noconv.zip", "w") as z:
        z.writestr("readme.txt", "hi")
    assert importers.scan([tmp_path]) == []
    with pytest.raises(ValueError):
        importers.run_import(tmp_path / "other.zip", StubExtractor(), None)


def test_scan_import_and_dedupe(home, tmp_path, inbox):
    dl = tmp_path / "Downloads"
    dl.mkdir()
    make_zip(dl / "a.zip", CHATGPT)
    make_zip(dl / "b.zip", CLAUDE, inner="data-2025/conversations.json")
    found = importers.scan([dl])
    assert [(c.path.name, c.kind, c.already_imported) for c in found] == [
        ("a.zip", "chatgpt", False), ("b.zip", "claude", False)]
    archived = []
    rep = importers.run_import(dl / "a.zip", StubExtractor(), inbox,
                               archive=lambda k, raw: archived.append((k, json.loads(raw))))
    assert rep.kind == "chatgpt" and rep.messages == 3 and len(rep.proposed) == 2 and rep.archived
    assert archived[0][0] == "chatgpt" and archived[0][1][0]["conversation_id"] == "c1"
    notes = [inbox.get(i) for i in rep.proposed]
    assert {n.source_channel for n in notes} == {"export-import"}
    assert {n.source_agent for n in notes} == {"chatgpt"}
    assert importers.scan([dl])[0].already_imported
    again = importers.run_import(dl / "a.zip", StubExtractor(), inbox)
    assert again.proposed == [] and again.duplicates == 2


def test_archive_failure_is_reported(home, tmp_path, inbox):
    p = make_zip(tmp_path / "c.zip", CLAUDE)

    def boom(kind, raw):
        raise RuntimeError("bm failed")

    rep = importers.run_import(p, StubExtractor(), inbox, archive=boom)
    assert not rep.archived and rep.archive_error == "bm failed" and len(rep.proposed) == 1


def test_archive_command(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["content"] = open(cmd[-3]).read()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(importers.subprocess, "run", fake_run)
    importers.archive_with_basic_memory("claude", b"[]", ["basic-memory"], {})
    assert seen["cmd"][:4] == ["basic-memory", "import", "claude", "conversations"]
    assert seen["cmd"][-2:] == ["--folder", "sources/claude"] and seen["content"] == "[]"
    importers.archive_with_basic_memory("chatgpt", b"[]", ["bm"], {})
    assert seen["cmd"][1:3] == ["import", "chatgpt"]


def test_sources_folder_hidden(tmp_path):
    v = Vault(tmp_path / "v")
    v.init()
    (v.root / "sources" / "chatgpt").mkdir(parents=True)
    (v.root / "sources" / "chatgpt" / "x.md").write_text("---\ntitle: x\n---\nraw", encoding="utf-8")
    assert v.is_hidden(v.root / "sources" / "chatgpt" / "x.md")


def test_cli_import_asks_first(home, tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    make_zip(dl / "a.zip", CHATGPT)
    r = CliRunner()
    out = r.invoke(app, ["import", "scan", "--dir", str(dl)])
    assert "chatgpt" in out.output and "a.zip" in out.output
    out = r.invoke(app, ["import", "run", "--dir", str(dl), "--no-archive"], input="n\n")
    assert out.exit_code == 0 and "proposed=" not in out.output
    out = r.invoke(app, ["import", "run", "--dir", str(dl), "--no-archive"], input="y\n")
    assert "proposed=2" in out.output
    out = r.invoke(app, ["import", "run", "--dir", str(dl), "--no-archive", "--yes"])
    assert "Nothing to import" in out.output
