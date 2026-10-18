from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import JsonMcpAdapter, ServerSpec


class ClaudeCodeAdapter(JsonMcpAdapter):
    """Claude Code, user scope: top-level `mcpServers` in ~/.claude.json (all OSes).

    Source: https://code.claude.com/docs/en/mcp  ("MCP installation scopes": User scope is
    stored in ~/.claude.json; JSON entries need "type"; a `url` without `type` is read as stdio).
    On Windows `~` is %USERPROFILE% (Path.home()).
    """

    id = "claude-code"
    name = "Claude Code"
    sources = ("https://code.claude.com/docs/en/mcp",)
    warning = (
        "Claude Code rewrites ~/.claude.json while running; exit running sessions first, "
        "or use `claude mcp add-json --scope user memrelay '<json>'`."
    )

    def config_path(self) -> Path:
        return self.env.home / ".claude.json"

    def detect(self) -> bool:
        return (self.env.home / ".claude.json").exists() or (self.env.home / ".claude").is_dir()

    def entry(self, spec: ServerSpec) -> dict[str, Any]:
        return {"type": "stdio", **super().entry(spec)}
