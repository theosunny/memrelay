import plistlib

import pytest

from memrelay.adapters import Env, ServerSpec
from memrelay.autostart import LABEL, TASK, UNIT, Autostart, watch_command

CMD = ["/Users/me/my apps/memrelay", "capture", "all", "--watch"]


class Rec:
    def __init__(self, rc=0):
        self.calls, self.rc = [], rc

    def __call__(self, c):
        self.calls.append(c)
        return type("R", (), {"returncode": self.rc})()


def test_watch_command():
    assert watch_command(ServerSpec(command="/b/memrelay", args=["serve"])) == ["/b/memrelay", "capture", "all", "--watch"]
    assert watch_command(ServerSpec(command="/py", args=["-m", "memrelay", "serve"])) == ["/py", "-m", "memrelay", "capture", "all", "--watch"]


def test_macos(tmp_path):
    r = Rec()
    a = Autostart(Env("darwin", tmp_path, {}), r, CMD, uid=501)
    plan = a.install(dry_run=True)
    assert not a.plist_path().exists() and r.calls == []
    assert a.plist_path() == tmp_path / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    a.install()
    data = plistlib.loads(a.plist_path().read_bytes())  # valid plist, args not shell-split
    assert data["Label"] == LABEL and data["ProgramArguments"] == CMD and data["RunAtLoad"]
    assert r.calls[-1] == ["launchctl", "bootstrap", "gui/501", str(a.plist_path())]
    assert a.installed()
    a.uninstall()
    assert not a.plist_path().exists() and r.calls[-1] == ["launchctl", "bootout", f"gui/501/{LABEL}"]
    assert plan.os == "macos"


def test_linux(tmp_path):
    r = Rec()
    a = Autostart(Env("linux", tmp_path, {}), r, CMD)
    a.install()
    text = a.unit_path().read_text()
    assert a.unit_path() == tmp_path / ".config" / "systemd" / "user" / UNIT
    assert 'ExecStart="/Users/me/my apps/memrelay" capture all --watch' in text
    assert "WantedBy=default.target" in text
    assert ["systemctl", "--user", "enable", "--now", UNIT] in r.calls
    a.uninstall()
    assert not a.unit_path().exists() and ["systemctl", "--user", "disable", "--now", UNIT] in r.calls
    xa = Autostart(Env("linux", tmp_path, {"XDG_CONFIG_HOME": str(tmp_path / "x")}), r, CMD)
    assert xa.unit_path() == tmp_path / "x" / "systemd" / "user" / UNIT


def test_windows_task_scheduler(tmp_path):
    r = Rec()
    a = Autostart(Env("win32", tmp_path, {}), r, [r"C:\Program Files\mr\memrelay.exe", "capture", "all", "--watch"])
    plan = a.install()
    assert plan.write == {}
    c = r.calls[0]
    assert c[:6] == ["schtasks", "/Create", "/SC", "ONLOGON", "/TN", TASK]
    assert c[7] == r'"C:\Program Files\mr\memrelay.exe" capture all --watch' and "/F" in c
    assert a.installed()
    assert not Autostart(Env("win32", tmp_path, {}), Rec(rc=1), CMD).installed()
    a.uninstall()
    assert r.calls[-1] == ["schtasks", "/Delete", "/TN", TASK, "/F"]


def test_windows_startup_folder(tmp_path):
    r = Rec()
    env = Env("win32", tmp_path, {"APPDATA": str(tmp_path / "AppData" / "Roaming")})
    a = Autostart(env, r, CMD, method="startup-folder")
    a.install()
    p = a.startup_cmd_path()
    assert p.parts[-4:] == ("Start Menu", "Programs", "Startup", "memrelay-capture.cmd")
    assert '"/Users/me/my apps/memrelay" capture all --watch' in p.read_text()
    assert r.calls == [] and a.installed()
    a.uninstall()
    assert not p.exists()


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_dry_run_never_touches_anything(tmp_path, platform):
    r = Rec()
    a = Autostart(Env(platform, tmp_path, {}), r, CMD)
    a.install(dry_run=True)
    a.uninstall(dry_run=True)
    assert r.calls == [] and not any(p.is_file() for p in tmp_path.rglob("*"))
