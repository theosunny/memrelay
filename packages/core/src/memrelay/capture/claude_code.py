"""Claude Code session transcripts.

Location (source: https://code.claude.com/docs/en/sessions "Where transcripts are stored", and
https://code.claude.com/docs/en/claude-directory): `~/.claude/projects/<mangled-cwd>/<session>.jsonl`,
movable with CLAUDE_CONFIG_DIR. Subagent transcripts live in `<session>/subagents/` and set-aside
copies are named `.orphaned-*` / `*.jsonl.superseded-*`; we skip those.

The docs warn the line format "is internal to Claude Code and changes between versions", so this
parser is defensive: any line it cannot understand is skipped, never fatal. Default retention is
30 days (`cleanupPeriodDays`), so capture should run at least that often.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .jsonl import JsonlTranscriptSource


def default_root(environ: dict[str, str] | None = None, home: Path | None = None) -> Path:
    env = os.environ if environ is None else environ
    base = Path(env["CLAUDE_CONFIG_DIR"]) if env.get("CLAUDE_CONFIG_DIR") else (home or Path.home()) / ".claude"
    return base / "projects"


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return ""


def parse_line(obj: dict) -> tuple[str, str] | None:
    """Return (role, text) for real user/assistant text turns, else None."""
    if not isinstance(obj, dict):
        return None
    if obj.get("isSidechain") or obj.get("isMeta"):
        return None
    kind = obj.get("type")
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
    role = msg.get("role") or kind
    if kind not in ("user", "assistant") or role not in ("user", "assistant"):
        return None
    content = msg.get("content")
    # user turns that only carry tool results are not the user's words
    if isinstance(content, list) and content and all(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    ):
        return None
    text = _text_of(content).strip()
    if not text or text.startswith("<command-") or text.startswith("<local-command"):
        return None
    return role, text


class ClaudeCodeSource(JsonlTranscriptSource):
    id = "claude-code"

    def __init__(self, root: Path | None = None):
        self.root = root or default_root()

    def files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(
            p for p in self.root.glob("*/*.jsonl")
            if not p.name.startswith(".") and "superseded" not in p.name and "orphaned" not in p.name
        )

    def parse(self, obj: dict) -> tuple[str, str] | None:
        return parse_line(obj)
