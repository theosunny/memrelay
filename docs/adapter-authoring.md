# Adding a connector or a capture source

Two rules first:

- **Cite every path.** Each path needs an official doc or source file, and an entry in
  [client-config-paths.md](client-config-paths.md). If you cannot find one, write a
  *guided* adapter instead of guessing.
- **Test on all three OSes without touching the real machine.** Use the injectable `Env`
  (platform, home, environ) and `tmp_path`.

## 1. A connector (writes the client's MCP config)

Most clients store `{"mcpServers": {name: {command, args, env}}}` in a JSON file, so you only
need a path:

```python
# packages/core/src/memrelay/adapters/myagent.py
from pathlib import Path
from .base import JsonMcpAdapter

class MyAgentAdapter(JsonMcpAdapter):
    """MyAgent user config. Source: https://docs.myagent.dev/mcp#config-location"""

    id = "myagent"
    name = "MyAgent"
    sources = ("https://docs.myagent.dev/mcp#config-location",)

    def config_path(self) -> Path:
        if self.env.os == "windows":
            return Path(self.env.environ.get("APPDATA", self.env.home)) / "MyAgent" / "mcp.json"
        return self.env.home / ".myagent" / "mcp.json"
```

`JsonMcpAdapter` already handles:

- refusing to touch invalid JSON
- backups under the data directory
- changing only `mcpServers.memrelay`
- atomic writes, dry runs and rollback

Override `entry()` if the client needs extra keys, e.g. `"type": "stdio"`. For other
formats, subclass `AgentAdapter`; see `adapters/codex.py` for TOML with comments preserved.

If no official path exists, subclass `GuidedAdapter` (`adapters/guided.py`). It writes
nothing and returns a snippet plus bilingual steps.

Then:

1. Register the adapter in `adapters/__init__.py` (`ADAPTERS`).
2. Add it to the `EXPECTED` path table in `tests/test_adapters.py` for `win32`, `darwin` and
   `linux`. The parametrised round-trip, rollback and invalid-file tests then cover it.
3. Add a row to `docs/client-config-paths.md` and to the README clients table.

## 2. A capture source (reads local history)

Capture is **read-only and incremental**. Per-file byte offsets are stored in `CursorState`,
so a re-run never re-reads old lines, and a partial last line waits until it is complete.
For JSONL transcripts, subclass `JsonlTranscriptSource`:

```python
# packages/core/src/memrelay/capture/mytool.py
from pathlib import Path
from .jsonl import JsonlTranscriptSource, text_of_parts

def default_root(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".mytool" / "sessions"     # cite the source!

class MyToolSource(JsonlTranscriptSource):
    id = "mytool"

    def __init__(self, root: Path | None = None):
        self.root = root or default_root()

    def files(self) -> list[Path]:
        return sorted(self.root.glob("*.jsonl")) if self.root.exists() else []

    def parse(self, obj: dict) -> tuple[str, str] | None:
        if obj.get("kind") == "user_turn":
            return "user", text_of_parts(obj.get("content"))
        if obj.get("kind") == "model_turn":
            return "assistant", text_of_parts(obj.get("content"))
        return None   # anything unknown is skipped, never fatal
```

Then:

1. Register the source in `capture/registry.py` (`SOURCES`).
2. Write a test with a small fixture file. Cover:
   - user versus assistant turns
   - junk lines
   - a second run that reads nothing new
   - always `encoding="utf-8"` when writing fixtures, or Windows CI will fail on non-ASCII
3. Document the path and its source.

Only `role == "user"` messages become facts about the user. Assistant text is context only.

## 3. Checklist before a PR

- [ ] `uv run pytest` and `uv run ruff check .` pass.
- [ ] Paths are cited in code docstrings and in `docs/client-config-paths.md`.
- [ ] No network calls in unit tests and no real home directory access.
- [ ] Commits are signed off (`git commit -s`).
