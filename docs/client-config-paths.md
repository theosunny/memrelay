# Client config paths and sources

Every path used by `memrelay connect` and `memrelay capture`, with the source it came from
(checked 2026-10-18). Do not add a path without a source.

| Client | OS | Path | Format notes | Source |
|---|---|---|---|---|
| Claude Code (user scope) | all | `~/.claude.json` → top-level `mcpServers` | stdio entry needs `"type": "stdio"`; Claude Code rewrites this file while running (keeps 5 backups in `~/.claude/backups/`) | https://code.claude.com/docs/en/mcp ("MCP installation scopes"); https://code.claude.com/docs/en/claude-directory |
| Claude Code (project scope) | all | `<project>/.mcp.json` | not written by MemRelay in v0.1 | same |
| Cursor (global) | all | `~/.cursor/mcp.json` | `type` required for stdio | https://cursor.com/docs/context/mcp ("Configuration locations", "STDIO server configuration") |
| Cursor (project) | all | `<project>/.cursor/mcp.json` | not written in v0.1 | same |
| Claude Desktop | macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` | `mcpServers` | https://modelcontextprotocol.io/docs/develop/connect-local-servers |
| Claude Desktop | Windows | `%APPDATA%\Claude\claude_desktop_config.json` | `mcpServers` | same |
| Claude Desktop | Linux | `$XDG_CONFIG_HOME/Claude/claude_desktop_config.json` (default `~/.config/Claude/…`) | **community-sourced**; app overwrites the file while running — quit first | https://github.com/aaddrick/claude-desktop-debian (README "Configuration"); overwrite bug: https://github.com/anthropics/claude-code/issues/32345 |
| Claude Code transcripts | all | `~/.claude/projects/<cwd with non-alphanumerics → "-">/<session-id>.jsonl`; `CLAUDE_CONFIG_DIR` moves `~/.claude` | JSONL, "internal to Claude Code and changes between versions"; 30-day default retention (`cleanupPeriodDays`) | https://code.claude.com/docs/en/sessions ("Where transcripts are stored"); https://code.claude.com/docs/en/claude-directory |
| Basic Memory state | all | `$BASIC_MEMORY_CONFIG_DIR`, else `$XDG_CONFIG_HOME/basic-memory`, else `~/.basic-memory` | MemRelay sets `BASIC_MEMORY_CONFIG_DIR=<memrelay data dir>/basic-memory` | basic-memory `src/basic_memory/config_models.py::resolve_data_dir` (v0.23.2) |
