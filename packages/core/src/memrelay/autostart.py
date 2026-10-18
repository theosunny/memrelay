"""Start the background capture watcher at login, per OS. Every action supports dry-run.

- macOS: LaunchAgent plist in ~/Library/LaunchAgents, loaded with
  `launchctl bootstrap gui/<uid> <plist>` (removal: `launchctl bootout gui/<uid>/<label>`).
  Sources: Apple "Creating Launch Daemons and Agents"
  https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
  and launchctl(1).
- Linux: systemd user unit in $XDG_CONFIG_HOME/systemd/user (default ~/.config/systemd/user),
  enabled with `systemctl --user enable --now`. Source: systemd.unit(5) "User Unit Search
  Path" https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html
- Windows: Task Scheduler logon task via `schtasks /Create /SC ONLOGON /TN ... /TR ...
  /RL LIMITED /F`. Source: https://learn.microsoft.com/windows-server/administration/windows-commands/schtasks-create
  Some Windows editions require elevation for ONLOGON tasks; `--method startup-folder` writes
  a .cmd into the per-user Startup folder instead (shell:startup,
  %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from .adapters.base import Env, ServerSpec

LABEL = "io.memrelay.capture"
UNIT = "memrelay-capture.service"
TASK = "MemRelayCapture"


@dataclass
class Plan:
    os: str
    write: dict[Path, str] = field(default_factory=dict)
    remove: list[Path] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def watch_command(spec: ServerSpec | None = None) -> list[str]:
    spec = spec or ServerSpec()
    base = [spec.command, *spec.args[:-1]] if spec.args and spec.args[-1] == "serve" else [spec.command]
    return [*base, "capture", "all", "--watch"]


def _quote_win(a: str) -> str:
    return f'"{a}"' if (" " in a or not a) else a


class Autostart:
    def __init__(self, env: Env | None = None, runner: Callable[..., object] | None = None,
                 cmd: list[str] | None = None, method: str = "default", uid: int | None = None):
        self.env = env or Env()
        self.runner = runner or (lambda c: subprocess.run(c, check=False, capture_output=True, text=True))
        self.cmd = cmd or watch_command()
        self.method = method
        self.uid = uid if uid is not None else (os.getuid() if hasattr(os, "getuid") else 0)

    # ------------------------------------------------------------- paths
    def plist_path(self) -> Path:
        return self.env.home / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    def unit_path(self) -> Path:
        xdg = self.env.environ.get("XDG_CONFIG_HOME")
        return (Path(xdg) if xdg else self.env.home / ".config") / "systemd" / "user" / UNIT

    def startup_cmd_path(self) -> Path:
        appdata = self.env.environ.get("APPDATA")
        base = Path(appdata) if appdata else self.env.home / "AppData" / "Roaming"
        return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "memrelay-capture.cmd"

    # ------------------------------------------------------------- content
    def plist(self) -> str:
        args = "\n".join(f"    <string>{escape(a)}</string>" for a in self.cmd)
        log = escape(str(self.env.home / "Library" / "Logs" / "memrelay-capture.log"))
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
{args}
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""

    def unit(self) -> str:
        def q(a: str) -> str:
            return '"' + a.replace("\\", "\\\\").replace('"', '\\"') + '"' if any(c in a for c in ' "\\') else a

        return f"""[Unit]
Description=MemRelay capture watcher (agent history -> review inbox)

[Service]
Type=simple
ExecStart={' '.join(q(a) for a in self.cmd)}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
"""

    def startup_cmd(self) -> str:
        return "@echo off\r\nstart \"\" /min " + " ".join(_quote_win(a) for a in self.cmd) + "\r\n"

    # ------------------------------------------------------------- plans
    def plan_install(self) -> Plan:
        os_ = self.env.os
        p = Plan(os_)
        if os_ == "macos":
            p.write[self.plist_path()] = self.plist()
            p.commands.append(["launchctl", "bootout", f"gui/{self.uid}/{LABEL}"])  # ignore failure
            p.commands.append(["launchctl", "bootstrap", f"gui/{self.uid}", str(self.plist_path())])
        elif os_ == "linux":
            p.write[self.unit_path()] = self.unit()
            p.commands += [["systemctl", "--user", "daemon-reload"],
                           ["systemctl", "--user", "enable", "--now", UNIT]]
            p.notes.append("To keep it running without an open session: `loginctl enable-linger $USER`.")
        elif self.method == "startup-folder":
            p.write[self.startup_cmd_path()] = self.startup_cmd()
        else:
            tr = " ".join(_quote_win(a) for a in self.cmd)
            p.commands.append(["schtasks", "/Create", "/SC", "ONLOGON", "/TN", TASK, "/TR", tr,
                               "/RL", "LIMITED", "/F"])
            p.notes.append("If this fails with 'Access is denied', rerun with --method startup-folder.")
        return p

    def plan_uninstall(self) -> Plan:
        os_ = self.env.os
        p = Plan(os_)
        if os_ == "macos":
            p.commands.append(["launchctl", "bootout", f"gui/{self.uid}/{LABEL}"])
            p.remove.append(self.plist_path())
        elif os_ == "linux":
            p.commands += [["systemctl", "--user", "disable", "--now", UNIT],
                           ["systemctl", "--user", "daemon-reload"]]
            p.remove.append(self.unit_path())
        elif self.method == "startup-folder":
            p.remove.append(self.startup_cmd_path())
        else:
            p.commands.append(["schtasks", "/Delete", "/TN", TASK, "/F"])
        return p

    def apply(self, plan: Plan, dry_run: bool = False) -> Plan:
        if dry_run:
            return plan
        for path, text in plan.write.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        # on uninstall, stop the service before deleting its file
        for c in plan.commands:
            self.runner(c)
        for path in plan.remove:
            if path.exists():
                path.unlink()
        return plan

    def install(self, dry_run: bool = False) -> Plan:
        return self.apply(self.plan_install(), dry_run)

    def uninstall(self, dry_run: bool = False) -> Plan:
        return self.apply(self.plan_uninstall(), dry_run)

    def installed(self) -> bool:
        os_ = self.env.os
        if os_ == "macos":
            return self.plist_path().exists()
        if os_ == "linux":
            return self.unit_path().exists()
        if self.method == "startup-folder":
            return self.startup_cmd_path().exists()
        r = self.runner(["schtasks", "/Query", "/TN", TASK])
        return getattr(r, "returncode", 1) == 0
