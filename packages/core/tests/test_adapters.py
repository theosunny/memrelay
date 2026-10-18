import json
from pathlib import Path

import pytest

from memrelay.adapters import ADAPTERS, Env, JsonMcpAdapter, ServerSpec, get_adapter, is_guided

SPEC = ServerSpec(command="/opt/py/bin/python", args=["-m", "memrelay", "serve"])


def env_for(platform: str, home: Path) -> Env:
    environ = {}
    if platform == "win32":
        environ["APPDATA"] = str(home / "AppData" / "Roaming")
    return Env(platform=platform, home=home, environ=environ)


EXPECTED = {
    # adapter, platform -> path relative to fake home
    ("claude-code", "win32"): ".claude.json",
    ("claude-code", "darwin"): ".claude.json",
    ("claude-code", "linux"): ".claude.json",
    ("cursor", "win32"): ".cursor/mcp.json",
    ("cursor", "darwin"): ".cursor/mcp.json",
    ("cursor", "linux"): ".cursor/mcp.json",
    ("claude-desktop", "win32"): "AppData/Roaming/Claude/claude_desktop_config.json",
    ("claude-desktop", "darwin"): "Library/Application Support/Claude/claude_desktop_config.json",
    ("claude-desktop", "linux"): ".config/Claude/claude_desktop_config.json",
    ("windsurf", "win32"): "AppData/Roaming/devin/mcp_config.json",
    ("windsurf", "darwin"): ".config/devin/mcp_config.json",
    ("windsurf", "linux"): ".config/devin/mcp_config.json",
    ("codex", "win32"): ".codex/config.toml",
    ("codex", "darwin"): ".codex/config.toml",
    ("codex", "linux"): ".codex/config.toml",
    ("gemini-cli", "win32"): ".gemini/settings.json",
    ("gemini-cli", "darwin"): ".gemini/settings.json",
    ("gemini-cli", "linux"): ".gemini/settings.json",
    ("vscode", "win32"): ".copilot/mcp-config.json",
    ("vscode", "darwin"): ".copilot/mcp-config.json",
    ("vscode", "linux"): ".copilot/mcp-config.json",
    ("cline", "win32"): ".cline/data/settings/cline_mcp_settings.json",
    ("cline", "darwin"): ".cline/data/settings/cline_mcp_settings.json",
    ("cline", "linux"): ".cline/data/settings/cline_mcp_settings.json",
    ("cline-vscode", "win32"): "AppData/Roaming/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    ("cline-vscode", "darwin"): "Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    ("cline-vscode", "linux"): ".config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
}
JSON_ADAPTERS = sorted(a for a, c in ADAPTERS.items() if issubclass(c, JsonMcpAdapter))
TYPED = {"claude-code", "cursor", "vscode"}


@pytest.mark.parametrize("aid,platform", sorted(EXPECTED))
def test_paths(tmp_path, aid, platform):
    a = get_adapter(aid, env_for(platform, tmp_path))
    assert a.config_path() == tmp_path / EXPECTED[(aid, platform)]
    assert a.sources, "every adapter must cite where its path comes from"


def test_linux_xdg(tmp_path):
    a = get_adapter("claude-desktop", Env("linux", tmp_path, {"XDG_CONFIG_HOME": str(tmp_path / "x")}))
    assert a.config_path() == tmp_path / "x" / "Claude" / "claude_desktop_config.json"


@pytest.mark.parametrize("aid", JSON_ADAPTERS)
@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_install_preserves_and_rolls_back(home, tmp_path, aid, platform):
    a = get_adapter(aid, env_for(platform, tmp_path))
    p = a.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    original = {"theme": "dark", "mcpServers": {"other": {"command": "x"}}, "projects": {"/a": {}}}
    p.write_text(json.dumps(original), encoding="utf-8")
    raw_before = p.read_bytes()

    ch = a.install(SPEC)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and data["projects"] == {"/a": {}}
    assert data["mcpServers"]["other"] == {"command": "x"}
    entry = data["mcpServers"]["memrelay"]
    assert entry["command"] == SPEC.command and entry["args"] == SPEC.args
    if aid in TYPED:
        assert entry["type"] == "stdio"  # required by their docs
    else:
        assert "type" not in entry
    assert ch.backup and ch.backup.read_bytes() == raw_before
    assert a.install(SPEC).action == "noop"  # idempotent, no extra backup
    assert len(a.backups()) == 1

    assert a.rollback() is not None
    assert p.read_bytes() == raw_before
    assert a.rollback() is None


def test_install_into_missing_file_then_rollback_removes_it(home, tmp_path):
    a = get_adapter("cursor", env_for("linux", tmp_path))
    p = a.config_path()
    assert not p.exists()
    a.install(SPEC)
    assert json.loads(p.read_text())["mcpServers"]["memrelay"]["type"] == "stdio"
    a.rollback()
    assert not p.exists()


