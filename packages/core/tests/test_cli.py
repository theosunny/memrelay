import json

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
    assert "proposed=1" in ok("capture", "claude-code")
    assert "proposed=0" in ok("capture", "claude-code")
    out = json.loads(ok("inbox", "list", "--json"))
    assert len(out) == 1 and out[0]["type"] == "preference"
    assert "preferences/" in ok("inbox", "approve", out[0]["id"])
    assert "Inbox empty" in ok("inbox", "list")

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
