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
| Windsurf (Cascade, now Devin) | macOS/Linux | `$XDG_CONFIG_HOME/devin/mcp_config.json` (default `~/.config/devin/mcp_config.json`) | `mcpServers`; legacy `~/.codeium/windsurf/mcp_config.json` is **not** written | https://docs.windsurf.com/windsurf/cascade/mcp |
| Windsurf (Cascade, now Devin) | Windows | `%APPDATA%\devin\mcp_config.json` | same | same |
| Codex CLI / IDE | all | `$CODEX_HOME/config.toml` (default `~/.codex/config.toml`) → `[mcp_servers.<name>]` `command`/`args`/`env` | TOML; edited with tomlkit so comments survive; invalid TOML is refused | https://developers.openai.com/codex/mcp ; https://developers.openai.com/codex/config-advanced |
| Codex transcripts | all | `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl` | JSONL `{timestamp,type,payload}`; user turn = `event_msg` / `payload.type=user_message` | openai/codex `codex-rs/rollout/src/lib.rs` (`SESSIONS_SUBDIR`), `recorder.rs`, `codex-rs/history/src/rollout_payload.rs` |
| Gemini CLI | all | `~/.gemini/settings.json` → `mcpServers` | user scope; project `.gemini/settings.json` not written | google-gemini/gemini-cli `docs/reference/configuration.md`, `docs/tools/mcp-server.md` |
| Gemini CLI transcripts | all | `~/.gemini/tmp/<project_hash>/chats/session-*.jsonl` | JSONL records `{id,timestamp,type:user\|gemini\|…,content}`; `$set` lines are patches; older `.json` sessions not read | gemini-cli `docs/cli/session-management.md`; `packages/core/src/services/chatRecordingService.ts`, `chatRecordingTypes.ts` |
| VS Code (GitHub Copilot, user) | all | `$COPILOT_HOME/mcp-config.json` (default `~/.copilot/mcp-config.json`) → `mcpServers` | entry gets `"type": "stdio"`; legacy per-profile `mcp.json` (`servers`) not written | https://code.visualstudio.com/docs/copilot/customization/mcp-servers |
| Cline (CLI / standalone) | all | `~/.cline/data/settings/cline_mcp_settings.json`; `CLINE_MCP_SETTINGS_PATH` overrides file, `CLINE_DATA_DIR` the data dir | `mcpServers` | https://docs.cline.bot/getting-started/config ; https://github.com/cline/cline/pull/11671 |
| Cline (VS Code extension) | all | `<VS Code user dir>/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | **secondary sources**; only offered when that globalStorage folder already exists | IONOS Cline docs; https://github.com/cline/cline/discussions/1728 |
| 豆包 / Kimi / 通义千问 desktop | — | **unverified — nothing is written** | `connect` prints a JSON snippet + bilingual steps to paste in the app's MCP settings | no official public config path found (2026-10-18) |
| Cursor chat history | — | **not captured** | internal SQLite, no documented path/schema | — |

## Autostart (`memrelay autostart`)

| OS | Mechanism | File / command | Source |
|---|---|---|---|
| macOS | launchd user agent | `~/Library/LaunchAgents/io.memrelay.capture.plist`; `launchctl bootstrap gui/<uid> <plist>` | Apple, "Creating Launch Daemons and Agents"; `man launchctl` |
| Linux | systemd user unit | `$XDG_CONFIG_HOME/systemd/user/memrelay-capture.service`; `systemctl --user enable --now` | systemd.unit(5) "User Unit Search Path" |
| Windows | Task Scheduler (default) | `schtasks /Create /SC ONLOGON /TN MemRelayCapture /TR "…" /RL LIMITED /F` | https://learn.microsoft.com/windows-server/administration/windows-commands/schtasks-create |
| Windows | Startup folder (`--method startup-folder`) | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\memrelay-capture.cmd` | Microsoft shell known folder `FOLDERID_Startup` |

## Model download mirror

Basic Memory's embeddings are downloaded by fastembed via huggingface_hub, which honours
`HF_ENDPOINT` (huggingface_hub `constants.py`). With `hf_endpoint = "auto"` (default) MemRelay
probes `https://huggingface.co`; if unreachable and `https://hf-mirror.com` answers, it sets
`HF_ENDPOINT=https://hf-mirror.com` for the Basic Memory subprocess. A user-set `HF_ENDPOINT`
always wins; `hf_endpoint = "off"` disables this.
