"""Guided adapters: clients whose MCP config location is not publicly documented.

MemRelay never guesses a path. For these it prints a ready-to-paste JSON snippet and the
steps to add it through the app's own settings UI; nothing is written to disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import AgentAdapter, Change, ServerSpec


class GuidedAdapter(AgentAdapter):
    steps_zh: tuple[str, ...] = ()
    steps_en: tuple[str, ...] = ()
    guided = True

    def config_path(self) -> Path | None:
        return None

    def detect(self) -> bool:
        return False  # cannot be verified without a documented path

    def installed(self, name: str = "memrelay"):
        return None

    def snippet(self, spec: ServerSpec) -> dict:
        e = {"command": spec.command, "args": list(spec.args)}
        if spec.env:
            e["env"] = dict(spec.env)
        return {"mcpServers": {spec.name: e}}

    def instructions(self, spec: ServerSpec) -> str:
        js = json.dumps(self.snippet(spec), ensure_ascii=False, indent=2)
        zh = "\n".join(f"  {i}. {s}" for i, s in enumerate(self.steps_zh, 1))
        en = "\n".join(f"  {i}. {s}" for i, s in enumerate(self.steps_en, 1))
        return f"{self.name} —— 手动接入 / manual setup\n{zh}\n{en}\n\n{js}\n"

    def install(self, spec: ServerSpec, dry_run: bool = False) -> Change:
        return Change(self.id, Path(), "guided", None, self.snippet(spec), dry_run=True,
                      note=self.instructions(spec))

    def uninstall(self, name: str = "memrelay", dry_run: bool = False) -> Change:
        return Change(self.id, Path(), "guided", None, None, dry_run=True,
                      note=f"在 {self.name} 的 MCP 设置中删除 “{name}”。/ Remove “{name}” in {self.name}'s MCP settings.")

    def rollback(self):
        return None


_COMMON_ZH = (
    "打开桌面客户端的「设置」，找到「MCP / 插件 / 工具 / 扩展」相关入口（各版本名称不同）",
    "选择「添加自定义 MCP 服务器」，类型选 stdio / 本地命令（若支持粘贴 JSON 则直接粘贴下方内容）",
    "保存并重启客户端，在对话中让它调用 get_profile 验证",
)
_COMMON_EN = (
    "Open the desktop app's Settings and find the MCP / plugins / tools section (name varies)",
    "Add a custom MCP server of type stdio / local command (or paste the JSON below if supported)",
    "Save, restart the app, and ask it to call get_profile to verify",
)


class DoubaoAdapter(GuidedAdapter):
    id, name = "doubao", "豆包 Doubao (desktop)"
    sources = ("unverified: no public doc for the config file path as of 2026-10-18",)
    steps_zh, steps_en = _COMMON_ZH, _COMMON_EN


class KimiAdapter(GuidedAdapter):
    id, name = "kimi", "Kimi (desktop)"
    sources = ("unverified: no public doc for the config file path as of 2026-10-18",)
    steps_zh, steps_en = _COMMON_ZH, _COMMON_EN


class QwenAdapter(GuidedAdapter):
    id, name = "qwen", "通义千问 Qwen (desktop)"
    sources = ("unverified: no public doc for the config file path as of 2026-10-18",)
    steps_zh, steps_en = _COMMON_ZH, _COMMON_EN
