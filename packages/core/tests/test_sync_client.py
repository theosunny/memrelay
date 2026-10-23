import pytest
from starlette.testclient import TestClient

from memrelay.faces import Face, ensure_default_faces, save_face
from memrelay.schema import Note
from memrelay.sync_client import ask_remote, pair_desktop, pair_phone, pull, push, relay_once
from memrelay.vault import Vault
from memrelay_sync.app import build_app


def _note(body: str) -> str:
    return Note(title="饮品", type="preference", body=body, status="active",
                visibility="private", confidence=0.9).to_markdown()


def test_push_pull_conflict_and_relay(tmp_path, monkeypatch):
    client = TestClient(build_app(tmp_path / "server"))
    desk, phone = tmp_path / "desk", tmp_path / "phone"
    monkeypatch.setenv("MEMRELAY_HOME", str(desk))
    (desk / "config").mkdir(parents=True)
    (desk / "config" / "config.toml").write_text('backend = "local"\n', encoding="utf-8")
    vault_a = Vault(desk / "vault")
    vault_a.init()
    ensure_default_faces(vault_a)
    (vault_a.folder_for("preference") / "tea.md").write_text(_note("我喜欢抹茶"), encoding="utf-8")
    (vault_a.root / "inbox" / "nope.md").write_text(_note("不要同步"), encoding="utf-8")
    info = pair_desktop(vault_a, "http://sync", client=client)
    assert push(vault_a, client=client)["pushed"] >= 2
    raw = b"".join(p.read_bytes() for p in (tmp_path / "server").rglob("*") if p.is_file())
    assert "我喜欢抹茶".encode() not in raw

    monkeypatch.setenv("MEMRELAY_HOME", str(phone))
    vault_b = Vault(phone / "vault")
    vault_b.init()
    pair_phone(info["pairing"], "http://sync", client=client)
    assert pull(vault_b, client=client)["pulled"] >= 2
    assert "我喜欢抹茶" in (vault_b.root / "preferences" / "tea.md").read_text(encoding="utf-8")
    assert (vault_b.root / ".memrelay" / "faces" / "self.toml").is_file()
    assert not (vault_b.root / "inbox" / "nope.md").exists()
    with pytest.raises(PermissionError):
        push(vault_b, client=client)

    def pump():
        monkeypatch.setenv("MEMRELAY_HOME", str(desk))
        relay_once(vault_a, client=client)
        monkeypatch.setenv("MEMRELAY_HOME", str(phone))

    answer = ask_remote("我喜欢什么？", "self", client=client, pump=pump, tries=1)
    assert answer["face_id"] == "self" and answer["disclosure"] and "抹茶" in answer["answer"]
    assert answer["citations"]
    save_face(vault_a, Face(id="out", name="对外", visibility_ceiling="public", capabilities=["answer"]))
    low = ask_remote("我喜欢什么？", "out", client=client, pump=pump, tries=1)
    assert low["face_id"] == "out" and "抹茶" not in low["answer"]

    (vault_b.root / "preferences" / "tea.md").write_text(_note("手机改过"), encoding="utf-8")
    monkeypatch.setenv("MEMRELAY_HOME", str(desk))
    (vault_a.root / "preferences" / "tea.md").write_text(_note("桌面改过"), encoding="utf-8")
    push(vault_a, client=client)
    monkeypatch.setenv("MEMRELAY_HOME", str(phone))
    again = pull(vault_b, client=client)
    assert "preferences/tea.md" in again["conflicts"]
    assert "手机改过" in (vault_b.root / "preferences" / "tea.md").read_text(encoding="utf-8")
    remote = vault_b.root / ".memrelay" / "conflicts" / "preferences" / "tea.md"
    assert "桌面改过" in remote.read_text(encoding="utf-8")
    client.close()
