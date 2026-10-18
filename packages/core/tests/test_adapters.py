import json
from pathlib import Path

import pytest

from memrelay.adapters import ADAPTERS, Env, ServerSpec, get_adapter

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
}


@pytest.mark.parametrize("aid,platform", sorted(EXPECTED))
def test_paths(tmp_path, aid, platform):
    a = get_adapter(aid, env_for(platform, tmp_path))
    assert a.config_path() == tmp_path / EXPECTED[(aid, platform)]
    assert a.sources, "every adapter must cite where its path comes from"


def test_linux_xdg(tmp_path):
    a = get_adapter("claude-desktop", Env("linux", tmp_path, {"XDG_CONFIG_HOME": str(tmp_path / "x")}))
    assert a.config_path() == tmp_path / "x" / "Claude" / "claude_desktop_config.json"


@pytest.mark.parametrize("aid", sorted(ADAPTERS))
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
    if aid in ("claude-code", "cursor"):
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
