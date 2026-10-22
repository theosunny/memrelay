"""OpenViking backend *stub* — documents the mapping; no live network I/O yet.

Intended mapping (see https://docs.openviking.ai/en/api/16-memory and
https://github.com/volcengine/OpenViking/blob/main/docs/en/agent-integrations/16-capability-reference.md):

| MemRelay MemoryBackend | OpenViking                                      |
|------------------------|-------------------------------------------------|
| ``remember(note)``     | MCP/API ``remember`` (one-shot session + commit)|
| ``search(query)``      | ``search(mode="context")`` (not deprecated recall)|
| ``get_note(id)``       | ``read`` / resource URI under ``viking://user/…``|
| *(forbidden)*          | ``forget`` — **never** exposed via MemRelay     |

Policy that stays in MemRelay no matter which engine is underneath:

1. Agents call ``propose_memory`` only → inbox. ``remember`` runs after human approve.
2. The gateway whitelist has no delete/forget/edit tool.
3. This class raises on any forget/delete attempt so a mistaken wiring fails closed.

Full HTTP/MCP client wiring is intentionally out of scope for this stub.
"""

from __future__ import annotations

from ..config import Config
from ..schema import Note
from ..vault import Vault

# OV MCP tool names we must never call from MemRelay.
FORBIDDEN_OV_TOOLS = frozenset({"forget", "forget_memory", "delete", "delete_memory"})


class OpenVikingBackend:
    name = "openviking"

    def __init__(self, cfg: Config, vault: Vault):
        self.cfg, self.vault = cfg, vault
        self._started = False
        # Reserved for a future Client; stub never opens a socket.
        self._client = None
        base = getattr(cfg, "openviking_base_url", "") or ""
        self.base_url = base.rstrip("/")

    async def start(self) -> None:
        # Real integration would connect to OV's /mcp or HTTP API using openviking_base_url.
        self._started = True

    async def stop(self) -> None:
        self._client = None
        self._started = False

    async def search(self, query: str, limit: int = 10) -> list[str]:
        """Would call OV ``search(mode="context", …)``. Stub: empty candidates."""
        self._require_started()
        _ = (query, limit)
        return []

    async def get_note(self, note_id: str) -> Note | None:
        """Would ``read`` a viking:// URI. Stub: unknown."""
        self._require_started()
        _ = note_id
        return None

    async def remember(self, note: Note, note_id: str | None = None) -> str:
        """Would call OV ``remember`` after inbox approval. Stub: echo id / synthetic id."""
        self._require_started()
        if note_id:
            return note_id
        # Synthetic id until a real OV URI comes back from remember's task result.
        return f"openviking:pending/{note.title[:40]}"

    # ----- hard refusals (tests assert these) ---------------------------------
    async def forget(self, *args, **kwargs) -> None:
        raise PermissionError(
            "MemRelay never exposes OpenViking 'forget' through its gateway; "
            "use SUPERSEDE / archive after human review instead."
        )

    async def delete(self, *args, **kwargs) -> None:
        await self.forget(*args, **kwargs)

    def call_tool(self, name: str, *args, **kwargs):
        """Escape hatch used only by tests / future MCP proxy — blocks delete tools."""
        if name in FORBIDDEN_OV_TOOLS:
            raise PermissionError(
                f"Refusing OpenViking tool {name!r}: MemRelay policy forbids delete/forget "
                f"(see docs/comparison.md)."
            )
        raise NotImplementedError(
            f"OpenVikingBackend stub: tool {name!r} not wired yet "
            f"(remember→OV remember, search→search mode=context)."
        )

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("OpenVikingBackend not started")
