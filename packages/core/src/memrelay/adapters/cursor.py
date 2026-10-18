from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import JsonMcpAdapter, ServerSpec


class CursorAdapter(JsonMcpAdapter):
    """Cursor, global config: ~/.cursor/mcp.json on every OS (project: .cursor/mcp.json).

    Source: https://cursor.com/docs/context/mcp ("Configuration locations" and
    "STDIO server configuration": `type` = "stdio", `command`, `args`, `env`).
    """

    id = "cursor"
    name = "Cursor"
    sources = ("https://cursor.com/docs/context/mcp",)

    def config_path(self) -> Path:
        return self.env.home / ".cursor" / "mcp.json"

    def entry(self, spec: ServerSpec) -> dict[str, Any]:
        return {"type": "stdio", **super().entry(spec)}
