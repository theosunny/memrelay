from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomlkit

from .base import AgentAdapter, Change, ServerSpec


class CodexAdapter(AgentAdapter):
    """OpenAI Codex (CLI, IDE extension, ChatGPT desktop share it): `$CODEX_HOME/config.toml`,
    default `~/.codex/config.toml`, table `[mcp_servers.<name>]` with command/args/env.

    Sources: https://developers.openai.com/codex/mcp ("Configure with config.toml");
    https://developers.openai.com/codex/config-advanced (CODEX_HOME). Edited with tomlkit so
    comments and formatting in the user's file are preserved.
    """

    id = "codex"
    name = "Codex"
    sources = ("https://developers.openai.com/codex/mcp",)

    def config_path(self) -> Path:
        ch = self.env.environ.get("CODEX_HOME")
        return (Path(ch) if ch else self.env.home / ".codex") / "config.toml"

    def entry(self, spec: ServerSpec) -> dict[str, Any]:
        e: dict[str, Any] = {"command": spec.command, "args": list(spec.args)}
        if spec.env:
            e["env"] = dict(spec.env)
        return e

    def _read(self, path: Path) -> tomlkit.TOMLDocument:
        if not path.exists():
            return tomlkit.document()
        try:
            return tomlkit.parse(path.read_text(encoding="utf-8"))
        except Exception as e:  # tomlkit raises several error types
            raise ValueError(f"{path} is not valid TOML ({e}); refusing to modify it") from e

    def _write(self, path: Path, doc: tomlkit.TOMLDocument) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".memrelay-tmp")
        tmp.write_text(tomlkit.dumps(doc), encoding="utf-8")
        os.replace(tmp, path)

    def installed(self, name: str = "memrelay") -> dict[str, Any] | None:
        p = self.config_path()
        if not p.exists():
            return None
        try:
            servers = self._read(p).get("mcp_servers") or {}
        except ValueError:
            return None
        v = servers.get(name)
        return v.unwrap() if v is not None else None

    def install(self, spec: ServerSpec, dry_run: bool = False) -> Change:
        path = self.config_path()
        doc = self._read(path)
        servers = doc.get("mcp_servers")
        before = servers.get(spec.name).unwrap() if servers and spec.name in servers else None
        after = self.entry(spec)
        if before == after:
            return Change(self.id, path, "noop", before, after, dry_run=dry_run)
        if dry_run:
            return Change(self.id, path, "install", before, after, dry_run=True)
        backup = self._backup(path)
        if servers is None:
            servers = tomlkit.table(is_super_table=True)
            doc["mcp_servers"] = servers
        tbl = tomlkit.table()
        for k, v in after.items():
            tbl[k] = v
        servers[spec.name] = tbl
        self._write(path, doc)
        return Change(self.id, path, "install", before, after, backup=backup)

    def uninstall(self, name: str = "memrelay", dry_run: bool = False) -> Change:
        path = self.config_path()
        if not path.exists():
            return Change(self.id, path, "noop", None, None, dry_run=dry_run)
        doc = self._read(path)
        servers = doc.get("mcp_servers")
        if not servers or name not in servers:
            return Change(self.id, path, "noop", None, None, dry_run=dry_run)
        before = servers[name].unwrap()
        if dry_run:
            return Change(self.id, path, "uninstall", before, None, dry_run=True)
        backup = self._backup(path)
        del servers[name]
        self._write(path, doc)
        return Change(self.id, path, "uninstall", before, None, backup=backup)
