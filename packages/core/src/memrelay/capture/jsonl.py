"""Generic incremental JSONL transcript reader shared by the CLI-agent capture sources."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from .base import CursorState, Message


class JsonlTranscriptSource:
    """Subclasses set `id`, implement `files()` and `parse(obj) -> (role, text) | None`."""

    id = "jsonl"

    def files(self) -> list[Path]:  # pragma: no cover - abstract
        raise NotImplementedError

    def parse(self, obj: dict) -> tuple[str, str] | None:  # pragma: no cover - abstract
        raise NotImplementedError

    def session_of(self, obj: dict, f: Path) -> str | None:
        return obj.get("sessionId") or obj.get("session_id") or f.stem

    def iter_new_messages(self, state: CursorState) -> Iterator[Message]:
        for f in self.files():
            st = state.get(f)
            size = f.stat().st_size
            offset, line_no = st["offset"], st["line"]
            if size < offset:  # rewritten/truncated -> start over
                offset, line_no = 0, 0
            if size == offset:
                continue
            with f.open("rb") as fh:
                fh.seek(offset)
                while True:
                    raw = fh.readline()
                    if not raw or not raw.endswith(b"\n"):  # EOF or partial line
                        break
                    offset += len(raw)
                    line_no += 1
                    try:
                        obj = json.loads(raw)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if not isinstance(obj, dict):
                        continue
                    try:
                        parsed = self.parse(obj)
                    except (KeyError, TypeError, AttributeError):
                        parsed = None
                    if not parsed:
                        continue
                    role, text = parsed
                    yield Message(
                        role=role, text=text, timestamp=obj.get("timestamp"),
                        session_id=self.session_of(obj, f), cwd=obj.get("cwd"),
                        source_ref=f"{f.as_posix()}#L{line_no}",
                    )
            state.set(f, offset, line_no, size)


def text_of_parts(content) -> str:
    """Join text from a str or a list of {type?: 'text'|'input_text'|..., text: str} parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, str):
                out.append(p)
            elif isinstance(p, dict) and isinstance(p.get("text"), str) and p.get("type", "text") in (
                "text", "input_text", "output_text"
            ):
                out.append(p["text"])
        return "\n".join(out)
    return ""
