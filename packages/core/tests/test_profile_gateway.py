import datetime as dt
import json

import pytest
from fastmcp import Client

from memrelay.backend import LocalBackend
from memrelay.gateway import TOOL_WHITELIST, build_server
from memrelay.profile import build_profile, export_plain, profile_path, write_profile
from memrelay.schema import Note


def add(vault, folder, name, **kw):
    kw.setdefault("status", "active")
    kw.setdefault("confidence", 0.9)
    kw.setdefault("last_confirmed", dt.date.today())
    n = Note(**kw)
    p = vault.root / folder / f"{name}.md"
    p.write_text(n.to_markdown(), encoding="utf-8")
    return p


@pytest.fixture
def seeded(vault, inbox):
    add(vault, "facts", "city", title="常住城市", type="fact", body="我常住上海", importance=8)
    add(vault, "preferences", "reply", title="回复风格", type="preference", body="喜欢简洁的中文回复")
    add(vault, "projects", "memrelay", title="MemRelay", type="project", body="在做跨智能体记忆项目 MemRelay")
    add(vault, "facts", "secret", title="银行卡", type="fact", body="上海 secret", sensitivity="secret")
    add(vault, "facts", "old", title="旧城市", type="fact", body="我常住北京",
        valid_to=dt.date(2020, 1, 1))
    add(vault, "facts", "proposed", title="未审核", type="fact", body="上海 proposed", status="proposed")
    inbox.propose(Note(title="收件箱里的上海", body="上海 inbox item"))
    return vault


def test_profile_build(seeded):
    text = build_profile(seeded)
    assert "我常住上海" in text and "喜欢简洁的中文回复" in text and "MemRelay" in text
    assert "secret" not in text and "北京" not in text and "proposed" not in text.split("---")[2]
    assert "[[facts/city]]" in text
    plain = export_plain(text)
    assert "[[" not in plain and "title:" not in plain
    p = write_profile(seeded, text)
    assert Note.from_markdown(p.read_text(encoding="utf-8")).type == "profile"


def test_profile_lock(seeded):
    profile_path(seeded).write_text("# my own profile\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        write_profile(seeded, build_profile(seeded))


def _data(r):
    if r.data is not None:
        return r.data
    return json.loads(r.content[0].text)


async def test_gateway_whitelist_and_policy(cfg, seeded):
    server = build_server(cfg, backend=LocalBackend(seeded))
    async with Client(server) as c:
        names = sorted(t.name for t in await c.list_tools())
        assert names == sorted(TOOL_WHITELIST)

        hits = _data(await c.call_tool("recall", {"query": "上海"}))
        ids = [h["id"] for h in hits]
        assert ids == ["facts/city.md"], ids  # no secret/expired/proposed/inbox

        assert _data(await c.call_tool("recall", {"query": "上海", "types": ["preference"]})) == []

        full = _data(await c.call_tool("read_memory", {"id": "facts/city.md"}))
        assert full["content"] == "我常住上海" and full["metadata"]["status"] == "active"
        for bad in ["facts/secret.md", "../config/config.toml", "inbox", "facts/proposed.md"]:
            assert "error" in _data(await c.call_tool("read_memory", {"id": bad}))
        inbox_file = next((seeded.root / "inbox").glob("*.md")).relative_to(seeded.root).as_posix()
        assert "error" in _data(await c.call_tool("read_memory", {"id": inbox_file}))

        recent_ids = [x["id"] for x in _data(await c.call_tool("recent", {"days": 3}))]
        assert set(recent_ids) == {"facts/city.md", "preferences/reply.md", "projects/memrelay.md"}

        prof = (await c.call_tool("get_profile", {})).content[0].text
        assert "尚未生成" in prof

        r = _data(await c.call_tool("propose_memory", {
            "title": "喜欢深色主题", "content": "用户喜欢深色主题", "type": "preference",
            "evidence": "我喜欢深色主题", "confidence": 1.0, "source_agent": "cursor"}))
        assert r["status"] == "pending_review"
        note = Note.from_markdown((seeded.root / "inbox" / f"{r['id']}.md").read_text(encoding="utf-8"))
        assert note.confidence == 0.9 and note.source_channel == "mcp" and "证据" in note.body
        # proposals are not recallable until approved
        assert _data(await c.call_tool("recall", {"query": "深色主题"})) == []

        r = _data(await c.call_tool("propose_memory", {"title": "x", "content": "y", "type": "profile"}))
        assert "error" in r


def test_gateway_never_exposes_basic_memory_write_tools():
    from memrelay import gateway

    src = open(gateway.__file__, encoding="utf-8").read()
    for forbidden in ("write_note", "delete_note", "edit_note", "move_note"):
        assert forbidden not in src
