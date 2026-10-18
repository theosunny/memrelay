# MemRelay (忆桥)

[中文](README.zh-CN.md) · License: Apache-2.0 · Status: **pre-alpha (v0.1 in progress, private)**

**One personal memory for all your AI agents.** MemRelay connects Claude Code, Cursor,
Claude Desktop and other MCP-capable agents to a single Markdown memory vault that *you* own,
with provenance on every memory and a review inbox in front of every write.

It does not reinvent storage: the vault is managed by
[Basic Memory](https://github.com/basicmachines-co/basic-memory), which MemRelay runs as a
separate program over MCP stdio. MemRelay adds the parts no existing project combines:

- **Gateway** – an MCP server that exposes only whitelisted tools (`get_profile`, `recall`,
  `read_memory`, `recent`, `propose_memory`). Agents can *read* reviewed memories and *propose*
  new ones; proposals land in `inbox/` and never touch the vault until you approve them.
- **Connect** – writes the MCP config for each agent on Windows / macOS / Linux, with a backup
  and one-command rollback.
- **Capture** – reads local agent history (Claude Code session logs first) incrementally and
  turns it into candidate memories through a pluggable extractor (LLM or offline stub).
- **Review** – `memrelay inbox list / show / approve / reject`.
- **Profile** – builds a compact core profile from approved memories, to inject into agents
  that cannot speak MCP.

## Quick start (development)

```bash
uv tool install basic-memory          # storage backend (AGPL-3.0, installed separately)
uv sync                               # in this repo
uv run memrelay init                  # creates ~/MemRelay vault + config
uv run memrelay connect list          # see which agents were detected
uv run memrelay connect install cursor --dry-run
uv run memrelay capture claude-code   # one-shot incremental capture -> inbox/
uv run memrelay inbox list
uv run memrelay profile build
uv run memrelay serve                 # MCP gateway over stdio (what agents launch)
```

## Repository layout

```
packages/core            Python package `memrelay` (gateway, connect, capture, review, profile)
packages/web             PWA review UI            (v0.2, planned)
packages/desktop         Tauri tray app           (v0.2, planned)
packages/extension       Browser capture extension (v0.2, planned)
packages/mobile-shortcuts iOS Shortcuts / Android share target (v0.2, planned)
docs/                    Design notes, client config path sources
```

## Licensing

MemRelay is Apache-2.0. Basic Memory is AGPL-3.0-or-later and is **not** bundled; see `NOTICE`.
