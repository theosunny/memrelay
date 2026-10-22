import json
from pathlib import Path

from typer.testing import CliRunner

from memrelay.cli import app

runner = CliRunner()


def ok(*args):
    r = runner.invoke(app, list(args))
    assert r.exit_code == 0, r.output
    return r.output


def test_end_to_end_cli(home, tmp_path, monkeypatch):
    fake_home = tmp_path / "user"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("APPDATA", str(fake_home / "AppData" / "Roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    cc = tmp_path / "cc"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cc))
    (cc / "projects" / "-w").mkdir(parents=True)
    (cc / "projects" / "-w" / "s.jsonl").write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "我喜欢简洁的中文回复"}},
                   ensure_ascii=False) + "\n", encoding="utf-8")

    ok("init", "--vault", str(tmp_path / "vault"))
    cap = ok("capture", "claude-code")
    assert "proposed=1" in cap and "auto=1" in cap
    assert "proposed=0" in ok("capture", "claude-code")
    assert "Inbox empty" in ok("inbox", "list")
    prefs = list((tmp_path / "vault" / "preferences").glob("*.md"))
    assert len(prefs) == 1 and "简洁" in prefs[0].read_text(encoding="utf-8")

    built = ok("profile", "build", "--yes")
    assert "written:" in built
    assert "Core profile unchanged" in ok("profile", "build", "--yes")
    exported = ok("profile", "export")
    assert "我喜欢简洁的中文回复" in exported and "[[" not in exported

    dry = ok("connect", "install", "cursor", "--dry-run")
    assert "DRY-RUN install" in dry and not (fake_home / ".cursor" / "mcp.json").exists()
    ok("connect", "install", "cursor", "claude-desktop")
    assert (fake_home / ".cursor" / "mcp.json").exists()
    assert "restored" in ok("connect", "rollback", "cursor")
    assert not (fake_home / ".cursor" / "mcp.json").exists()
    assert "claude-code" in ok("connect", "list")
    assert "vault:" in ok("doctor")


def test_installed_script_on_path_is_preferred(tmp_path, monkeypatch):
    """Unix: keep unresolved symlink. Windows: find memrelay.cmd/.exe via PATHEXT."""
    import os
    import sys

    from memrelay.adapters.base import _default_command

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if sys.platform.startswith("win"):
        stub = bin_dir / "memrelay.cmd"
        stub.write_text("@echo off\r\n", encoding="utf-8")
        monkeypatch.setenv("PATH", str(bin_dir))
        cmd, args = _default_command()
        assert Path(cmd).name.lower() in ("memrelay.cmd", "memrelay.exe", "memrelay.bat")
        assert Path(cmd).parent == bin_dir
        assert args == ["serve"]
    else:
        real = tmp_path / "venv" / "bin" / "memrelay"
        real.parent.mkdir(parents=True)
        real.write_text("#!/bin/sh\n", encoding="utf-8")
        real.chmod(0o755)
        shim = bin_dir / "memrelay"
        os.symlink(real, shim)
        monkeypatch.setenv("PATH", str(bin_dir))
        assert _default_command() == (str(shim), ["serve"])


def test_cli_autostart_dry_run_writes_nothing(home, tmp_path, monkeypatch):
    fake = tmp_path / "u"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake / ".config"))
    out = ok("autostart", "install", "--dry-run")
    assert "capture" in out and "--watch" in out
    assert not any(p.is_file() for p in fake.rglob("*"))
    assert "not installed" in ok("autostart", "status").lower() or "未" in ok("autostart", "status")


def test_cli_capture_all_and_connect_all(home, tmp_path, monkeypatch):
    fake = tmp_path / "u"
    (fake / ".gemini").mkdir(parents=True)
    for k, v in {"HOME": fake, "USERPROFILE": fake, "XDG_CONFIG_HOME": fake / ".config",
                 "APPDATA": fake / "AppData", "CODEX_HOME": fake / ".codex",
                 "CLAUDE_CONFIG_DIR": fake / ".claude", "COPILOT_HOME": fake / ".copilot"}.items():
        monkeypatch.setenv(k, str(v))
    monkeypatch.delenv("CLINE_MCP_SETTINGS_PATH", raising=False)
    monkeypatch.delenv("CLINE_DATA_DIR", raising=False)
    day = fake / ".codex" / "sessions" / "2026" / "10" / "18"
    day.mkdir(parents=True)
    (day / "rollout-x.jsonl").write_text(json.dumps(
        {"timestamp": "t", "type": "event_msg", "payload": {"type": "user_message", "message": "我喜欢用 Rust 写工具"}},
        ensure_ascii=False) + "\n", encoding="utf-8")
    out = ok("capture", "all")
    assert "codex" in out and "proposed=1" in out
    out = ok("connect", "--all", "--yes")
    settings = json.loads((fake / ".gemini" / "settings.json").read_text(encoding="utf-8"))
    assert "memrelay" in settings["mcpServers"]
