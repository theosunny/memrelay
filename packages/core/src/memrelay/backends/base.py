"""Thin MemoryBackend protocol: what the gateway (and twin) need from a storage engine.

Implementations may be local files (Basic Memory / LocalBackend) or a remote engine
(OpenViking, …). Policy stays in MemRelay:

- Agents only *propose* → inbox. `remember` is called for **already-approved** notes (or not
  at all when the vault write already persisted the note).
- `search` returns unfiltered candidate ids; MemRelay applies visibility / secret / as_of.
- **No delete / forget** on this interface. Engines that have a forget tool must not expose
  it through the MemRelay gateway (see OpenVikingBackend).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schema import Note


@runtime_checkable
class MemoryBackend(Protocol):
    """Storage + retrieval engine behind MemRelay."""

    name: str

    async def start(self) -> None:
        """Open connections / spawn subprocesses."""
        ...

    async def stop(self) -> None:
        """Close connections."""
        ...

    async def search(self, query: str, limit: int = 10) -> list[str]:
        """Return note ids (vault-relative paths for file backends), best match first.

        Results are *candidates*: the gateway still filters hidden folders, secrets,
        status and temporal validity.
        """
        ...

    async def get_note(self, note_id: str) -> Note | None:
        """Load one note by id. ``None`` if missing or unreadable at the storage layer."""
        ...

    async def remember(self, note: Note, note_id: str | None = None) -> str:
        """Persist an **already-reviewed** note. Returns the stable note id.

        Must not be wired to agent-facing tools that skip the inbox. File-backed engines
        often no-op here because ``inbox.approve`` already wrote the Markdown file; remote
        engines push the approved content to their ``remember``-equivalent API.
        """
        ...


# Back-compat alias used by older call sites / tests.
SearchBackend = MemoryBackend
