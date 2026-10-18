# Contributing to MemRelay

Thanks for helping! 欢迎贡献（中文 issue / PR 同样欢迎）。

## Developer Certificate of Origin (DCO)

We use the [DCO 1.1](https://developercertificate.org/) instead of a CLA. Every commit must be
signed off, certifying you wrote it or otherwise have the right to submit it under Apache-2.0:

```bash
git commit -s -m "feat(connect): add Windsurf adapter"
# adds: Signed-off-by: Your Name <you@example.com>
```

PRs with unsigned commits will be asked to rebase with `git rebase --signoff`.

## Setup

```bash
uv sync
uv run pytest                 # unit tests (no network, no Basic Memory needed)
uv run pytest -m integration  # needs `basic-memory` on PATH
uv run ruff check .
```

## Adding an agent adapter

Full guide with examples: [docs/adapter-authoring.md](docs/adapter-authoring.md).

1. Subclass `memrelay.adapters.base.JsonMcpAdapter` (or `AgentAdapter`) in
   `packages/core/src/memrelay/adapters/<agent>.py`.
2. Implement `config_path(platform)` for `win32`, `darwin`, `linux` and **cite the official doc
   or source for every path** in `docs/client-config-paths.md`. Never guess a path.
3. Register it in `memrelay/adapters/__init__.py` and add tests under a temporary home dir.

## Adding a capture source

Implement `memrelay.capture.base.CaptureSource` (`iter_new_messages(state)`), keep it
incremental and read-only, and document the file location with a source.

## Rules

- Agents must never write to the vault directly: all writes go through `inbox/`.
- No secrets in tests or fixtures. No network in unit tests.
- Keep user-facing strings bilingual (zh/en) where practical.
