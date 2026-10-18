from __future__ import annotations

from pathlib import Path

from .base import JsonMcpAdapter


class GeminiCliAdapter(JsonMcpAdapter):
    """Gemini CLI user settings `~/.gemini/settings.json`, top-level `mcpServers` (all OSes).

    Sources: https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md
    (user settings location) and docs/tools/mcp-server.md (`mcpServers` with command/args/env).
    """

    id = "gemini-cli"
    name = "Gemini CLI"
    sources = (
        "https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md",
        "https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md",
    )

    def config_path(self) -> Path:
        return self.env.home / ".gemini" / "settings.json"
