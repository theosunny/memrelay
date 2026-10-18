from __future__ import annotations

from pathlib import Path

from .base import JsonMcpAdapter


class ClaudeDesktopAdapter(JsonMcpAdapter):
    """Claude Desktop `claude_desktop_config.json`.

    - macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
    - Windows: %APPDATA%\\Claude\\claude_desktop_config.json
      Source: https://modelcontextprotocol.io/docs/develop/connect-local-servers
    - Linux:   $XDG_CONFIG_HOME/Claude/claude_desktop_config.json (default ~/.config/Claude)
      Not in the official MCP doc; documented by the Linux packaging project
      https://github.com/aaddrick/claude-desktop-debian (README "Configuration"), which notes
      the official Linux .deb shares ~/.config/Claude. Treated as community-sourced.
    """

    id = "claude-desktop"
    name = "Claude Desktop"
    sources = (
        "https://modelcontextprotocol.io/docs/develop/connect-local-servers",
        "https://github.com/aaddrick/claude-desktop-debian",
    )
    warning = "Quit Claude Desktop completely before editing; it rewrites this file while running."

    def config_path(self) -> Path | None:
        e = self.env
        if e.os == "macos":
            return e.home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        if e.os == "windows":
            appdata = e.environ.get("APPDATA")
            base = Path(appdata) if appdata else e.home / "AppData" / "Roaming"
            return base / "Claude" / "claude_desktop_config.json"
        xdg = e.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else e.home / ".config"
        return base / "Claude" / "claude_desktop_config.json"
