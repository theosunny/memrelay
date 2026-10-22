# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com/); versions follow SemVer (pre-1.0: minor = features).

## [Unreleased] (0.2.0.dev0)

### Added
- `docs/comparison.md`: MemRelay vs OpenViking vs Supermemory vs Basic Memory vs Mem0.
- Pluggable `memrelay.backends` (`MemoryBackend`: search / get_note / remember). OpenViking
  stub refuses forget/delete; config `backend = "openviking"` (+ `openviking_base_url`).

### Added — v0.2 "twin"
- Temporal memory: `recall(as_of=YYYY-MM-DD)` returns what was true then, including
  superseded facts. Events are stored under `events/YYYY/` and reflections under
  `reflections/<period>/`.
- Consolidation (`memrelay consolidate`): ADD / UPDATE / SUPERSEDE / NOOP plans made by
  rules or an LLM, applied only on approval. SUPERSEDE sets `valid_to` + `superseded_by`;
  replaced versions are copied to `archive/`; nothing is deleted. `inbox approve --as-new`
  ignores the plan.
- Reflection: `reflect daily|weekly` writes reflections with validated citations (a
  Generative-Agents style insight step for weekly). `dream` takes a git snapshot, proposes
  merges and lists stale or long notes; `dream rollback <sha>` restores a snapshot as a new
  commit.
- Persona:
  - `profile style` builds a style card from the user's own messages only (reproducible
    statistics, redacted examples, optional LLM tone summary).
  - `profile principles` keeps principles that have at least 2 pieces of evidence.
- Twin MCP tools:
  - `answer_as_me` returns citations, a confidence value and an AI-twin disclosure,
    supports `as_of`, refuses requests for secrets or memory dumps, and applies a
    visibility ceiling.
  - `draft_as_me` returns a draft only, flags commitments and applies a channel
    visibility. There is no send capability.
  - Both are logged to a local audit file.
- Pluggable persona LLM (`persona_llm`): OpenAI-compatible endpoints with presets for
  openai, deepseek, qwen, kimi and ollama, plus `StubLLM` for tests.
- Fidelity eval (`eval init|run`): fact, point-in-time, should-refuse and unknown
  categories.

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
