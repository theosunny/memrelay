"""Agent adapter interface + JSON `mcpServers` config writer with backup/rollback.

Every write: (1) parse existing file (refuse if it is not valid JSON), (2) copy it to
<data_dir>/backups/<adapter>/<timestamp>.json (or record that it was absent), (3) change only
`mcpServers.<name>`, (4) write atomically. `rollback()` restores the latest backup.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import data_dir


def _default_command() -> tuple[str, list[str]]:
    """Prefer the installed `memrelay` console script (absolute path, so GUI apps that do not
    inherit the shell PATH can still launch it). Symlinks are kept, not resolved: e.g. the
    `uv tool` / pipx shim in ~/.local/bin stays valid across upgrades. Fallback: `<python> -m memrelay`."""
    exe = shutil.which("memrelay")
    if exe:
        return str(Path(exe).absolute()), ["serve"]
    return sys.executable, ["-m", "memrelay", "serve"]


@dataclass
class ServerSpec:
    name: str = "memrelay"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.command:
            self.command, default_args = _default_command()
            if not self.args:
                self.args = default_args


@dataclass
class Change:
    adapter: str
    path: Path
    action: str  # "install" | "uninstall" | "noop"
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    backup: Path | None = None
    dry_run: bool = False
    note: str | None = None


@dataclass
class Env:
    """Injectable OS environment so paths can be tested for all three platforms."""

    platform: str = field(default_factory=lambda: sys.platform)
    home: Path = field(default_factory=Path.home)
    environ: dict[str, str] = field(default_factory=lambda: dict(os.environ))

    @property
    def os(self) -> str:
        if self.platform.startswith("win"):
            return "windows"
        if self.platform == "darwin":
            return "macos"
        return "linux"


class AgentAdapter(ABC):
    id: str
    name: str
    sources: tuple[str, ...] = ()  # where the config location is documented
    warning: str | None = None

    def __init__(self, env: Env | None = None):
        self.env = env or Env()

    @abstractmethod
    def config_path(self) -> Path | None: ...

    def detect(self) -> bool:
        p = self.config_path()
        return bool(p and (p.exists() or p.parent.exists()))

    @abstractmethod
    def install(self, spec: ServerSpec, dry_run: bool = False) -> Change: ...

    @abstractmethod
    def uninstall(self, name: str = "memrelay", dry_run: bool = False) -> Change: ...

    # ---------------------------------------------------------------- backups
    def backup_dir(self) -> Path:
        return data_dir() / "backups" / self.id

    def _backup(self, path: Path) -> Path:
        d = self.backup_dir()
        d.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
        if path.exists():
            dest = d / f"{stamp}.bak"
            shutil.copy2(path, dest)
        else:
            dest = d / f"{stamp}.absent"
            dest.write_text(str(path), encoding="utf-8")
        return dest

    def backups(self) -> list[Path]:
        d = self.backup_dir()
        return sorted(d.iterdir()) if d.exists() else []

    def rollback(self) -> Path | None:
        """Restore the most recent backup; returns the backup used (None if none)."""
        items = self.backups()
        if not items:
            return None
        last = items[-1]
        path = self.config_path()
        assert path is not None
        if last.suffix == ".absent":
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(last, path)
        last.unlink()
        return last


class JsonMcpAdapter(AgentAdapter):
    """Clients whose config is a JSON file with a top-level `mcpServers` object."""

    def entry(self, spec: ServerSpec) -> dict[str, Any]:
        e: dict[str, Any] = {"command": spec.command, "args": list(spec.args)}
        if spec.env:
            e["env"] = dict(spec.env)
        return e

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists() or path.stat().st_size == 0:
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{path} is not valid JSON ({e}); refusing to modify it") from e
        if not isinstance(data, dict):
            raise ValueError(f"{path}: top-level JSON must be an object")
        return data

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".memrelay-tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def install(self, spec: ServerSpec, dry_run: bool = False) -> Change:
        path = self.config_path()
        if path is None:
            raise RuntimeError(f"{self.name} is not supported on {self.env.os}")
        data = self._read(path)
        before = (data.get("mcpServers") or {}).get(spec.name)
        after = self.entry(spec)
        if before == after:
            return Change(self.id, path, "noop", before, after, dry_run=dry_run, note=self.warning)
        if dry_run:
            return Change(self.id, path, "install", before, after, dry_run=True, note=self.warning)
        backup = self._backup(path)
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
        servers[spec.name] = after
        data["mcpServers"] = servers
        self._write(path, data)
        return Change(self.id, path, "install", before, after, backup=backup, note=self.warning)

    def uninstall(self, name: str = "memrelay", dry_run: bool = False) -> Change:
        path = self.config_path()
        if path is None or not path.exists():
            return Change(self.id, path or Path(), "noop", None, None, dry_run=dry_run)
        data = self._read(path)
        servers = data.get("mcpServers") or {}
        if name not in servers:
            return Change(self.id, path, "noop", None, None, dry_run=dry_run)
        before = servers[name]
        if dry_run:
            return Change(self.id, path, "uninstall", before, None, dry_run=True)
        backup = self._backup(path)
        del servers[name]
        data["mcpServers"] = servers
        self._write(path, data)
        return Change(self.id, path, "uninstall", before, None, backup=backup)

    def installed(self, name: str = "memrelay") -> dict[str, Any] | None:
        path = self.config_path()
        if not path or not path.exists():
            return None
        try:
            return (self._read(path).get("mcpServers") or {}).get(name)
        except ValueError:
            return None
