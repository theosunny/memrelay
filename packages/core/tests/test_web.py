from starlette.testclient import TestClient

from memrelay.schema import Note
from memrelay.web import build_app

TOKEN = "tok-123"


def client(inbox, login=True):
    c = TestClient(build_app(inbox, TOKEN), follow_redirects=False)
    if login:
        c.get(f"/?t={TOKEN}")  # first visit sets the session cookie
    return c


def test_requires_token_and_local_host(inbox):
    c = client(inbox, login=False)
    assert c.get("/").status_code == 403
    assert c.get("/?t=wrong").status_code == 403
    assert c.get(f"/?t={TOKEN}", headers={"host": "evil.example"}).status_code == 403
    r = c.get(f"/?t={TOKEN}")
    assert r.status_code == 200 and "收件箱为空" in r.text
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert c.get("/").status_code == 200  # cookie set on first visit


def test_list_escapes_and_approve(inbox, vault):
    rid = inbox.propose(Note(title="<script>x</script>常住城市", body="我常住上海 <b>", source_agent="t")).id
    c = client(inbox)
    r = c.get(f"/?t={TOKEN}")
    assert "&lt;script&gt;" in r.text and "<script>x" not in r.text and "&lt;b&gt;" in r.text
    assert c.post(f"/item/{rid}/approve", data={}).status_code == 403  # no csrf
    anon = client(inbox, login=False)  # csrf alone without the session cookie is refused
    assert anon.post(f"/item/{rid}/approve", data={"csrf": TOKEN}).status_code == 403
    r = c.post(f"/item/{rid}/approve", data={"csrf": TOKEN, "title": "常住城市", "type": "fact"})
    assert r.status_code == 303 and inbox.list() == []
    assert list(vault.root.rglob("常住城市.md"))


def test_detail_edit_and_reject(inbox, vault):
    rid = inbox.propose(Note(title="咖啡", body="喜欢美式")).id
    c = client(inbox)
    r = c.get(f"/item/{rid}?t={TOKEN}")
    assert r.status_code == 200 and "textarea" in r.text and "喜欢美式" in r.text
    assert c.get(f"/item/nope?t={TOKEN}").status_code == 404
    assert c.get(f"/item/..%2Fx?t={TOKEN}").status_code in (404, 405)
    r = c.post(f"/item/{rid}/reject", data={"csrf": TOKEN, "reason": "不准确"})
    assert r.status_code == 303
    rejected = (vault.root / "rejected" / f"{rid}.md").read_text(encoding="utf-8")
    assert "不准确" in rejected
    assert c.post(f"/item/{rid}/reject", data={"csrf": TOKEN}).status_code == 400


def test_approve_with_body_edit(inbox, vault):
    rid = inbox.propose(Note(title="编辑器", body="vim")).id
    c = client(inbox)
    c.post(f"/item/{rid}/approve", data={"csrf": TOKEN, "body": "我用 Neovim", "visibility": "work"})
    (p,) = list(vault.root.rglob("编辑器.md"))
    t = p.read_text(encoding="utf-8")
    assert "我用 Neovim" in t and "visibility: work" in t


def test_invalid_edit_is_400(inbox):
    rid = inbox.propose(Note(title="x", body="y")).id
    r = client(inbox).post(f"/item/{rid}/approve", data={"csrf": TOKEN, "type": "bogus"})
    assert r.status_code == 400 and inbox.list()
