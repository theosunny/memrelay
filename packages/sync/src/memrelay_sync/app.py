"""Ciphertext blob server. It never decrypts a vault."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

_CODE = re.compile(r"^[A-Z2-9]{8}$")
_HEX = re.compile(r"^[0-9a-f]{16,64}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_RID = re.compile(r"^[0-9a-f]{16}$")
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_MAX = 2_000_000
_PAIR_TTL = 600


def _cors(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, OPTIONS"
    return resp


class _Cors(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return _cors(Response(status_code=204))
        return _cors(await call_next(request))


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def start_pair(self, vault_id: str | None) -> dict:
        vault_id = (vault_id or secrets.token_hex(16)).lower()
        if not _HEX.fullmatch(vault_id):
            raise ValueError("bad vault_id")
        code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        path = self.root / "pair" / f"{code}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"vault_id": vault_id, "exp": time.time() + _PAIR_TTL}), encoding="utf-8")
        return {"pair_code": code, "vault_id": vault_id}

    def finish_pair(self, code: str, device_pubkey: str) -> dict:
        if not _CODE.fullmatch(code or ""):
            raise KeyError(code)
        path = self.root / "pair" / f"{code}.json"
        if not path.is_file():
            raise KeyError(code)
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec["exp"] < time.time():
            path.unlink(missing_ok=True)
            raise KeyError(code)
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        dest = self.root / "tokens" / digest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({
            "vault_id": rec["vault_id"],
            "device_pubkey": (device_pubkey or "")[:200],
        }), encoding="utf-8")
        return {"device_token": token, "vault_id": rec["vault_id"]}

    def vault_for(self, token: str) -> str | None:
        if not token:
            return None
        path = self.root / "tokens" / hashlib.sha256(token.encode()).hexdigest()
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["vault_id"]

    def put_blob(self, vault_id: str, path_hash: str, data: bytes) -> str:
        self._ids(vault_id, path_hash)
        etag = hashlib.sha256(data).hexdigest()
        with self._lock:
            dest = self.root / "vaults" / vault_id / path_hash
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            idx = self._index(vault_id)
            idx[path_hash] = etag
            self._write_index(vault_id, idx)
        return etag

    def list_blobs(self, vault_id: str) -> list[dict]:
        self._ids(vault_id, "0" * 64)
        idx = self._index(vault_id)
        return [{"path_hash": k, "etag": v} for k, v in sorted(idx.items())]

    def get_blob(self, vault_id: str, path_hash: str) -> bytes | None:
        self._ids(vault_id, path_hash)
        path = self.root / "vaults" / vault_id / path_hash
        if not path.is_file():
            return None
        return path.read_bytes()

    def put_question(self, vault_id: str, data: bytes) -> str:
        self._ids(vault_id, "0" * 64)
        rid = secrets.token_hex(8)
        with self._lock:
            dest = self.root / "vaults" / vault_id / "relay" / f"{rid}.q"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        return rid

    def pending(self, vault_id: str) -> list[str]:
        self._ids(vault_id, "0" * 64)
        d = self.root / "vaults" / vault_id / "relay"
        if not d.is_dir():
            return []
        return sorted(p.name[:-2] for p in d.glob("*.q") if not (d / f"{p.name[:-2]}.a").exists())

    def question(self, vault_id: str, rid: str) -> bytes | None:
        return self._relay_file(vault_id, rid, "q")

    def answer(self, vault_id: str, rid: str) -> bytes | None:
        return self._relay_file(vault_id, rid, "a")

    def put_answer(self, vault_id: str, rid: str, data: bytes) -> None:
        if self.question(vault_id, rid) is None:
            raise KeyError(rid)
        dest = self.root / "vaults" / vault_id / "relay" / f"{rid}.a"
        dest.write_bytes(data)

    def _relay_file(self, vault_id: str, rid: str, suffix: str) -> bytes | None:
        if not _RID.fullmatch(rid or ""):
            raise KeyError(rid)
        self._ids(vault_id, "0" * 64)
        path = self.root / "vaults" / vault_id / "relay" / f"{rid}.{suffix}"
        if not path.is_file():
            return None
        return path.read_bytes()

    def _ids(self, vault_id: str, path_hash: str) -> None:
        if not _HEX.fullmatch(vault_id or "") or not _HASH.fullmatch(path_hash or ""):
            raise KeyError(vault_id)

    def _index(self, vault_id: str) -> dict[str, str]:
        path = self.root / "vaults" / vault_id / "index.json"
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_index(self, vault_id: str, idx: dict) -> None:
        path = self.root / "vaults" / vault_id / "index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(idx), encoding="utf-8")


def build_app(root: Path) -> Starlette:
    store = Store(root)

    def _token(request: Request) -> str:
        header = request.headers.get("authorization") or ""
        return header[7:] if header[:7].lower() == "bearer " else ""

    def _auth(request: Request, vault_id: str) -> Response | None:
        if store.vault_for(_token(request)) != vault_id:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return None

    async def health(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    async def pair_start(request: Request) -> Response:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        try:
            return JSONResponse(store.start_pair(body.get("vault_id")))
        except ValueError:
            return JSONResponse({"error": "bad_vault"}, status_code=400)

    async def pair_finish(request: Request) -> Response:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_json"}, status_code=400)
        try:
            return JSONResponse(store.finish_pair(str(body.get("pair_code") or ""), str(body.get("device_pubkey") or "")))
        except KeyError:
            return JSONResponse({"error": "unknown_code"}, status_code=404)

    async def put_blob(request: Request) -> Response:
        vault_id, path_hash = request.path_params["vault_id"], request.path_params["path_hash"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        data = await request.body()
        if not data or len(data) > _MAX:
            return JSONResponse({"error": "bad_body"}, status_code=400)
        try:
            etag = store.put_blob(vault_id, path_hash, data)
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse({"etag": etag})

    async def list_blobs(request: Request) -> Response:
        vault_id = request.path_params["vault_id"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        try:
            return JSONResponse({"blobs": store.list_blobs(vault_id)})
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)

    async def get_blob(request: Request) -> Response:
        vault_id, path_hash = request.path_params["vault_id"], request.path_params["path_hash"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        try:
            data = store.get_blob(vault_id, path_hash)
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if data is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return Response(data, media_type="application/octet-stream")

    async def relay_post(request: Request) -> Response:
        vault_id = request.path_params["vault_id"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        data = await request.body()
        if not data or len(data) > _MAX:
            return JSONResponse({"error": "bad_body"}, status_code=400)
        try:
            return JSONResponse({"id": store.put_question(vault_id, data)})
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)

    async def relay_pending(request: Request) -> Response:
        vault_id = request.path_params["vault_id"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        try:
            return JSONResponse({"items": [{"id": i} for i in store.pending(vault_id)]})
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)

    async def relay_question(request: Request) -> Response:
        vault_id, rid = request.path_params["vault_id"], request.path_params["rid"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        try:
            data = store.question(vault_id, rid)
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if data is None:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return Response(data, media_type="application/octet-stream")

    async def relay_answer_get(request: Request) -> Response:
        vault_id, rid = request.path_params["vault_id"], request.path_params["rid"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        try:
            data = store.answer(vault_id, rid)
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if data is None:
            return Response(status_code=204)
        return Response(data, media_type="application/octet-stream")

    async def relay_answer_put(request: Request) -> Response:
        vault_id, rid = request.path_params["vault_id"], request.path_params["rid"]
        if (bad := _auth(request, vault_id)) is not None:
            return bad
        data = await request.body()
        if not data or len(data) > _MAX:
            return JSONResponse({"error": "bad_body"}, status_code=400)
        try:
            store.put_answer(vault_id, rid, data)
        except KeyError:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/health", health),
            Route("/pair/start", pair_start, methods=["POST"]),
            Route("/pair/finish", pair_finish, methods=["POST"]),
            Route("/v1/blobs/{vault_id}", list_blobs, methods=["GET"]),
            Route("/v1/blobs/{vault_id}/{path_hash}", put_blob, methods=["PUT"]),
            Route("/v1/blobs/{vault_id}/{path_hash}", get_blob, methods=["GET"]),
            Route("/v1/relay/{vault_id}/pending", relay_pending, methods=["GET"]),
            Route("/v1/relay/{vault_id}/{rid}/question", relay_question, methods=["GET"]),
            Route("/v1/relay/{vault_id}/{rid}/answer", relay_answer_get, methods=["GET"]),
            Route("/v1/relay/{vault_id}/{rid}/answer", relay_answer_put, methods=["PUT"]),
            Route("/v1/relay/{vault_id}", relay_post, methods=["POST"]),
        ],
        middleware=[Middleware(_Cors)],
    )


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="MemRelay ciphertext sync server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--data", default=None)
    args = parser.parse_args()
    # shortcut: default bind is loopback, pass --host 0.0.0.0 when a phone on the LAN must connect
    root = Path(args.data or os.environ.get("MEMRELAY_SYNC_DIR") or Path.home() / ".memrelay-sync")
    uvicorn.run(build_app(root), host=args.host, port=args.port, log_level="warning")
