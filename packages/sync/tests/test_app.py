import hashlib

from starlette.testclient import TestClient

from memrelay.sync_crypto import decrypt_blob, encrypt_blob, generate_vault_key
from memrelay_sync.app import build_app

PLAIN = "我喜欢抹茶".encode()


def _pair(client: TestClient, pubkey: str) -> tuple[str, str]:
    started = client.post("/pair/start", json={}).json()
    fin = client.post("/pair/finish", json={"pair_code": started["pair_code"], "device_pubkey": pubkey}).json()
    return started["vault_id"], fin["device_token"]


def test_put_get_list_is_ciphertext_only(tmp_path):
    client = TestClient(build_app(tmp_path / "store"))
    vault_id, token = _pair(client, "desktop")
    _, other = _pair(client, "stranger")
    key = generate_vault_key()
    blob = encrypt_blob(key, PLAIN)
    headers = {"Authorization": f"Bearer {token}"}
    path_hash = hashlib.sha256(b"preferences/tea.md").hexdigest()
    assert client.put(f"/v1/blobs/{vault_id}/{path_hash}", content=blob).status_code == 401
    put = client.put(f"/v1/blobs/{vault_id}/{path_hash}", content=blob, headers=headers)
    assert put.status_code == 200
    stored = (tmp_path / "store" / "vaults" / vault_id / path_hash).read_bytes()
    assert PLAIN not in stored and "我喜欢抹茶" not in stored.decode("utf-8", "ignore")
    assert decrypt_blob(key, stored) == PLAIN
    listed = client.get(f"/v1/blobs/{vault_id}", headers=headers).json()["blobs"]
    assert listed[0]["path_hash"] == path_hash and listed[0]["etag"] == put.json()["etag"]
    got = client.get(f"/v1/blobs/{vault_id}/{path_hash}", headers=headers)
    assert got.content == blob
    assert client.get(f"/v1/blobs/{vault_id}", headers={"Authorization": f"Bearer {other}"}).status_code == 401


def test_relay_roundtrip_stays_opaque(tmp_path):
    client = TestClient(build_app(tmp_path / "store"))
    vault_id, token = _pair(client, "desktop")
    phone = client.post("/pair/finish", json={
        "pair_code": client.post("/pair/start", json={"vault_id": vault_id}).json()["pair_code"],
        "device_pubkey": "phone",
    }).json()["device_token"]
    headers = {"Authorization": f"Bearer {token}"}
    phone_h = {"Authorization": f"Bearer {phone}"}
    created = client.post(f"/v1/relay/{vault_id}", content=b"cipher-question", headers=phone_h)
    rid = created.json()["id"]
    assert client.get(f"/v1/relay/{vault_id}/pending", headers=headers).json()["items"] == [{"id": rid}]
    assert client.get(f"/v1/relay/{vault_id}/{rid}/answer", headers=phone_h).status_code == 204
    assert client.put(f"/v1/relay/{vault_id}/{rid}/answer", content=b"cipher-answer", headers=headers).status_code == 200
    assert client.get(f"/v1/relay/{vault_id}/{rid}/answer", headers=phone_h).content == b"cipher-answer"
    raw = (tmp_path / "store" / "vaults" / vault_id / "relay" / f"{rid}.q").read_bytes()
    assert raw == b"cipher-question"


def test_health(tmp_path):
    assert TestClient(build_app(tmp_path / "store")).get("/health").json()["ok"] is True


def test_pair_finish_locks_out(tmp_path):
    client = TestClient(build_app(tmp_path / "store"))
    started = client.post("/pair/start", json={}).json()
    bad = {"pair_code": "AAAAAAAA", "device_pubkey": "x"}
    for _ in range(7):
        assert client.post("/pair/finish", json=bad).status_code == 404
    assert client.post("/pair/finish", json=bad).status_code == 429
    blocked = client.post("/pair/finish", json={"pair_code": started["pair_code"], "device_pubkey": "phone"})
    assert blocked.status_code == 429


def test_pair_success_clears_failures(tmp_path):
    client = TestClient(build_app(tmp_path / "store"))
    started = client.post("/pair/start", json={}).json()
    bad = {"pair_code": "AAAAAAAA", "device_pubkey": "x"}
    for _ in range(7):
        assert client.post("/pair/finish", json=bad).status_code == 404
    ok = client.post("/pair/finish", json={"pair_code": started["pair_code"], "device_pubkey": "phone"})
    assert ok.status_code == 200
    assert client.post("/pair/finish", json=bad).status_code == 404


def test_pair_start_rate_limit(tmp_path):
    client = TestClient(build_app(tmp_path / "store"))
    for _ in range(20):
        assert client.post("/pair/start", json={}).status_code == 200
    assert client.post("/pair/start", json={}).status_code == 429


def test_pair_lockout_survives_restart(tmp_path):
    root = tmp_path / "store"
    bad = {"pair_code": "AAAAAAAA", "device_pubkey": "x"}
    first = TestClient(build_app(root))
    assert first.post("/pair/finish", json=bad).status_code == 404
    for _ in range(7):
        first.post("/pair/finish", json=bad)
    again = TestClient(build_app(root))
    assert again.post("/pair/finish", json=bad).status_code == 429


def test_trusted_proxy_splits_clients(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMRELAY_TRUST_PROXY", "1")
    client = TestClient(build_app(tmp_path / "store"))
    bad = {"pair_code": "AAAAAAAA", "device_pubkey": "x"}
    for _ in range(8):
        assert client.post("/pair/finish", json=bad, headers={"X-Forwarded-For": "203.0.113.4"}).status_code in (404, 429)
    assert client.post("/pair/finish", json=bad, headers={"X-Forwarded-For": "203.0.113.4"}).status_code == 429
    assert client.post("/pair/finish", json=bad, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 404


def test_port_env_binds_public_interface(monkeypatch):
    from memrelay_sync.app import data_dir_from_env, service_bind

    monkeypatch.delenv("PORT", raising=False)
    assert service_bind() == ("127.0.0.1", 8790)
    monkeypatch.setenv("PORT", "4321")
    assert service_bind() == ("0.0.0.0", 4321)
    assert service_bind("127.0.0.1", 9) == ("127.0.0.1", 9)
    monkeypatch.setenv("MEMRELAY_SYNC_DATA", "/data")
    assert str(data_dir_from_env()) == "/data"
