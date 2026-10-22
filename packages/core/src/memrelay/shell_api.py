"""Localhost JSON API for the first-party shell (分身 / 记忆 / 动态).

Binds to 127.0.0.1 only. Every request needs ``Authorization: Bearer``.
There is no forget, delete, or send route.
"""

from __future__ import annotations

import datetime as dt
import secrets
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from . import __version__
from .config import Config, data_dir
from .faces import ensure_default_faces
from .review import iter_auto, weekly_auto_digest
from .schema import Note
from .vault import Vault

# Same host allow-list as the review UI, including Starlette's test client.
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "testserver"}


def load_or_create_token(token_file: Path | None = None) -> tuple[Path, str]:
    path = Path(token_file) if token_file else data_dir() / "shell-api.token"
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return path, existing
    token = secrets.token_urlsafe(24)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path, token


def _host_ok(request: Request) -> bool:
    host = (request.headers.get("host") or "").rsplit(":", 1)[0]
    return host in ALLOWED_HOSTS


def _bearer_ok(request: Request, token: str) -> bool:
    header = request.headers.get("authorization") or ""
    given = header[7:] if header[:7].lower() == "bearer " else ""
    if not token or not given or len(given) != len(token):
        return False
    return secrets.compare_digest(given, token)


def _cors(resp: Response) -> Response:
    # The tray app is a different origin from 127.0.0.1. The bearer is the secret.
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


class _Guard(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if not _host_ok(request):
            return Response("bad host", status_code=403)
        if request.method == "OPTIONS":
            return _cors(Response(status_code=204))
        if not _bearer_ok(request, self.token):
            return _cors(JSONResponse({"error": "unauthorized"}, status_code=401))
        return _cors(await call_next(request))


def _snippet(body: str) -> str:
    text = " ".join(body.split())
    return text if len(text) <= 160 else text[:157] + "…"


def _shell_digest(days: int) -> str:
    # 动态 is a home screen: drop lines that name the CLI or config file.
    kept = []
    for line in weekly_auto_digest(days).splitlines():
        low = line.lower()
        if "memrelay inbox" in low or "review.mode" in low or ".toml" in low:
            continue
        kept.append(line)
    return "\n".join(kept).strip() + "\n"


async def _backend(app: Starlette, cfg: Config):
    existing = getattr(app.state, "backend", None)
    if existing is not None:
        return existing
    from .backends import make_backend

    backend = make_backend(cfg, Vault(cfg.vault))
    try:
        await backend.start()
    except Exception:
        return None
    app.state.backend = backend
    return backend


def build_shell_app(cfg: Config, token: str) -> Starlette:
    vault = Vault(cfg.vault)

    async def health(_request: Request) -> Response:
        return JSONResponse({"ok": True, "version": __version__})

    async def faces(_request: Request) -> Response:
        rows = ensure_default_faces(vault)
        return JSONResponse({"faces": [asdict(row) for row in rows]})

    async def memories(request: Request) -> Response:
        q = (request.query_params.get("q") or "").strip().lower()
        mtype = (request.query_params.get("type") or "").strip()
        try:
            limit = int(request.query_params.get("limit") or 50)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))
        # shortcut: substring scan over markdown, switch to backend.search when the shell needs ranking
        items = []
        for path, note in vault.iter_notes():
            if mtype and str(note.type) != mtype:
                continue
            if q and q not in f"{note.title}\n{note.body}".lower():
                continue
            items.append({
                "id": vault.rel(path),
                "title": note.title,
                "type": note.type,
                "snippet": _snippet(note.body),
                "status": note.status,
            })
            if len(items) >= limit:
                break
        return JSONResponse({"items": items})

    async def memory(request: Request) -> Response:
        rel = request.path_params["note_id"]
        try:
            path = vault.resolve(rel)
        except ValueError:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if not path.is_file() or path.suffix != ".md" or vault.is_hidden(path):
            return JSONResponse({"error": "not_found"}, status_code=404)
        try:
            note = Note.from_markdown(path.read_text(encoding="utf-8"))
        except Exception:
            return JSONResponse({"error": "not_found"}, status_code=404)
        data = note.model_dump(mode="json")
        data["id"] = vault.rel(path)
        data["body"] = note.body
        return JSONResponse(data)

    async def activity(request: Request) -> Response:
        try:
            days = int(request.query_params.get("days") or 7)
        except ValueError:
            days = 7
        days = max(1, min(days, 90))
        since = dt.datetime.now().astimezone() - dt.timedelta(days=days)
        return JSONResponse({"digest": _shell_digest(days), "items": iter_auto(since)})

    async def twin_ask(request: Request) -> Response:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_json"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "bad_json"}, status_code=400)
        question = str(body.get("question") or "").strip()
        if not question:
            return JSONResponse({"error": "question_required"}, status_code=400)
        face_id = str(body.get("face_id") or "self")
        backend = await _backend(request.app, cfg)
        if backend is None:
            return JSONResponse({"error": "backend_unavailable"}, status_code=503)
        ensure_default_faces(vault)
        from .llm import get_llm
        from .twin import answer_as_me

        result = await answer_as_me(
            question[:2000], vault=vault, backend=backend, llm=get_llm(cfg), face_id=face_id,
        )
        return JSONResponse(result)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        yield
        backend = getattr(app.state, "backend", None)
        if backend is not None:
            try:
                await backend.stop()
            except Exception:
                pass

    return Starlette(
        routes=[
            Route("/v1/health", health, methods=["GET"]),
            Route("/v1/faces", faces, methods=["GET"]),
            Route("/v1/twin/ask", twin_ask, methods=["POST"]),
            Route("/v1/memories", memories, methods=["GET"]),
            Route("/v1/memories/{note_id:path}", memory, methods=["GET"]),
            Route("/v1/activity", activity, methods=["GET"]),
        ],
        middleware=[Middleware(_Guard, token=token)],
        lifespan=lifespan,
    )


def serve_shell_api(port: int = 8787, token_file: Path | None = None) -> None:
    import uvicorn

    cfg = Config.load()
    path, token = load_or_create_token(token_file)
    print(f"shell-api token: {path}", flush=True)
    # Bind address is the security boundary; do not accept a host flag.
    uvicorn.run(build_shell_app(cfg, token), host="127.0.0.1", port=port, log_level="warning")
