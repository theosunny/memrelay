import json

from memrelay.adapters import Env, ServerSpec
from memrelay.wizard import discover, run_wizard

SPEC = ServerSpec(command="/x/memrelay", args=["serve"])


def make_env(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".gemini").mkdir()
    (tmp_path / ".gemini" / "settings.json").write_text('{"theme": "x"}')
    (tmp_path / ".codex").mkdir()
    return Env("linux", tmp_path, {})


def test_discover(tmp_path):
    env = make_env(tmp_path)
    found = {a.id: ok for a, ok in discover(env)}
    assert found["cursor"] and found["gemini-cli"] and found["codex"]
    assert not found["claude-desktop"] and not found["doubao"]


def test_wizard_asks_per_agent(home, tmp_path):
    env = make_env(tmp_path)
    asked, out = [], []

    def confirm(q):
        asked.append(q)
        return "Cursor" in q or "Codex" in q  # decline Gemini

    res = run_wizard(SPEC, confirm, out.append, env=env)
    assert sorted(c.adapter for c in res.applied) == ["codex", "cursor"]
    assert res.skipped == ["gemini-cli"] and len(asked) == 3
    assert set(res.guided) == {"doubao", "kimi", "qwen"}
    assert json.loads((tmp_path / ".gemini" / "settings.json").read_text()) == {"theme": "x"}
    assert "memrelay" in json.loads((tmp_path / ".cursor" / "mcp.json").read_text())["mcpServers"]
    text = "\n".join(out)
    assert "写入 / write" in text and "mcpServers" in text  # preview + guided snippet shown

    # second run: everything already connected is reported, nothing re-asked for them
    asked.clear()
    res2 = run_wizard(SPEC, lambda q: False, out.append, env=env, include_guided=False)
    assert sorted(res2.already) == ["codex", "cursor"] and res2.skipped == ["gemini-cli"]


def test_wizard_yes_and_errors(home, tmp_path):
    env = make_env(tmp_path)
    (tmp_path / ".cursor" / "mcp.json").write_text("{broken")
    res = run_wizard(SPEC, lambda q: False, lambda s: None, env=env, yes=True, include_guided=False)
    assert "cursor" in res.errors and sorted(c.adapter for c in res.applied) == ["codex", "gemini-cli"]
