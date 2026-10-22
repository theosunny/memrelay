import json

from memrelay.capture import codex, gemini
from memrelay.capture.base import CursorState
from memrelay.capture.registry import SOURCES
from memrelay.capture.runner import run_once
from memrelay.extract.stub import StubExtractor


def jl(*objs):
    return "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in objs)


def test_registry():
    assert set(SOURCES) == {"claude-code", "codex", "gemini-cli"}


def test_codex_roots(tmp_path):
    assert codex.default_root({}, tmp_path) == tmp_path / ".codex" / "sessions"
    assert codex.default_root({"CODEX_HOME": str(tmp_path / "ch")}, tmp_path) == tmp_path / "ch" / "sessions"


def test_codex_capture(home, tmp_path, inbox):
    root = tmp_path / "sessions"
    d = root / "2026" / "10" / "18"
    d.mkdir(parents=True)
    (d / "rollout-2026-10-18T09-00-00-abc.jsonl").write_text(jl(
        {"timestamp": "t", "type": "session_meta", "payload": {"id": "abc", "cwd": "/w"}},
        {"timestamp": "t", "type": "response_item", "payload": {"type": "message", "role": "user",
         "content": [{"type": "input_text", "text": "<environment_context>…</environment_context>"}]}},
        {"timestamp": "t", "type": "event_msg", "payload": {"type": "user_message", "message": "我习惯用 pnpm 而不是 npm"}},
        {"timestamp": "t", "type": "event_msg", "payload": {"type": "agent_message", "message": "我喜欢 yarn"}},
        {"timestamp": "t", "type": "event_msg", "payload": {"type": "token_count"}},
    ), encoding="utf-8")
    (d / "other.jsonl").write_text(jl({"type": "event_msg", "payload": {"type": "user_message", "message": "我喜欢猫"}}), encoding="utf-8")
    src = codex.CodexSource(root)
    r = run_once(src, StubExtractor(), inbox, CursorState("codex"))
    assert r.messages == 2 and len(r.proposed) == 1 and len(r.auto_approved) == 1
    from memrelay.schema import Note
    prefs = list((inbox.vault.root / "preferences").glob("*.md"))
    assert prefs
    n = Note.from_markdown(prefs[0].read_text(encoding="utf-8"))
    assert "pnpm" in n.title and n.source_agent == "codex" and "rollout-" in n.source_ref
    assert run_once(src, StubExtractor(), inbox, CursorState("codex")).messages == 0


def test_gemini_capture(home, tmp_path, inbox):
    root = tmp_path / "tmp"
    chats = root / "abc123" / "chats"
    chats.mkdir(parents=True)
    (chats / "session-2026-10-18T09-00-x.jsonl").write_text(jl(
        {"sessionId": "s", "projectHash": "abc123", "startTime": "t"},
        {"id": "m1", "timestamp": "t", "type": "user", "content": [{"text": "I prefer dark mode in every editor"}]},
        {"id": "m1", "timestamp": "t", "type": "user", "content": [{"text": "I prefer dark mode in every editor"}]},
        {"id": "m2", "timestamp": "t", "type": "gemini", "content": "I like light mode"},
        {"id": "m3", "timestamp": "t", "type": "info", "content": "I prefer nothing"},
        {"$set": {"messages": []}},
    ), encoding="utf-8")
    src = gemini.GeminiCliSource(root)
    r = run_once(src, StubExtractor(), inbox, CursorState("gemini-cli"))
    assert r.messages == 2 and len(r.proposed) == 1 and len(r.auto_approved) == 1
    from memrelay.schema import Note
    prefs = list((inbox.vault.root / "preferences").glob("*.md"))
    assert any("dark mode" in Note.from_markdown(f.read_text(encoding="utf-8")).title for f in prefs)
    assert gemini.default_root(tmp_path) == tmp_path / ".gemini" / "tmp"


def test_watch_all(home, tmp_path, inbox):
    """Initial capture + a later append; robust to macOS FSEvents /var vs /private/var."""
    import os
    import threading
    import time

    from memrelay.capture.claude_code import ClaudeCodeSource
    from memrelay.capture.runner import watch_all

    cc_root = tmp_path / "cc"
    (cc_root / "-p").mkdir(parents=True)
    f = cc_root / "-p" / "s.jsonl"
    f.write_text(jl({"type": "user", "message": {"role": "user", "content": "我喜欢早起跑步"}}), encoding="utf-8")
    cx_root = tmp_path / "missing-codex"  # absent roots are fine
    reports, stop = [], threading.Event()
    th = threading.Thread(target=watch_all, daemon=True, kwargs=dict(
        sources=[ClaudeCodeSource(cc_root), codex.CodexSource(cx_root)], extractor=StubExtractor(),
        inbox=inbox, on_report=lambda sid, r: reports.append((sid, r)), stop_event=stop, debounce=100))
    th.start()
    deadline = time.time() + 10
    while len(reports) < 2 and time.time() < deadline:
        time.sleep(0.05)
    assert len(reports) >= 2, f"initial reports never arrived: {reports!r}"
    # Give watchfiles time to subscribe (FSEvents can miss events fired during setup).
    time.sleep(1.0)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(jl({"type": "user", "message": {"role": "user", "content": "我习惯喝美式咖啡"}}))
        fh.flush()
        os.fsync(fh.fileno())
    # Also bump mtime explicitly — some FSEvents setups coalesce pure appends.
    os.utime(f, None)
    def vault_count():
        root = inbox.vault.root
        return sum(1 for d in ("preferences", "facts") for _ in (root / d).glob("*.md"))
    deadline = time.time() + 20
    while time.time() < deadline:
        if vault_count() >= 2:
            break
        time.sleep(0.1)
    stop.set()
    th.join(timeout=5)
    from memrelay.schema import Note
    titles = " ".join(
        Note.from_markdown(f.read_text(encoding="utf-8")).title
        for d in ("preferences", "facts")
        for f in (inbox.vault.root / d).glob("*.md")
    )
    assert vault_count() >= 2, (
        f"expected 2 vault items after append; vault={titles!r} "
        f"reports={[(s, len(r.proposed), len(r.auto_approved)) for s, r in reports]!r}"
    )
    assert {sid for sid, _ in reports} >= {"claude-code", "codex"}
