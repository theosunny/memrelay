from __future__ import annotations

from .base import AgentAdapter, Change, Env, JsonMcpAdapter, ServerSpec
from .claude_code import ClaudeCodeAdapter
from .claude_desktop import ClaudeDesktopAdapter
from .cline import ClineAdapter, ClineVSCodeAdapter
from .codex import CodexAdapter
from .cursor import CursorAdapter
from .gemini_cli import GeminiCliAdapter
from .guided import DoubaoAdapter, GuidedAdapter, KimiAdapter, QwenAdapter
from .vscode import VSCodeCopilotAdapter
from .windsurf import WindsurfAdapter

ADAPTERS: dict[str, type[AgentAdapter]] = {
    a.id: a
    for a in (
        ClaudeCodeAdapter, CursorAdapter, ClaudeDesktopAdapter, WindsurfAdapter, CodexAdapter,
        GeminiCliAdapter, VSCodeCopilotAdapter, ClineAdapter, ClineVSCodeAdapter,
        DoubaoAdapter, KimiAdapter, QwenAdapter,
    )
}


def get_adapter(adapter_id: str, env: Env | None = None) -> AgentAdapter:
    try:
        return ADAPTERS[adapter_id](env)
    except KeyError:
        raise KeyError(f"unknown adapter {adapter_id!r}; known: {', '.join(ADAPTERS)}") from None


def is_guided(a: AgentAdapter) -> bool:
    return isinstance(a, GuidedAdapter)


__all__ = ["ADAPTERS", "AgentAdapter", "Change", "Env", "JsonMcpAdapter", "ServerSpec",
           "get_adapter", "is_guided"]
