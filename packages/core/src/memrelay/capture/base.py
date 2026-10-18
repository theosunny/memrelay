"""Capture sources: read-only, incremental readers of local agent history."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..config import data_dir


@dataclass
class Message:
    role: str  # "user" | "assistant"
    text: str
    timestamp: str | None
    session_id: str | None
    cwd: str | None
    source_ref: str  # file path + line number, kept as provenance


class CaptureSource(Protocol):
    id: str

    def iter_new_messages(self, state: CursorState) -> Iterator[Message]: ...


class CursorState:
    """Per-device byte offsets per file, so repeated runs never re-read old lines."""

    def __init__(self, source_id: str, path: Path | None = None):
        self.path = path or data_dir() / "state" / f"capture-{source_id}.json"
        self.data: dict[str, dict] = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, file: Path) -> dict:
        return self.data.get(str(file), {"offset": 0, "line": 0, "size": 0})

    def set(self, file: Path, offset: int, line: int, size: int) -> None:
        self.data[str(file)] = {"offset": offset, "line": line, "size": size}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        tmp.replace(self.path)
