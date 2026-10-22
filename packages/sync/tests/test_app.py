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
