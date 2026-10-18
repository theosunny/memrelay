import json

import httpx

from memrelay.capture.base import CursorState, Message
from memrelay.capture.claude_code import ClaudeCodeSource, default_root, parse_line
from memrelay.capture.runner import run_once
from memrelay.extract.llm import OpenAICompatExtractor
from memrelay.extract.stub import StubExtractor


def _line(kind, content, **kw):
    return json.dumps({"type": kind, "message": {"role": kind, "content": content},
                       "sessionId": "s1", "cwd": "/w", "timestamp": "2026-10-18T01:00:00Z", **kw},
                      ensure_ascii=False) + "\n"


def write_session(root, lines, name="s1.jsonl", proj="-w-proj"):
    d = root / proj
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    with p.open("a", encoding="utf-8") as f:
        f.writelines(lines)
    return p


def test_parse_line_filters():
    assert parse_line(json.loads(_line("user", "我喜欢简洁的回复"))) == ("user", "我喜欢简洁的回复")
    assert parse_line(json.loads(_line("assistant", [{"type": "text", "text": "ok"},
                                                     {"type": "tool_use", "name": "x"}]))) == ("assistant", "ok")
    assert parse_line(json.loads(_line("user", [{"type": "tool_result", "content": "x"}]))) is None
    assert parse_line(json.loads(_line("user", "hi", isSidechain=True))) is None
    assert parse_line(json.loads(_line("user", "hi", isMeta=True))) is None
    assert parse_line(json.loads(_line("user", "<command-name>/clear</command-name>"))) is None
    assert parse_line({"type": "summary", "summary": "x"}) is None
    assert parse_line([1, 2]) is None


def test_default_root(tmp_path):
    assert default_root({}, tmp_path) == tmp_path / ".claude" / "projects"
    assert default_root({"CLAUDE_CONFIG_DIR": str(tmp_path / "c")}, tmp_path) == tmp_path / "c" / "projects"


def test_incremental_capture(home, tmp_path, inbox):
    root = tmp_path / "projects"
    write_session(root, [
        _line("user", "请记住：我的时区是 Asia/Shanghai"),
        _line("assistant", "好的。我喜欢猫"),  # assistant text must not become a user fact
        "not json at all\n",
        _line("user", "I prefer short answers in Chinese."),
    ])
    write_session(root, [_line("user", "我喜欢猫")], name=".orphaned-x.jsonl")
    write_session(root, [_line("user", "我喜欢狗")], proj="-w-proj/s1/subagents")
    src = ClaudeCodeSource(root)
    state = CursorState("claude-code")
    r = run_once(src, StubExtractor(), inbox, state)
    assert r.messages == 3 and len(r.proposed) == 2
    titles = sorted(n.title for _, n in inbox.list())
    assert any("Asia/Shanghai" in t for t in titles) and any("prefer short" in t for t in titles)
    assert not any("猫" in t or "狗" in t for t in titles)
    n = inbox.list()[0][1]
    assert n.source_channel == "local-capture" and n.source_agent == "claude-code"
    assert n.source_ref and "#L" in n.source_ref and n.extractor == "stub@0.1"

    # second run: nothing new
    r = run_once(src, StubExtractor(), inbox, CursorState("claude-code"))
    assert r.messages == 0 and r.proposed == []

    # partial line (still being written) is not consumed
    p = root / "-w-proj" / "s1.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(_line("user", "我习惯先调研再动手").rstrip("\n"))
    r = run_once(src, StubExtractor(), inbox, CursorState("claude-code"))
    assert r.messages == 0
    with p.open("a", encoding="utf-8") as f:
        f.write("\n")
    r = run_once(src, StubExtractor(), inbox, CursorState("claude-code"))
    assert r.messages == 1 and len(r.proposed) == 1

    # repeated fact in a new session -> duplicate, not a new inbox item
    write_session(root, [_line("user", "I prefer short answers in Chinese.")], name="s2.jsonl")
    r = run_once(src, StubExtractor(), inbox, CursorState("claude-code"))
    assert r.duplicates == 1 and r.proposed == []


