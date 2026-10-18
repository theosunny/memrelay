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
    (d / "other.jsonl").write_text(jl({"type": "event_msg", "payload": {"type": "user_message", "message": "我喜欢猫"}}))
    src = codex.CodexSource(root)
    r = run_once(src, StubExtractor(), inbox, CursorState("codex"))
    assert r.messages == 2 and len(r.proposed) == 1
    n = inbox.list()[0][1]
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
    assert r.messages == 2 and len(r.proposed) == 1
    assert "dark mode" in inbox.list()[0][1].title
    assert gemini.default_root(tmp_path) == tmp_path / ".gemini" / "tmp"
