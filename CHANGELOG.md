# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com/); versions follow SemVer (pre-1.0: minor = features).

## [Unreleased]

## [0.1.0] - 2026-10-18

First public preview. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md).

### Added

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
- Docs: architecture overview, adapter-authoring guide, cited path table; issue/PR templates.

### Fixed
- Windows: UTF-8 everywhere in tests; `memrelay.exe/.cmd` PATH lookup.
- macOS: watcher path matching across `/var` ↔ `/private/var` (FSEvents).

### Security
- Agents can only propose; reads exclude inbox/rejected/archive/expired/secret notes.
- Secret redaction and prompt-injection flags on every proposal.
- Review UI bound to 127.0.0.1 with per-run token, CSRF check, host check and CSP.
