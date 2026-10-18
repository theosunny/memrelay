from __future__ import annotations

from .base import AgentAdapter, Change, Env, JsonMcpAdapter, ServerSpec
from .claude_code import ClaudeCodeAdapter
from .claude_desktop import ClaudeDesktopAdapter
from .cursor import CursorAdapter

ADAPTERS: dict[str, type[AgentAdapter]] = {
    a.id: a for a in (ClaudeCodeAdapter, CursorAdapter, ClaudeDesktopAdapter)
}


def get_adapter(adapter_id: str, env: Env | None = None) -> AgentAdapter:
    try:
        return ADAPTERS[adapter_id](env)
    except KeyError:
        raise KeyError(f"unknown adapter {adapter_id!r}; known: {', '.join(ADAPTERS)}") from None


__all__ = ["ADAPTERS", "AgentAdapter", "Change", "Env", "JsonMcpAdapter", "ServerSpec", "get_adapter"]
