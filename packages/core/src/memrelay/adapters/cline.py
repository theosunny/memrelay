from __future__ import annotations

from pathlib import Path

from .base import JsonMcpAdapter


class ClineAdapter(JsonMcpAdapter):
    """Cline (CLI / SDK; shared global config): `~/.cline/data/settings/cline_mcp_settings.json`.

    `CLINE_MCP_SETTINGS_PATH` overrides the file, `CLINE_DATA_DIR` the data dir.
    Sources: https://docs.cline.bot/getting-started/config ; docs/mcp/mcp-overview.mdx in
    github.com/cline/cline ; resolver `resolveMcpSettingsPath()` quoted in cline/cline#11671.
    """

    id = "cline"
    name = "Cline"
    sources = (
        "https://docs.cline.bot/getting-started/config",
        "https://github.com/cline/cline/issues/11671",
    )

    def config_path(self) -> Path:
        env = self.env.environ
        if env.get("CLINE_MCP_SETTINGS_PATH", "").strip():
            return Path(env["CLINE_MCP_SETTINGS_PATH"].strip())
        data = Path(env["CLINE_DATA_DIR"]) if env.get("CLINE_DATA_DIR") else self.env.home / ".cline" / "data"
        return data / "settings" / "cline_mcp_settings.json"


class ClineVSCodeAdapter(JsonMcpAdapter):
    """Cline VS Code extension storage (`saoudrizwan.claude-dev` globalStorage).

    Paths are from secondary sources (not Cline's own docs): IONOS Cline guide
    https://docs.ionos.com/cloud/ai/mcp-server/connect-to-an-ai-client/cline and a Cline
    maintainer answer in https://github.com/cline/cline/discussions/1728. Only detected when the
    extension folder already exists.
    """

    id = "cline-vscode"
    name = "Cline (VS Code extension)"
    sources = (
        "https://docs.ionos.com/cloud/ai/mcp-server/connect-to-an-ai-client/cline",
        "https://github.com/cline/cline/discussions/1728",
    )

    def config_path(self) -> Path:
        e = self.env
        if e.os == "macos":
            user = e.home / "Library" / "Application Support" / "Code" / "User"
        elif e.os == "windows":
            appdata = e.environ.get("APPDATA")
            user = (Path(appdata) if appdata else e.home / "AppData" / "Roaming") / "Code" / "User"
        else:
            xdg = e.environ.get("XDG_CONFIG_HOME")
            user = (Path(xdg) if xdg else e.home / ".config") / "Code" / "User"
        return user / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"

    def detect(self) -> bool:
        return self.config_path().parent.parent.is_dir()