def test_dry_run_writes_nothing(home, tmp_path):
    a = get_adapter("claude-desktop", env_for("darwin", tmp_path))
    ch = a.install(SPEC, dry_run=True)
    assert ch.dry_run and ch.action == "install" and not a.config_path().exists()
    assert a.backups() == []


def test_invalid_json_is_refused(home, tmp_path):
    a = get_adapter("cursor", env_for("linux", tmp_path))
    p = a.config_path()
    p.parent.mkdir(parents=True)
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError):
        a.install(SPEC)
    assert p.read_text() == "{ not json"


def test_uninstall(home, tmp_path):
    a = get_adapter("claude-code", env_for("linux", tmp_path))
    a.install(SPEC)
    assert a.installed() is not None
    ch = a.uninstall()
    assert ch.action == "uninstall" and a.installed() is None
    assert a.uninstall().action == "noop"
    a.rollback()  # undo the uninstall
    assert a.installed() is not None


def test_unknown_adapter():
    with pytest.raises(KeyError):
        get_adapter("nope")


def test_every_file_adapter_has_expected_paths():
    file_based = {a for a, c in ADAPTERS.items() if not is_guided(c())}
    assert file_based == {a for a, _ in EXPECTED}


def test_env_overrides(tmp_path):
    e = {"CODEX_HOME": str(tmp_path / "cx"), "COPILOT_HOME": str(tmp_path / "cp"),
         "CLINE_MCP_SETTINGS_PATH": str(tmp_path / "c.json")}
    env = Env("linux", tmp_path, e)
    assert get_adapter("codex", env).config_path() == tmp_path / "cx" / "config.toml"
    assert get_adapter("vscode", env).config_path() == tmp_path / "cp" / "mcp-config.json"
    assert get_adapter("cline", env).config_path() == tmp_path / "c.json"
    env = Env("linux", tmp_path, {"CLINE_DATA_DIR": str(tmp_path / "d")})
    assert get_adapter("cline", env).config_path() == tmp_path / "d" / "settings" / "cline_mcp_settings.json"


def test_codex_toml_preserves_comments_and_rolls_back(home, tmp_path):
    import tomllib

    a = get_adapter("codex", env_for("linux", tmp_path))
    p = a.config_path()
    p.parent.mkdir(parents=True)
    original = '# my codex config\nmodel = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x" # keep\n'
    p.write_text(original, encoding="utf-8")
    ch = a.install(SPEC)
    text = p.read_text(encoding="utf-8")
    assert "# my codex config" in text and "# keep" in text
    data = tomllib.loads(text)
    assert data["model"] == "gpt-5" and data["mcp_servers"]["other"] == {"command": "x"}
    assert data["mcp_servers"]["memrelay"] == {"command": SPEC.command, "args": SPEC.args}
    assert ch.backup and a.install(SPEC).action == "noop"
    assert a.installed() == {"command": SPEC.command, "args": SPEC.args}
    a.uninstall()
    assert "memrelay" not in tomllib.loads(p.read_text())["mcp_servers"]
    a.rollback()
    a.rollback()
    assert p.read_text(encoding="utf-8") == original


def test_codex_new_file_and_bad_toml(home, tmp_path):
    import tomllib

    a = get_adapter("codex", env_for("darwin", tmp_path))
    a.install(SPEC)
    assert tomllib.loads(a.config_path().read_text())["mcp_servers"]["memrelay"]["args"] == SPEC.args
    a.config_path().write_text("[[[ broken", encoding="utf-8")
    with pytest.raises(ValueError):
        a.install(ServerSpec(command="/other", args=["serve"]))


@pytest.mark.parametrize("aid", ["doubao", "kimi", "qwen"])
def test_guided_adapters_write_nothing(home, tmp_path, aid):
    a = get_adapter(aid, env_for("win32", tmp_path))
    assert is_guided(a) and a.config_path() is None and not a.detect()
    ch = a.install(SPEC)
    assert ch.action == "guided" and ch.dry_run
    assert ch.after == {"mcpServers": {"memrelay": {"command": SPEC.command, "args": SPEC.args}}}
    assert "mcpServers" in ch.note and "设置" in ch.note
    assert list(tmp_path.rglob("*")) == [] or not any(p.is_file() for p in tmp_path.rglob("*"))
    assert a.sources[0].startswith("unverified")


def test_default_spec_prefers_installed_console_script(monkeypatch, tmp_path):
    import sys

    from memrelay.adapters import base

    exe = tmp_path / "bin" / "memrelay"
    exe.parent.mkdir()
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(base.shutil, "which", lambda name: str(exe) if name == "memrelay" else None)
    s = ServerSpec()
    assert s.command == str(exe.absolute()) and s.args == ["serve"]
    monkeypatch.setattr(base.shutil, "which", lambda name: None)
    s = ServerSpec()
    assert s.command == sys.executable and s.args == ["-m", "memrelay", "serve"]
