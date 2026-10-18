"""End-to-end with the real Basic Memory executable (run: pytest -m integration)."""

import asyncio
import json
import shutil

import pytest
from fastmcp import Client

from memrelay.backend import BasicMemoryBackend
from memrelay.config import Config
from memrelay.gateway import build_server
from memrelay.inbox import Inbox
from memrelay.schema import Note
from memrelay.vault import Vault

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("basic-memory") is None, reason="basic-memory not installed"),
]


async def test_gateway_over_real_basic_memory(home):
    cfg = Config(vault=home / "vault", backend="basic-memory", bm_project="memrelay-test")
    vault = Vault(cfg.vault)
    vault.init()
    inbox = Inbox(vault)
    r = inbox.propose(Note(title="常住城市", body="我常住上海，时区 Asia/Shanghai", source_agent="t"))
    inbox.approve(r.id)
    inbox.propose(Note(title="未审核的上海笔记", body="上海 这条还在收件箱"))

    backend = BasicMemoryBackend(cfg, vault)
    server = build_server(cfg, backend=backend)
    async with Client(server) as c:
        hits = []
        for _ in range(20):  # Basic Memory indexes the vault on startup
            res = await c.call_tool("recall", {"query": "上海"})
            hits = res.data if res.data is not None else json.loads(res.content[0].text)
            if hits:
                break
            await asyncio.sleep(1)
        assert [h["id"] for h in hits] == ["facts/常住城市.md"]
    # Basic Memory state was isolated under MemRelay's data dir
    assert (home / "data" / "basic-memory").is_dir()


async def test_memrelay_serve_over_stdio_like_an_agent(home):
    """Launch `python -m memrelay serve` exactly as the connect adapters configure it."""
    import os

    from fastmcp.client.transports import StdioTransport

    from memrelay.adapters import ServerSpec

    Config(vault=home / "vault", backend="basic-memory", bm_project="memrelay-serve").save()
    spec = ServerSpec()
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    env["MEMRELAY_HOME"] = str(home)
    t = StdioTransport(command=spec.command, args=spec.args, env=env)
    async with Client(t) as c:
        names = sorted(x.name for x in await c.list_tools())
        from memrelay.gateway import TOOL_WHITELIST
        assert names == sorted(TOOL_WHITELIST)
        r = await c.call_tool("propose_memory", {"title": "t", "content": "我喜欢冷萃咖啡",
                                                 "type": "preference"})
        assert r.data["status"] == "pending_review"
    assert spec.args == ["serve"]  # the installed console script, as packaged
    assert len(list((home / "vault" / "inbox").glob("*.md"))) == 1


def test_export_archive_with_real_basic_memory(home, tmp_path):
    import zipfile

    from test_importers import CLAUDE

    from memrelay.extract.stub import StubExtractor
    from memrelay.importers import archive_with_basic_memory, run_import

    cfg = Config(vault=home / "vault", backend="basic-memory", bm_project="memrelay-import-test")
    vault = Vault(cfg.vault)
    vault.init()
    bm = BasicMemoryBackend(cfg, vault)
    bm.ensure_project()
    env = bm.env()
    p = tmp_path / "claude.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("conversations.json", json.dumps(CLAUDE, ensure_ascii=False))
    rep = run_import(p, StubExtractor(), Inbox(vault),
                     archive=lambda k, raw: archive_with_basic_memory(k, raw, cfg.bm_command, env))
    assert rep.archived, rep.archive_error
    assert list((vault.root / "sources" / "claude").rglob("*.md"))
