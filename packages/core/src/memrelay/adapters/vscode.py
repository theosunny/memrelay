from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import JsonMcpAdapter, ServerSpec


class VSCodeCopilotAdapter(JsonMcpAdapter):
    """VS Code (GitHub Copilot) user MCP config: `$COPILOT_HOME/mcp-config.json`, default
    `~/.copilot/mcp-config.json`, top-level `mcpServers`.

    Source: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
    ("Configure the mcp.json file": the user-level file "preferred for personal configurations"
    shared with compatible Copilot tools). The per-profile `mcp.json` (`servers` key) is marked
    as a legacy destination in that doc and is not written.
    """

    id = "vscode"
    name = "VS Code (Copilot)"
    sources = ("https://code.visualstudio.com/docs/copilot/customization/mcp-servers",)

    def config_path(self) -> Path:
        ch = self.env.environ.get("COPILOT_HOME")
        return (Path(ch) if ch else self.env.home / ".copilot") / "mcp-config.json"

    def detect(self) -> bool:
        return super().detect() or (self.env.home / ".vscode").is_dir()

    def entry(self, spec: ServerSpec) -> dict[str, Any]:
        return {"type": "stdio", **super().entry(spec)}