def test_truncated_file_restarts(home, tmp_path, inbox):
    root = tmp_path / "projects"
    p = write_session(root, [_line("user", "我喜欢 A 方案"), _line("user", "我喜欢 B 方案")])
    src = ClaudeCodeSource(root)
    run_once(src, StubExtractor(), inbox)
    p.write_text(_line("user", "我喜欢 C 方案"), encoding="utf-8")
    r = run_once(src, StubExtractor(), inbox)
    assert r.messages == 1 and len(r.proposed) == 1


def _m(role, text, i=0):
    return Message(role, text, None, "s", None, f"f#L{i}")


def test_stub_extractor_rules():
    out = StubExtractor().extract([
        _m("user", "我习惯用 uv 管理 Python 项目。我是一名独立开发者"),
        _m("user", "Remember that my dog is called Mochi."),
        _m("user", "今天天气不错"),
        _m("assistant", "I prefer tabs."),
    ])
    kinds = {(c.type, c.content) for c in out}
    assert ("preference", "我习惯用 uv 管理 Python 项目") in kinds
    assert ("fact", "我是一名独立开发者") in kinds
    assert ("fact", "my dog is called Mochi") in kinds
    assert not any("tabs" in c.content for c in out)


def test_llm_extractor_with_mock_transport():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen["auth"] = req.headers.get("authorization")
        seen["model"] = body["model"]
        assert "user: 我住在杭州" in body["messages"][1]["content"]
        content = json.dumps({"memories": [
            {"title": "常住杭州", "content": "用户住在杭州", "type": "fact", "confidence": 0.99,
             "evidence": "我住在杭州", "valid_from": "2025-01-01", "msg": 0},
            {"title": "bad", "content": "x", "type": "weird", "msg": 99},
            "garbage",
        ]})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    ex = OpenAICompatExtractor("https://llm.example/v1", "m1", "k",
                               client=httpx.Client(transport=httpx.MockTransport(handler)))
    out = ex.extract([_m("user", "我住在杭州", 7)])
    assert seen == {"auth": "Bearer k", "model": "m1"}
    assert out[0].type == "fact" and out[0].confidence == 0.9  # capped
    assert out[0].source_ref == "f#L7" and str(out[0].valid_from) == "2025-01-01"
    assert out[1].type == "fact" and out[1].source_ref is None
    assert len(out) == 2
    assert ex.extract([_m("assistant", "hi")]) == []  # no user text -> no call


def test_watch_picks_up_new_lines(home, tmp_path, inbox):
    import os
    import threading
    import time

    from memrelay.capture.runner import watch

    root = tmp_path / "projects"
    p = write_session(root, [_line("user", "我喜欢早起")])
    reports, stop = [], threading.Event()
    th = threading.Thread(target=watch, daemon=True, kwargs=dict(
        source=ClaudeCodeSource(root), extractor=StubExtractor(), inbox=inbox, root=root,
        on_report=reports.append, stop_event=stop, debounce=100))
    th.start()
    deadline = time.time() + 10
    while not reports and time.time() < deadline:
        time.sleep(0.05)
    assert reports and len(reports[0].proposed) == 1
    # FSEvents can emit a spurious event right after subscribe; wait it out, then append.
    time.sleep(1.0)
    with p.open("a", encoding="utf-8") as f:
        f.write(_line("user", "我习惯晚上写代码"))
        f.flush()
        os.fsync(f.fileno())
    os.utime(p, None)
    # Poll inbox (not report count): an empty re-run must not end the wait early.
    deadline = time.time() + 20
    while time.time() < deadline:
        if len(inbox.list()) >= 2:
            break
        time.sleep(0.1)
    stop.set()
    th.join(timeout=5)
    assert len(inbox.list()) >= 2, (
        f"inbox={[(n.title, n) for _, n in inbox.list()]!r} "
        f"reports={[(r.messages, len(r.proposed)) for r in reports]!r}"
    )
