"""Dependency-free keyword search over the vault (tests, offline fallback)."""

from __future__ import annotations

import re

from ..schema import Note
from ..vault import Vault


def tokens(text: str) -> set[str]:
    text = text.lower()
    words = set(re.findall(r"[a-z0-9_]{2,}", text))
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    words |= {a + b for a, b in zip(cjk, cjk[1:], strict=False)} | set(cjk if len(cjk) == 1 else [])
    return words


# Historical name used by consolidate / twin.
_tokens = tokens


class LocalBackend:
    name = "local"

    def __init__(self, vault: Vault):
        self.vault = vault

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def search(self, query: str, limit: int = 10) -> list[str]:
        q = tokens(query)
        scored = []
        for path, note in self.vault.iter_notes():
            t = tokens(f"{note.title} {note.title} {note.body} {' '.join(note.tags)}")
            s = len(q & t)
            if s:
                scored.append((s, self.vault.rel(path)))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [p for _, p in scored[:limit]]

    async def get_note(self, note_id: str) -> Note | None:
        try:
            p = self.vault.resolve(note_id)
        except ValueError:
            return None
        if not p.is_file() or p.suffix != ".md" or self.vault.is_hidden(p):
            return None
        try:
            return Note.from_markdown(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def remember(self, note: Note, note_id: str | None = None) -> str:
        # Vault file already written by inbox.approve; id is the relative path.
        if note_id:
            return note_id
        raise ValueError("LocalBackend.remember requires note_id (vault-relative path)")
