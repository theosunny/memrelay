"""Vault layout: one folder per memory layer + review areas."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .schema import MemoryType, Note

TYPE_FOLDER: dict[str, str] = {
    MemoryType.event.value: "events",
    MemoryType.fact.value: "facts",
    MemoryType.preference.value: "preferences",
    MemoryType.procedure.value: "skills",
    MemoryType.person.value: "people",
    MemoryType.project.value: "projects",
    MemoryType.principle.value: "principles",
    MemoryType.reflection.value: "reflections",
    MemoryType.profile.value: "profile",
}
REVIEW_FOLDERS = ("inbox", "rejected", "archive")
# Never returned to agents by recall/read.
# `sources/` holds raw archived transcripts (e.g. Basic Memory imports of chat exports).
HIDDEN_FOLDERS = frozenset(REVIEW_FOLDERS) | {"sources", ".memrelay", ".git", ".obsidian"}

README = """# MemRelay vault

Managed by MemRelay (忆桥). Plain Markdown — edit freely.

- `inbox/`     proposals from agents and capture, waiting for your review
- `rejected/`  rejected proposals (kept for audit; safe to delete)
- `archive/`   retired memories
- other folders: approved memories, one folder per layer
"""


class Vault:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser()

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    def init(self) -> list[Path]:
        created = []
        for name in [*TYPE_FOLDER.values(), *REVIEW_FOLDERS]:
            p = self.root / name
            if not p.exists():
                p.mkdir(parents=True)
                created.append(p)
        readme = self.root / "README.md"
        if not readme.exists():
            readme.write_text(README, encoding="utf-8")
        return created

    def folder_for(self, mtype: str) -> Path:
        return self.root / TYPE_FOLDER.get(str(mtype), "facts")

    def is_hidden(self, path: Path) -> bool:
        rel = Path(path).resolve().relative_to(self.root.resolve())
        return bool(rel.parts) and rel.parts[0] in HIDDEN_FOLDERS

    def resolve(self, rel: str) -> Path:
        """Resolve a vault-relative path, refusing traversal outside the vault."""
        p = (self.root / rel).resolve()
        p.relative_to(self.root.resolve())  # raises ValueError if outside
        return p

    def iter_notes(self, include_hidden: bool = False) -> Iterator[tuple[Path, Note]]:
        for p in sorted(self.root.rglob("*.md")):
            if p.name == "README.md" and p.parent == self.root:
                continue
            if not include_hidden and self.is_hidden(p):
                continue
            try:
                yield p, Note.from_markdown(p.read_text(encoding="utf-8"))
            except Exception:
                continue  # user notes without our frontmatter are skipped

    def rel(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.root.resolve()).as_posix()
