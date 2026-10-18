from __future__ import annotations

from pathlib import Path

from .base import JsonMcpAdapter


class WindsurfAdapter(JsonMcpAdapter):
    """Windsurf / Devin Desktop — legacy Cascade agent `mcp_config.json` (`mcpServers`).

    - macOS / Linux: `$XDG_CONFIG_HOME/devin/mcp_config.json`, default `~/.config/devin/…`
    - Windows: `%APPDATA%\\devin\\mcp_config.json`
    Source: https://docs.windsurf.com/windsurf/cascade/mcp ("mcp_config.json" section, 2026-10).
    The doc notes the newer "Devin Local" agent uses Devin CLI config files instead; those are
    not written in v0.1. Older Windsurf builds used ~/.codeium/windsurf/mcp_config.json, which
    the current doc no longer lists, so MemRelay does not write it.
    """

    id = "windsurf"
    name = "Windsurf (Cascade)"
    sources = ("https://docs.windsurf.com/windsurf/cascade/mcp",)

    def config_path(self) -> Path:
        e = self.env
        if e.os == "windows":
            appdata = e.environ.get("APPDATA")
            return (Path(appdata) if appdata else e.home / "AppData" / "Roaming") / "devin" / "mcp_config.json"
        xdg = e.environ.get("XDG_CONFIG_HOME")
        return (Path(xdg) if xdg else e.home / ".config") / "devin" / "mcp_config.json"
