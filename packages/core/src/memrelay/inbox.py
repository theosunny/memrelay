"""Review queue: every agent/capture write lands here; only a human moves it into the vault."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from .sanitize import injection_flags, redact
from .schema import Note, Sensitivity, Status, slugify
from .vault import Vault


@dataclass
class ProposeResult:
    id: str
    path: Path
    duplicate_of: str | None = None
    redacted: list[str] | None = None
    flags: list[str] | None = None


class Inbox:
    def __init__(self, vault: Vault):
        self.vault = vault
        vault.inbox.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ write
    def propose(self, note: Note) -> ProposeResult:
        body, kinds = redact(note.body)
        title, tkinds = redact(note.title)
        kinds = sorted(set(kinds + tkinds))
        flags = sorted(set(note.flags + injection_flags(f"{note.title}\n{note.body}")))
        if kinds:
            flags = sorted(set(flags + ["redacted"]))
        note = note.model_copy(
            update={
                "title": title,
                "body": body,
                "status": Status.proposed.value,
                "flags": flags,
                "sensitivity": Sensitivity.secret.value if kinds else note.sensitivity,
            }
        )
        fp = note.fingerprint()
        for path, existing in self.vault.iter_notes(include_hidden=True):
            rel = self.vault.rel(path)
            if rel.startswith(("rejected/", "archive/")):
                continue
            if existing.fingerprint() == fp:
                return ProposeResult(id=path.stem, path=path, duplicate_of=rel)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{stamp}-{slugify(note.title, 40)}"
        path = self.vault.inbox / f"{base}.md"
        n = 1
        while path.exists():
            n += 1
            path = self.vault.inbox / f"{base}-{n}.md"
        path.write_text(note.to_markdown(), encoding="utf-8")
        return ProposeResult(id=path.stem, path=path, redacted=kinds or None, flags=flags or None)

    # ------------------------------------------------------------------ read
    def list(self) -> list[tuple[str, Note]]:
        out = []
        for p in sorted(self.vault.inbox.glob("*.md")):
            try:
                out.append((p.stem, Note.from_markdown(p.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return out

    def _path(self, item_id: str) -> Path:
        if "/" in item_id or "\\" in item_id or item_id.startswith("."):
            raise ValueError(f"invalid inbox id: {item_id!r}")
        p = self.vault.inbox / f"{item_id}.md"
        if not p.exists():
            raise KeyError(item_id)
        return p

    def get(self, item_id: str) -> Note:
        return Note.from_markdown(self._path(item_id).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ review
    def approve(self, item_id: str, *, edits: dict | None = None) -> Path:
        src = self._path(item_id)
        note = Note.from_markdown(src.read_text(encoding="utf-8"))
        update = {"status": Status.active.value, "last_confirmed": dt.date.today()}
        update.update(edits or {})
        note = Note(**{**note.model_dump(), **update, "body": update.get("body", note.body)})
        folder = self.vault.folder_for(note.type)
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{slugify(note.title)}.md"
        n = 1
        while dest.exists():
            n += 1
            dest = folder / f"{slugify(note.title)}-{n}.md"
        dest.write_text(note.to_markdown(), encoding="utf-8")
        src.unlink()
        return dest

    def reject(self, item_id: str, reason: str | None = None) -> Path:
        src = self._path(item_id)
        note = Note.from_markdown(src.read_text(encoding="utf-8"))
        extra = {"rejected_reason": reason} if reason else {}
        note = Note(**{**note.model_dump(), "status": Status.rejected.value, **extra, "body": note.body})
        dest_dir = self.vault.root / "rejected"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        dest.write_text(note.to_markdown(), encoding="utf-8")
        src.unlink()
        return dest
