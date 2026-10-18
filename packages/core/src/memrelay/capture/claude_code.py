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

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .base import CursorState, Message


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


class ClaudeCodeSource:
    id = "claude-code"

    def __init__(self, root: Path | None = None):
        self.root = root or default_root()

    def files(self) -> list[Path]:
        if not self.root.exists():
            return []
        out = []
        for p in self.root.glob("*/*.jsonl"):
            if p.name.startswith(".") or "superseded" in p.name or "orphaned" in p.name:
                continue
            out.append(p)
        return sorted(out)

    def iter_new_messages(self, state: CursorState) -> Iterator[Message]:
        for f in self.files():
            st = state.get(f)
            size = f.stat().st_size
            offset, line_no = st["offset"], st["line"]
            if size < offset:  # file was rewritten/truncated -> start over
                offset, line_no = 0, 0
            if size == offset:
                continue
            with f.open("rb") as fh:
                fh.seek(offset)
                while True:
                    raw = fh.readline()
                    if not raw:
                        break
                    if not raw.endswith(b"\n"):  # partial line still being written
                        break
                    offset += len(raw)
                    line_no += 1
                    try:
                        obj = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    parsed = parse_line(obj)
                    if not parsed:
                        continue
                    role, text = parsed
                    yield Message(
                        role=role,
                        text=text,
                        timestamp=obj.get("timestamp"),
                        session_id=obj.get("sessionId") or f.stem,
                        cwd=obj.get("cwd"),
                        source_ref=f"{f.as_posix()}#L{line_no}",
                    )
            state.set(f, offset, line_no, size)
