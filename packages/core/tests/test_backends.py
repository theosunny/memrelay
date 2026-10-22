"""MemoryBackend interface, BM/local behaviour, OpenViking stub policy."""

from __future__ import annotations

import pytest

from memrelay.backends import (
    BasicMemoryBackend,
    LocalBackend,
    MemoryBackend,
    OpenVikingBackend,
    make_backend,
    normalize_backend,
)
from memrelay.backends.openviking import FORBIDDEN_OV_TOOLS
from memrelay.config import Config
from memrelay.schema import Note


def put(vault, rel, **kw):
    kw.setdefault("status", "active")
    kw.setdefault("confidence", 0.9)
    p = vault.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    n = Note(title=kw.pop("title", "t"), body=kw.pop("body", "我常住上海"), **kw)
    p.write_text(n.to_markdown(), encoding="utf-8")
    return p


def test_normalize_and_make_backend(cfg, vault):
    assert normalize_backend("basic-memory") == "basic_memory"
    assert normalize_backend("openviking") == "openviking"
    assert normalize_backend("ov") == "openviking"
    cfg.backend = "local"
    b = make_backend(cfg, vault)
    assert isinstance(b, LocalBackend) and isinstance(b, MemoryBackend)
    cfg.backend = "openviking"
    b = make_backend(cfg, vault)
    assert isinstance(b, OpenVikingBackend) and b.name == "openviking"


async def test_local_backend_search_get_remember(vault):
    put(vault, "facts/city.md", title="常住城市", body="我常住上海")
    put(vault, "preferences/x.md", title="包管理器", body="我用 pnpm", type="preference")
    b = LocalBackend(vault)
    await b.start()
    hits = await b.search("上海", limit=5)
    assert hits[0] == "facts/city.md"
    n = await b.get_note("facts/city.md")
    assert n and "上海" in n.body
    assert await b.get_note("facts/nope.md") is None
    assert await b.get_note("../outside.md") is None
    assert await b.remember(n, "facts/city.md") == "facts/city.md"
    with pytest.raises(ValueError):
        await b.remember(n)
    await b.stop()


async def test_basic_memory_class_implements_protocol(cfg, vault):
    """Structural check without spawning basic-memory (integration tests cover that)."""
    b = BasicMemoryBackend(cfg, vault)
    assert isinstance(b, MemoryBackend)
    assert b.name == "basic_memory"
    put(vault, "facts/city.md", title="常住城市", body="我常住上海")
    # get_note / remember work without start (file layer)
    n = await b.get_note("facts/city.md")
    assert n and await b.remember(n, "facts/city.md") == "facts/city.md"
    with pytest.raises(RuntimeError, match="not started"):
        await b.search("上海")


async def test_openviking_stub_refuses_forget_and_delete(cfg, vault):
    cfg.backend = "openviking"
    cfg.openviking_base_url = "https://ov.example"
    b = OpenVikingBackend(cfg, vault)
    assert b.base_url == "https://ov.example"
    with pytest.raises(RuntimeError, match="not started"):
        await b.search("x")
    await b.start()
    assert await b.search("anything") == []
    assert await b.get_note("viking://user/u/memories/profile.md") is None
    note = Note(title="偏好", body="喜欢简洁回复", type="preference")
    assert (await b.remember(note)).startswith("openviking:pending/")
    assert await b.remember(note, "viking://user/u/memories/preferences/x.md") == (
        "viking://user/u/memories/preferences/x.md"
    )
    with pytest.raises(PermissionError, match="forget"):
        await b.forget("viking://anything")
    with pytest.raises(PermissionError, match="forget"):
        await b.delete("viking://anything")
    for tool in FORBIDDEN_OV_TOOLS:
        with pytest.raises(PermissionError, match="forbids delete/forget"):
            b.call_tool(tool, uri="viking://x")
    with pytest.raises(NotImplementedError, match="not wired"):
        b.call_tool("search", query="hi")
    await b.stop()
    with pytest.raises(RuntimeError):
        await b.remember(note, "x")


def test_config_roundtrip_openviking(home):
    c = Config(backend="openviking", openviking_base_url="https://ov.example/mcp")
    c.save()
    c2 = Config.load()
    assert c2.backend == "openviking" and c2.openviking_base_url.endswith("/mcp")
