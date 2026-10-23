# MemRelay sync protocol

端到端加密同步：服务器只保存密文。桌面是主写入方，手机拉取后浏览，提问经加密信箱交给在线的桌面回答。

## Keys

- `generate_vault_key()` is a Fernet key (URL-safe base64 of 32 bytes). It lives in the device data dir (`data/sync/state.json`, mode `0600`), never in the vault and never in a request body except inside a ciphertext.
- A blob is `Fernet.encrypt(utf-8 JSON)` of `{"path": "<vault-relative>", "body": "<file text>"}`.
- The server addresses a blob by `sha256(path)`, so filenames are not stored.

## What syncs

- Reviewed vault Markdown (anything that is not under a hidden folder).
- `.memrelay/faces/*.toml`.

Never synced: `data_dir()` (capture cursors, audit, shell token, the vault key), `inbox/`, `rejected/`, `archive/`, `sources/`, `.memrelay/conflicts/`.

Deletes are not synced. `shortcut: no tombstones, add them when a deletion on one device must remove the file on the other.`

## Pairing

1. Desktop `POST /pair/start` `{"vault_id": "<hex>"}` → `{pair_code, vault_id}`. The code is 8 characters and expires in 10 minutes.
2. Desktop `POST /pair/finish` `{"pair_code", "device_pubkey"}` → `{device_token, vault_id}`.
3. The desktop shows a QR of `mr1.<vault_id>.<pair_code>.<fernet-key>` and the same string as text. The phone scans or pastes. The key is not sent to the server.
4. The phone parses the string locally and calls `/pair/finish` with the same code. The key is not sent.
5. `device_pubkey` is stored as a label. Encryption stays the shared vault key. `shortcut: not a per-device sealed box, switch if devices must not share one key.`

Later calls send `Authorization: Bearer <device_token>`. The server stores `sha256(token)`, not the token.

`/pair/finish` allows 8 misses per client, then locks that client for 10 minutes. `/pair/start` allows 20 new codes per client per 10 minutes. Counters are in memory. `shortcut: one process, a restart clears the lockout.`

Bind `127.0.0.1` unless a phone on the same LAN must connect (`--host 0.0.0.0`). That is still not a public-internet deployment: there is no TLS, and the pair code is only 8 characters.

## Blobs

| Method | Path | Body | Response |
|--------|------|------|----------|
| PUT | `/v1/blobs/{vault_id}/{path_hash}` | ciphertext bytes | `{etag}` sha256 of those bytes |
| GET | `/v1/blobs/{vault_id}` | — | `{blobs: [{path_hash, etag}]}` |
| GET | `/v1/blobs/{vault_id}/{path_hash}` | — | ciphertext bytes |

## Conflicts

Desktop pushes. Phone does not. On pull, if the remote etag changed and the local file also changed since the cursor, the remote bytes are written to `.memrelay/conflicts/<same relative path>` and the local file is left alone. Desktop 动态 lists that directory as 需要你看一眼.

## Relay ask

Phone encrypts `{"question", "face_id"}` and `POST /v1/relay/{vault_id}`. Desktop `memrelay sync relay` (also started beside `shell-api`) decrypts, calls `answer_as_me` (face ceiling applies), and `PUT`s the encrypted answer. The phone polls `GET .../{id}/answer`. Offline, the phone only browses files it already pulled.
