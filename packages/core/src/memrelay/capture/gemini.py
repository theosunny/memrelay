"""Gemini CLI chat sessions.

Location: `~/.gemini/tmp/<project_hash>/chats/session-*.jsonl`.
Sources: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/session-management.md
("Sessions are stored in ~/.gemini/tmp/<project_hash>/chats/"); record shape from
packages/core/src/services/chatRecordingService.ts and chatRecordingTypes.ts: message
records `{id, timestamp, type: 'user'|'gemini'|'info'|..., content: string | Part[]}`;
other lines are metadata/patches (`$set`, rewinds) and are skipped. Older versions wrote a
single `session-*.json`; those are not read (v0.1).
"""

from __future__ import annotations

from pathlib import Path

from .jsonl import JsonlTranscriptSource, text_of_parts


def default_root(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".gemini" / "tmp"


class GeminiCliSource(JsonlTranscriptSource):
    id = "gemini-cli"

    def __init__(self, root: Path | None = None):
        self.root = root or default_root()
        self._seen: set[str] = set()

    def files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*/chats/**/session-*.jsonl"))

    def parse(self, obj: dict) -> tuple[str, str] | None:
        kind = obj.get("type")
        if kind not in ("user", "gemini") or "id" not in obj:
            return None
        key = f"{kind}:{obj['id']}"
        if key in self._seen:  # re-written records for the same message id
            return None
        text = text_of_parts(obj.get("content")).strip()
        if not text:
            return None
        self._seen.add(key)
        return ("user" if kind == "user" else "assistant"), text
