"""Search backends. Basic Memory does indexing/search; MemRelay applies policy on the files.

The Basic Memory backend launches `basic-memory mcp --project <name>` as a *separate program*
over MCP stdio (no import, no bundling — Basic Memory is AGPL-3.0, MemRelay is Apache-2.0).
CLI flags verified against basic-memory 0.23.2: `basic-memory mcp --transport stdio
--project NAME`, `basic-memory project add NAME PATH`, state dir via BASIC_MEMORY_CONFIG_DIR
(src/basic_memory/config_models.py::resolve_data_dir).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from .config import Config
from .vault import Vault

log = logging.getLogger(__name__)


class SearchBackend(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def search(self, query: str, limit: int) -> list[str]:
        """Return vault-relative file paths, best match first (unfiltered)."""
        ...


def _tokens(text: str) -> set[str]:
    text = text.lower()
    words = set(re.findall(r"[a-z0-9_]{2,}", text))
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    words |= {a + b for a, b in zip(cjk, cjk[1:], strict=False)} | set(cjk if len(cjk) == 1 else [])
    return words


class LocalBackend:
    """Dependency-free keyword search over the vault (tests, offline fallback)."""

    def __init__(self, vault: Vault):
        self.vault = vault

    async def start(self) -> None:  # noqa: D401
        return None

    async def stop(self) -> None:
        return None

    async def search(self, query: str, limit: int) -> list[str]:
        q = _tokens(query)
        scored = []
        for path, note in self.vault.iter_notes():
            t = _tokens(f"{note.title} {note.title} {note.body} {' '.join(note.tags)}")
            s = len(q & t)
            if s:
                scored.append((s, self.vault.rel(path)))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [p for _, p in scored[:limit]]


class BasicMemoryBackend:
    def __init__(self, cfg: Config, vault: Vault):
        self.cfg, self.vault = cfg, vault
        self._client = None
        self._stack = None

    def env(self) -> dict[str, str]:
        return self._env()

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        # Basic Memory switches to "test mode" (no file sync) when it sees this variable
        # (basic_memory/config_models.py); it must not leak from our own test runs.
        env.pop("PYTEST_CURRENT_TEST", None)
        from .hf import resolve_endpoint

        hf = resolve_endpoint(self.cfg.hf_endpoint, env)
        if hf:
            env["HF_ENDPOINT"] = hf
        d = self.cfg.resolved_bm_config_dir()
        if d:
            d.mkdir(parents=True, exist_ok=True)
            env["BASIC_MEMORY_CONFIG_DIR"] = str(d)
        return env

    @staticmethod
    def available(cfg: Config) -> bool:
        return shutil.which(cfg.bm_command[0]) is not None

    def ensure_project(self) -> None:
        cmd = [*self.cfg.bm_command, "project", "add", self.cfg.bm_project, str(self.vault.root)]
        env = self._env()
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).lower()
        if r.returncode != 0 and "exist" not in out:
            raise RuntimeError(f"basic-memory project add failed: {r.stdout}{r.stderr}")
        # Make it the default project inside MemRelay's isolated Basic Memory config, so
        # project-less commands such as `basic-memory import ...` land in our vault.
        if self.cfg.resolved_bm_config_dir() is not None:
            subprocess.run([*self.cfg.bm_command, "project", "default", self.cfg.bm_project],
                           env=env, capture_output=True, text=True, timeout=120)

    async def start(self) -> None:
        from contextlib import AsyncExitStack

        from fastmcp import Client
        from fastmcp.client.transports import StdioTransport

        await asyncio.to_thread(self.ensure_project)
        transport = StdioTransport(
            command=self.cfg.bm_command[0],
            args=[*self.cfg.bm_command[1:], "mcp", "--project", self.cfg.bm_project],
            env=self._env(),
        )
        self._stack = AsyncExitStack()
        self._client = await self._stack.enter_async_context(Client(transport))

    async def stop(self) -> None:
        if self._stack:
            await self._stack.aclose()
        self._client = self._stack = None

    async def search(self, query: str, limit: int) -> list[str]:
        if self._client is None:
            raise RuntimeError("backend not started")
        r = await self._client.call_tool(
            "search_notes",
            {"query": query, "output_format": "json", "page_size": max(limit * 3, 10)},
        )
        data = r.data if isinstance(r.data, dict) else {}
        out: list[str] = []
        for item in data.get("results", []):
            fp = item.get("file_path")
            if fp and fp not in out:
                out.append(Path(fp).as_posix())
        return out


def make_backend(cfg: Config, vault: Vault) -> SearchBackend:
    if cfg.backend == "basic-memory":
        if BasicMemoryBackend.available(cfg):
            return BasicMemoryBackend(cfg, vault)
        log.warning("basic-memory not found on PATH; falling back to local keyword search")
    return LocalBackend(vault)
