"""Minimal local web review UI for the inbox (`memrelay review --web`).

Security model: binds to 127.0.0.1 only; every request needs a random per-run token
(first visit via `?t=<token>`, then an HttpOnly SameSite=Strict cookie); every POST also
needs the token as a form field (CSRF); the Host header must be localhost (DNS-rebinding
guard). All note content is HTML-escaped. No JavaScript, no external assets.
"""

from __future__ import annotations

import html
import secrets
from urllib.parse import parse_qs, quote

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from .inbox import Inbox
from .schema import MemoryType, Visibility

COOKIE = "memrelay_review"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "testserver"}
CSS = """body{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:2em auto;padding:0 1em;color:#222}
.card{border:1px solid #ddd;border-radius:8px;padding:.8em 1em;margin:.8em 0}
.meta{color:#666;font-size:13px}.flag{background:#fde68a;border-radius:4px;padding:0 .3em;margin-right:.3em}
pre{white-space:pre-wrap;background:#f6f6f6;padding:.6em;border-radius:6px}
button{margin-right:.4em}input[type=text],textarea{width:100%;box-sizing:border-box}textarea{height:8em}"""


def e(x) -> str:
    return html.escape(str(x), quote=True)


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html lang=zh><meta charset=utf-8><title>{e(title)}</title>"
        f"<meta name=viewport content='width=device-width'><style>{CSS}</style>"
        f"<h1>MemRelay · 记忆收件箱 / Inbox</h1>{body}</html>",
        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
                 "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"})


def build_app(inbox: Inbox, token: str | None = None) -> Starlette:
    token = token or secrets.token_urlsafe(24)

    def guard(req: Request) -> Response | None:
        host = (req.headers.get("host") or "").rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            return Response("bad host", status_code=403)
        given = req.query_params.get("t") or req.cookies.get(COOKIE) or ""
        if not secrets.compare_digest(given, token):
            return Response("missing or wrong token; open the URL printed by `memrelay review --web`",
                            status_code=403)
        return None

    def with_cookie(resp: Response) -> Response:
        resp.set_cookie(COOKIE, token, httponly=True, samesite="strict")
        return resp

    async def form(req: Request) -> dict[str, str] | None:
        data = {k: v[0] for k, v in parse_qs((await req.body()).decode("utf-8")).items()}
        return data if secrets.compare_digest(data.get("csrf", ""), token) else None

    def note_card(iid: str, n, full: bool = False) -> str:
        flags = "".join(f"<span class=flag>{e(f)}</span>" for f in n.flags)
        body = e(n.body if full else (n.body[:280] + ("…" if len(n.body) > 280 else "")))
        hidden = f"<input type=hidden name=csrf value='{e(token)}'>"
        return (f"<div class=card><b>[{e(n.type)}] {e(n.title)}</b> {flags}"
                f"<div class=meta>{e(iid)} · from {e(n.source_agent)} / {e(n.source_channel)} · "
                f"conf {e(n.confidence)} · {e(n.visibility)}"
                + (f" · ref {e(n.source_ref)}" if full and n.source_ref else "") + "</div>"
                f"<pre>{body}</pre>"
                f"<form method=post action='/item/{quote(iid)}/approve' style=display:inline>{hidden}"
                f"<button>✔ 通过 Approve</button></form>"
                f"<form method=post action='/item/{quote(iid)}/reject' style=display:inline>{hidden}"
                f"<button>✘ 拒绝 Reject</button></form>"
                + ("" if full else f" <a href='/item/{quote(iid)}'>编辑 Edit</a>") + "</div>")

    async def index(req: Request) -> Response:
        if (bad := guard(req)) is not None:
            return bad
        items = inbox.list()
        msg = e(req.query_params.get("msg", ""))
        body = (f"<p class=meta>{msg}</p>" if msg else "") + (
            "".join(note_card(i, n) for i, n in items) if items else "<p>收件箱为空 / Inbox empty.</p>")
        return with_cookie(page("MemRelay inbox", f"<p>{len(items)} 条待审核 / pending</p>{body}"))

    async def item(req: Request) -> Response:
        if (bad := guard(req)) is not None:
            return bad
        iid = req.path_params["iid"]
        try:
            n = inbox.get(iid)
        except (KeyError, ValueError):
            return Response("not found", status_code=404)
        types = "".join(f"<option{' selected' if t.value == str(n.type) else ''}>{e(t.value)}</option>" for t in MemoryType)
        vis = "".join(f"<option{' selected' if v.value == str(n.visibility) else ''}>{e(v.value)}</option>" for v in Visibility)
        edit = (f"<div class=card><h3>编辑后通过 / Edit & approve</h3>"
                f"<form method=post action='/item/{quote(iid)}/approve'>"
                f"<input type=hidden name=csrf value='{e(token)}'>"
                f"<label>标题 Title<input type=text name=title value='{e(n.title)}'></label>"
                f"<label>类型 Type <select name=type>{types}</select></label> "
                f"<label>可见性 Visibility <select name=visibility>{vis}</select></label>"
                f"<label>正文 Body<textarea name=body>{e(n.body)}</textarea></label>"
                f"<button>✔ 保存并通过 Save & approve</button></form>"
                f"<form method=post action='/item/{quote(iid)}/reject'>"
                f"<input type=hidden name=csrf value='{e(token)}'>"
                f"<label>拒绝原因 Reason<input type=text name=reason></label><button>✘ 拒绝 Reject</button>"
                f"</form></div>")
        return with_cookie(page(n.title, note_card(iid, n, full=True) + edit + "<a href='/'>← 返回 Back</a>"))

    async def act(req: Request) -> Response:
        if (bad := guard(req)) is not None:
            return bad
        data = await form(req)
        if data is None:
            return Response("bad csrf token", status_code=403)
        iid, action = req.path_params["iid"], req.path_params["action"]
        try:
            if action == "approve":
                edits = {k: data[k] for k in ("title", "type", "visibility", "body") if data.get(k)}
                inbox.approve(iid, edits=edits)
            elif action == "reject":
                inbox.reject(iid, data.get("reason") or None)
            else:
                return Response("unknown action", status_code=404)
        except (KeyError, ValueError) as ex:
            return Response(f"error: {e(ex)}", status_code=400)
        return RedirectResponse(f"/?msg={quote(f'{action}d {iid}')}", status_code=303)

    app = Starlette(routes=[
        Route("/", index), Route("/item/{iid}", item),
        Route("/item/{iid}/{action}", act, methods=["POST"]),
    ])
    app.state.token = token
    return app


def serve(inbox: Inbox, port: int = 0, open_browser: bool = True, echo=print) -> None:
    import socket
    import webbrowser

    import uvicorn

    if port == 0:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    app = build_app(inbox)
    url = f"http://127.0.0.1:{port}/?t={app.state.token}"
    echo(f"Review UI / 审核界面: {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
