"""OpenAI Codex (CLI / IDE extension / desktop) session rollouts.

Location: `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<id>.jsonl`, CODEX_HOME defaults
to ~/.codex. Sources: https://developers.openai.com/codex/config-advanced ("Config and state
locations": state lives under CODEX_HOME, default ~/.codex); codex-rs/rollout/src/lib.rs
(SESSIONS_SUBDIR = "sessions") and codex-rs/rollout/src/recorder.rs (year/month/day dirs,
`rollout-...jsonl` names). Line envelope `{"timestamp", "type", "payload"}` from
codex-rs/history/src/rollout_payload.rs; user turns are `type=event_msg` with
`payload.type=user_message` and `payload.message`; assistant turns `agent_message`.
The format is internal to Codex, so unknown lines are skipped.
"""

from __future__ import annotations

import os
from pathlib import Path

from .jsonl import JsonlTranscriptSource


def default_root(environ: dict[str, str] | None = None, home: Path | None = None) -> Path:
    env = os.environ if environ is None else environ
    base = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else (home or Path.home()) / ".codex"
    return base / "sessions"


class CodexSource(JsonlTranscriptSource):
    id = "codex"

    def __init__(self, root: Path | None = None):
        self.root = root or default_root()

    def files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*/*/*/rollout-*.jsonl"))

    def parse(self, obj: dict) -> tuple[str, str] | None:
        if obj.get("type") != "event_msg":
            return None
        payload = obj.get("payload") or {}
        kind = payload.get("type")
        msg = payload.get("message")
        if not isinstance(msg, str) or not msg.strip():
            return None
        if kind == "user_message":
            return "user", msg.strip()
        if kind == "agent_message":
            return "assistant", msg.strip()
        return None

    def session_of(self, obj: dict, f: Path) -> str | None:
        return f.stem
