# Changelog

## 0.1.0 (unreleased, private)

- MCP gateway over a Basic Memory subprocess; whitelisted tools; every write goes to `inbox/`.
- `connect`: Claude Code, Cursor, Claude Desktop, Windsurf (Devin path), Codex (TOML), Gemini CLI,
  VS Code Copilot, Cline (CLI + VS Code extension); guided-only 豆包 / Kimi / 千问.
  Backups + rollback; `connect --all` wizard with discovery, preview and per-agent confirm.
  Configs call the installed `memrelay` script.
- `capture`: Claude Code, Codex, Gemini CLI transcripts (incremental); `capture all --watch`.
- `autostart`: launchd / systemd --user / Task Scheduler (or Startup folder), `--dry-run`.
- `import`: ChatGPT / Claude.ai export packages (Downloads scan, ask first); raw transcripts
  archived via Basic Memory importers into hidden `sources/`.
- `review`: local web review UI (127.0.0.1, token + CSRF).
- `HF_ENDPOINT` auto-fallback to hf-mirror.com for embedding model download.
