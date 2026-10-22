"""Basic Memory backend: search via `basic-memory mcp` stdio; notes live in the vault files.

Basic Memory is AGPL-3.0 — launched as a *separate program*, never imported or bundled.
CLI flags verified against basic-memory 0.23.2: `basic-memory mcp --project NAME`,
`basic-memory project add NAME PATH`, state via BASIC_MEMORY_CONFIG_DIR.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path

from ..config import Config
from ..schema import Note
from ..vault import Vault
from .local import LocalBackend

log = logging.getLogger(__name__)


class BasicMemoryBackend:
    name = "basic_memory"

    def __init__(self, cfg: Config, vault: Vault):
        self.cfg, self.vault = cfg, vault
        self._client = None
        self._stack = None
        self._files = LocalBackend(vault)  # get_note / remember stay file-based

    def env(self) -> dict[str, str]:
        return self._env()

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        # Basic Memory switches to "test mode" (no file sync) when it sees this variable
        # (basic_memory/config_models.py); it must not leak from our own test runs.
        env.pop("PYTEST_CURRENT_TEST", None)
        from ..hf import resolve_endpoint

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

    async def search(self, query: str, limit: int = 10) -> list[str]:
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

    async def get_note(self, note_id: str) -> Note | None:
        return await self._files.get_note(note_id)

    async def remember(self, note: Note, note_id: str | None = None) -> str:
        # Markdown already on disk after inbox.approve; BM indexes on its own sync cycle.
        return await self._files.remember(note, note_id)
