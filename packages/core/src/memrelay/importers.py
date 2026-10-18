"""Import ChatGPT / Claude.ai data-export packages.

Two things happen, both only after the user confirms:
1. Candidate memories: the USER's messages go through the configured extractor into inbox/.
2. Raw archive (optional): Basic Memory's own importers convert the transcripts to Markdown
   under `sources/<kind>/` (hidden from recall), reusing
   `basic-memory import chatgpt <conversations.json> --folder ...` and
   `basic-memory import claude conversations <conversations.json> --folder ...`
   (verified with basic-memory 0.23.2 `--help`).

Export formats follow what Basic Memory's importers read (basic_memory/importers/
chatgpt_importer.py: conversations[*].mapping[*].message.{author.role, content.parts};
claude_conversations_importer.py: conversations[*].chat_messages[*].{sender, text, content}).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import tempfile
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .capture.base import Message
from .config import data_dir
from .extract.base import Extractor
from .inbox import Inbox

KINDS = ("chatgpt", "claude")


@dataclass
class ExportCandidate:
    path: Path
    kind: str
    size: int
    mtime: dt.datetime
    already_imported: bool = False


@dataclass
class ImportReport:
    kind: str
    conversations: int = 0
    messages: int = 0
    proposed: list[str] = field(default_factory=list)
    duplicates: int = 0
    archived: bool = False
    archive_error: str | None = None


def downloads_dir() -> Path:
    import platformdirs

    return Path(platformdirs.user_downloads_dir())


def _read_conversations_bytes(path: Path) -> bytes | None:
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if n.rsplit("/", 1)[-1] == "conversations.json"]
                if not names:
                    return None
                return z.read(sorted(names, key=len)[0])
        except (zipfile.BadZipFile, OSError):
            return None
    if path.name == "conversations.json":
        return path.read_bytes()
    return None


def detect_kind(data: list) -> str | None:
    for conv in data[:20] if isinstance(data, list) else []:
        if isinstance(conv, dict):
            if "mapping" in conv:
                return "chatgpt"
            if "chat_messages" in conv:
                return "claude"
    return None


def load(path: Path) -> tuple[str, list] | None:
    raw = _read_conversations_bytes(path)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    kind = detect_kind(data)
    return (kind, data) if kind else None


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:20]


def _state_path() -> Path:
    return data_dir() / "state" / "imports.json"


def _imported() -> dict:
    p = _state_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _mark_imported(path: Path, kind: str) -> None:
    d = _imported()
    d[file_hash(path)] = {"path": str(path), "kind": kind, "at": dt.datetime.now().isoformat()}
    _state_path().parent.mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(d, indent=1), encoding="utf-8")


def scan(dirs: list[Path] | None = None) -> list[ExportCandidate]:
    """Find export packages (zip or conversations.json) directly inside the given folders."""
    done = _imported()
    out: list[ExportCandidate] = []
    for d in dirs or [downloads_dir()]:
        if not d.is_dir():
            continue
        paths = [*d.glob("*.zip"), *d.glob("conversations.json"), *d.glob("*/conversations.json")]
        for p in sorted(set(paths)):
            res = load(p)
            if not res:
                continue
            st = p.stat()
            out.append(ExportCandidate(p, res[0], st.st_size,
                                       dt.datetime.fromtimestamp(st.st_mtime).astimezone(),
                                       file_hash(p) in done))
    return out


def _chatgpt_text(content: dict) -> str:
    if not isinstance(content, dict) or content.get("content_type") not in ("text", "multimodal_text"):
        return ""
    return "\n".join(p for p in content.get("parts") or [] if isinstance(p, str)).strip()


def iter_messages(kind: str, data: list, ref: str) -> Iterator[Message]:
    for conv in data:
        if not isinstance(conv, dict):
            continue
        if kind == "chatgpt":
            cid = conv.get("conversation_id") or conv.get("id") or conv.get("title", "")
            nodes = sorted(
                (n for n in (conv.get("mapping") or {}).values() if isinstance(n, dict) and n.get("message")),
                key=lambda n: n["message"].get("create_time") or 0,
            )
            for n in nodes:
                m = n["message"]
                role = (m.get("author") or {}).get("role")
                if role not in ("user", "assistant"):
                    continue
                if (m.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
                    continue
                text = _chatgpt_text(m.get("content") or {})
                if text:
                    ts = m.get("create_time")
                    yield Message(role, text,
                                  dt.datetime.fromtimestamp(ts, dt.UTC).isoformat() if ts else None,
                                  str(cid), None, f"{ref}#{cid}/{m.get('id') or n.get('id')}")
        else:
            cid = conv.get("uuid") or conv.get("name", "")
            for m in conv.get("chat_messages") or []:
                sender = m.get("sender")
                role = "user" if sender == "human" else "assistant" if sender == "assistant" else None
                if not role:
                    continue
                text = (m.get("text") or "").strip()
                if not text and isinstance(m.get("content"), list):
                    text = "\n".join(str(c.get("text")) for c in m["content"]
                                     if isinstance(c, dict) and c.get("text")).strip()
                if text:
                    yield Message(role, text, m.get("created_at"), str(cid), None,
                                  f"{ref}#{cid}/{m.get('uuid', '')}")


def archive_with_basic_memory(kind: str, raw: bytes, bm_command: list[str], env: dict[str, str]) -> None:
    sub = ["chatgpt"] if kind == "chatgpt" else ["claude", "conversations"]
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "conversations.json"
        f.write_bytes(raw)
        r = subprocess.run([*bm_command, "import", *sub, str(f), "--folder", f"sources/{kind}"],
                           env=env, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout)[-2000:])


def run_import(path: Path, extractor: Extractor, inbox: Inbox, archive=None) -> ImportReport:
    """`archive`: optional callable(kind, raw_bytes) used to keep raw transcripts."""
    res = load(path)
    if not res:
        raise ValueError(f"{path} is not a ChatGPT or Claude export")
    kind, data = res
    rep = ImportReport(kind, conversations=len(data))
    msgs = list(iter_messages(kind, data, path.name))
    rep.messages = len(msgs)
    for cand in extractor.extract(msgs):
        note = cand.to_note(source_agent=kind, source_channel="export-import", extractor=extractor.name)
        r = inbox.propose(note)
        if r.duplicate_of:
            rep.duplicates += 1
        else:
            rep.proposed.append(r.id)
    if archive is not None:
        try:
            archive(kind, _read_conversations_bytes(path) or b"[]")
            rep.archived = True
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            rep.archive_error = str(e)
    _mark_imported(path, kind)
    return rep
