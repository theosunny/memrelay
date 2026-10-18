from __future__ import annotations

from .claude_code import ClaudeCodeSource
from .codex import CodexSource
from .gemini import GeminiCliSource

SOURCES = {s.id: s for s in (ClaudeCodeSource, CodexSource, GeminiCliSource)}

# Cursor: chat history lives in internal SQLite (state.vscdb) with no documented schema or
# path, so it is intentionally NOT a capture source in v0.1 (see docs/client-config-paths.md).
